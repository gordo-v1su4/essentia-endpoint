"""One bounded worker with durable owner-isolated jobs; no automatic recompute."""
from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid

from services.studio_analysis import validate_studio_result

log = logging.getLogger(__name__)
TERMINAL = {"completed", "failed"}
JOB_ID = re.compile(r"^[0-9a-f]{32}$")


class JobError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


@dataclass(frozen=True)
class JobSettings:
    directory: Path
    max_upload_bytes: int = 256 * 1024 * 1024
    max_pending: int = 4
    max_uploads: int = 2
    max_jobs: int = 64
    max_storage_bytes: int = 2 * 1024 * 1024 * 1024
    max_scratch_bytes: int = 1024 * 1024 * 1024
    max_result_bytes: int = 8 * 1024 * 1024
    ttl_seconds: int = 86400
    timeout_seconds: int = 1200

    @classmethod
    def from_env(cls):
        defaults = cls(Path(os.getenv("STUDIO_JOBS_DIR", "/app/studio-jobs")))
        values = {name: int(os.getenv("STUDIO_" + name.upper(), str(getattr(defaults, name))))
                  for name in cls.__dataclass_fields__ if name != "directory"}
        if any(value <= 0 for value in values.values()):
            raise ValueError("Studio job limits must be positive.")
        return cls(directory=defaults.directory, **values)


def directory_bytes(path: Path) -> int:
    total = 0
    for candidate in path.rglob("*"):
        try:
            if candidate.is_file():
                total += candidate.stat().st_size
        except FileNotFoundError:
            pass  # Worker cleanup may remove a scratch file during inspection.
    return total


def log_worker_failure(directory: Path, code: str):
    """Retain bounded, credential-redacted provider detail in server logs only."""
    try:
        with (directory / "worker.log").open("rb") as file:
            file.seek(0, 2)
            file.seek(max(0, file.tell() - 8192))
            detail = file.read().decode("utf-8", errors="replace")
    except OSError:
        detail = "No worker diagnostic was available."
    for name, value in os.environ.items():
        if any(marker in name.upper() for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            for secret in value.split(","):
                if len(secret) >= 4:
                    detail = detail.replace(secret, "[redacted]")
    log.error("Studio job %s failed (%s). Worker diagnostic (last8KiB):\n%s", directory.name, code, detail)


def isolated_analysis(path: Path, progress, settings: JobSettings, stopping=lambda: False):
    """Bound inference time/disk usage and terminate its process group on failure."""
    output, stage = path.parent / "analysis.json", path.parent / "stage.txt"
    with (path.parent / "worker.log").open("wb") as logfile:
        process = subprocess.Popen(
            [sys.executable, "-m", "services.studio_analysis", str(path), str(output), str(stage)],
            cwd=str(Path(__file__).resolve().parent.parent), stdout=logfile, stderr=logfile,
            start_new_session=True,
        )
        start, previous = time.monotonic(), ""
        try:
            while process.poll() is None:
                if stopping():
                    raise JobError(422, "interrupted", "Server stopped before analysis completed. Submit a new job to retry.")
                if time.monotonic() - start > settings.timeout_seconds:
                    raise JobError(422, "analysis_timeout", "Audio analysis exceeded its time limit.")
                if directory_bytes(path.parent) > settings.max_scratch_bytes + settings.max_upload_bytes:
                    raise JobError(422, "analysis_storage_limit", "Audio analysis exceeded its temporary storage limit.")
                if stage.exists():
                    value = stage.read_text()
                    if value in {"decoding", "rhythm", "structure", "validating"} and value != previous:
                        progress(value)
                        previous = value
                time.sleep(0.25)
            if process.returncode != 0 or not output.is_file():
                error_file = path.parent / "error.json"
                if error_file.is_file() and json.loads(error_file.read_text()).get("code") == "cuda_unavailable":
                    raise JobError(422, "cuda_unavailable", "Studio requires usable CUDA and ALLIN1_DEVICE=cuda; CPU/MPS inference is disabled.")
                # Detailed provider logs remain server-side, never in API errors.
                log.error("Studio analyzer failed for job %s", path.parent.name)
                raise JobError(422, "analysis_failed", "Audio analysis failed; no estimated structure was substituted.")
            if output.stat().st_size > settings.max_result_bytes:
                raise JobError(422, "result_too_large", "Audio analysis result exceeded its storage limit.")
            return json.loads(output.read_text())
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


class StudioJobs:
    def __init__(self, settings: JobSettings, analyzer=None, clock=time.time):
        self.settings, self.clock = settings, clock
        self.analyzer = analyzer or (lambda path, progress: isolated_analysis(path, progress, settings, lambda: self.stopping))
        self.lock = threading.Condition(threading.RLock())
        self.jobs, self.uploads = {}, {}
        self.worker = None
        self.stopping = False
        self.process_lock = None

    def _write(self, job):
        target = self.settings.directory / job["id"] / "job.json"
        temporary = target.with_suffix(".tmp")
        with temporary.open("w") as file:
            json.dump(job, file, allow_nan=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(target)

    def _cleanup(self):
        for key, job in list(self.jobs.items()):
            if job["status"] in TERMINAL and self.clock() - job["updated_at"] >= self.settings.ttl_seconds:
                shutil.rmtree(self.settings.directory / key)
                del self.jobs[key]

    def start(self):
        import fcntl
        with self.lock:
            if self.worker is not None:
                return
            root = self.settings.directory
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.process_lock = (root / ".worker.lock").open("a")
            try:
                fcntl.flock(self.process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.process_lock.close()
                self.process_lock = None
                raise RuntimeError("Studio jobs directory already has a worker; run one API process.")
            # Incomplete inputs and interrupted jobs must not silently run again.
            for path in root.iterdir():
                if not path.is_dir():
                    continue
                if path.name.startswith("upload-"):
                    shutil.rmtree(path)
                elif JOB_ID.fullmatch(path.name):
                    try:
                        job = json.loads((path / "job.json").read_text())
                        if job["id"] != path.name:
                            raise ValueError("Mismatched job directory")
                        self.jobs[job["id"]] = job
                        if job["status"] not in TERMINAL:
                            job.update(status="failed", stage="interrupted", updated_at=self.clock(), error={
                                "code": "interrupted", "message": "Server restarted before analysis completed. Submit a new job to retry.",
                            })
                            self._write(job)
                        elif job["status"] == "completed":
                            try:
                                validate_studio_result(json.loads((path / "result.json").read_text()))
                            except (ValueError, OSError):
                                job.update(status="failed", stage="failed", updated_at=self.clock(), error={
                                    "code": "result_unavailable", "message": "The saved analysis result is unavailable or invalid. Submit a new job to retry.",
                                })
                                self._write(job)
                        self._remove_work_files(path)
                    except (ValueError, KeyError, OSError):
                        log.error("Discarding incomplete Studio job directory %s", path.name)
                        shutil.rmtree(path)
            self._cleanup()
            self.stopping = False
            self.worker = threading.Thread(target=self._work, name="studio-analysis", daemon=True)
            self.worker.start()

    def stop(self):
        with self.lock:
            self.stopping = True
            self.lock.notify_all()
        if self.worker:
            # Keep ownership until an active bounded child exits. API shutdown is
            # normally externally time-bounded; next startup fails interrupted jobs.
            self.worker.join(timeout=2)
            if self.worker.is_alive():
                return
            self.worker = None
        if self.process_lock:
            self.process_lock.close()
            self.process_lock = None

    def _identity(self, owner, key):
        if not key or len(key) > 200 or not key.isascii() or any(ord(c) < 33 for c in key):
            raise JobError(422, "invalid_idempotency_key", "Idempotency-Key must contain 1–200 printable non-space ASCII characters.")
        owner_hash = hashlib.sha256(owner.encode()).hexdigest()
        return owner_hash, hashlib.sha256((owner_hash + ":" + key).encode()).hexdigest()

    def begin_upload(self, owner, key):
        owner_hash, identity = self._identity(owner, key)
        with self.lock:
            if self.worker is None or self.stopping:
                raise JobError(503, "unavailable", "Studio analysis worker is unavailable.")
            self._cleanup()
            exists = any(j["identity"] == identity for j in self.jobs.values())
            pending = sum(j["status"] not in TERMINAL for j in self.jobs.values())
            if len(self.uploads) >= self.settings.max_uploads or (not exists and (
                pending + len(self.uploads) >= self.settings.max_pending or
                len(self.jobs) + len(self.uploads) >= self.settings.max_jobs
            )):
                raise JobError(429, "queue_full", "Studio analysis capacity is full. Retry later with the same idempotency key.")
            reserved = (len(self.uploads) + 1) * self.settings.max_upload_bytes
            if directory_bytes(self.settings.directory) + reserved + self.settings.max_scratch_bytes > self.settings.max_storage_bytes:
                raise JobError(507, "storage_full", "Studio analysis storage is full. Retry later.")
            token = uuid.uuid4().hex
            directory = self.settings.directory / ("upload-" + token)
            directory.mkdir(mode=0o700)
            self.uploads[token] = (owner_hash, identity, directory)
            return token, directory

    def abort_upload(self, token):
        with self.lock:
            upload = self.uploads.pop(token, None)
            if upload:
                shutil.rmtree(upload[2], ignore_errors=True)

    def submit(self, token, path: Path, checksum: str):
        with self.lock:
            owner, identity, directory = self.uploads[token]
            if path.parent != directory or not path.is_file() or not 0 < path.stat().st_size <= self.settings.max_upload_bytes:
                raise JobError(413, "invalid_upload_size", "Audio must be nonempty and within the upload limit.")
            for job in self.jobs.values():
                if job["identity"] == identity:
                    if job["checksum"] != checksum:
                        raise JobError(409, "idempotency_conflict", "This idempotency key was already used for different audio.")
                    self.abort_upload(token)
                    return self._response(job)
            key = uuid.uuid4().hex
            target = self.settings.directory / key
            directory.replace(target)
            del self.uploads[token]
            job = {"id": key, "identity": identity, "owner": owner, "checksum": checksum,
                   "input": path.name, "status": "queued", "stage": "queued",
                   "created_at": self.clock(), "updated_at": self.clock()}
            self._write(job)
            self.jobs[key] = job
            self.lock.notify_all()
            return self._response(job)

    def get(self, owner, key):
        with self.lock:
            self._cleanup()
            job = self.jobs.get(key)
            if not job or job["owner"] != hashlib.sha256(owner.encode()).hexdigest():
                raise JobError(404, "not_found", "Studio analysis job not found.")
            return self._response(job)

    def _response(self, job):
        response = {key: job[key] for key in ("id", "status", "stage")}
        if job["status"] == "completed":
            response["result"] = json.loads((self.settings.directory / job["id"] / "result.json").read_text())
        elif job["status"] == "failed":
            response["error"] = job["error"]
        return response

    def _remove_work_files(self, directory):
        for path in directory.iterdir():
            if path.name in {"job.json", "result.json"}:
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    def _work(self):
        while True:
            with self.lock:
                self._cleanup()
                if self.stopping:
                    return
                job = next((j for j in self.jobs.values() if j["status"] == "queued"), None)
                if job is None:
                    self.lock.wait(timeout=30)
                    continue
                job.update(status="running", stage="starting", updated_at=self.clock())
                self._write(job)
            directory = self.settings.directory / job["id"]
            def progress(stage):
                with self.lock:
                    job.update(stage=stage, updated_at=self.clock())
                    self._write(job)
            try:
                result = validate_studio_result(self.analyzer(directory / job["input"], progress))
                payload = json.dumps(result, allow_nan=False)
                if len(payload.encode()) > self.settings.max_result_bytes:
                    raise JobError(422, "result_too_large", "Audio analysis result exceeded its storage limit.")
                temporary = directory / "result.tmp"
                with temporary.open("w") as file:
                    file.write(payload)
                    file.flush()
                    os.fsync(file.fileno())
                temporary.replace(directory / "result.json")
                with self.lock:
                    job.update(status="completed", stage="completed", updated_at=self.clock())
                    self._write(job)
            except Exception as exc:
                code = exc.code if isinstance(exc, JobError) else "analysis_failed"
                message = exc.message if isinstance(exc, JobError) else "Audio analysis failed validation; no estimated structure was substituted."
                log_worker_failure(directory, code)
                with self.lock:
                    job.update(status="failed", stage="failed", updated_at=self.clock(), error={"code": code, "message": message})
                    self._write(job)
            finally:
                self._remove_work_files(directory)
