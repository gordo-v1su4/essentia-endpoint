import copy
from dataclasses import replace
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("API_KEYS", "test-owner-a,test-owner-b")
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.studio_routes import StudioUploadLimits, router
from services.studio_analysis import build_studio_result, validate_studio_result, StudioAnalysisError
from services.studio_jobs import JobSettings, StudioJobs, JobError, isolated_analysis
from services.allin1_structure import require_studio_cuda, AllInOneCudaRequiredError, analyze_structure_allin1_logic


def fixture():
    rhythm = {"duration": 2.0, "bpm": 120, "beats": [0.0, 0.5, 1.0, 1.5], "confidence": 2.4,
              "onsets": [0.1, 0.8], "energy": {"curve": [0.2] * 87 + [0.8] * 87}}
    structure = {"source": "allin1", "analyzed_duration_s": 2.0, "boundaries": [0.0, 1.0, 2.0], "sections": [
        {"start": 0.0, "end": 1.0, "duration": 1.0, "label": "intro", "original_label": "intro", "energy": 0.0},
        {"start": 1.0, "end": 2.0, "duration": 1.0, "label": "section", "original_label": "end", "energy": 0.0},
    ]}
    return build_studio_result(rhythm, structure, "harmonix-all")


class ResultTests(unittest.TestCase):
    def test_energy_time_grid_and_raw_end_label(self):
        value = fixture()
        self.assertEqual(value["energy"]["sample_rate_hz"], 44100 / 512)
        self.assertEqual(value["energy"]["start_time_s"], 0)
        self.assertAlmostEqual(value["structure"]["sections"][0]["energy"], 0.2)
        self.assertAlmostEqual(value["structure"]["sections"][1]["energy"], 0.8)
        self.assertEqual(value["structure"]["sections"][1]["original_label"], "end")
        self.assertEqual(value["structure"]["provenance"]["device"], "cuda")

    def test_incomplete_or_invalid_analysis_fails_without_fallback(self):
        changes = [
            lambda r: r.update(duration=4),
            lambda r: r["beats"].append(0.5),
            lambda r: r["onsets"].append(float("nan")),
            lambda r: r["energy"]["curve"].clear(),
            lambda r: r["structure"]["boundaries"].append(2.5),
            lambda r: r["structure"]["sections"][1].update(start=1.5, duration=0.5),
            lambda r: r["structure"]["sections"][1].update(start=0.5, duration=1.5),
        ]
        for change in changes:
            with self.subTest(change=change):
                value = fixture(); change(value)
                with self.assertRaises(ValueError): validate_studio_result(value)

    def test_only_small_edge_rounding_is_accepted_without_stretching(self):
        value = fixture()
        value["structure"]["sections"][-1].update(end=1.9, duration=0.9)
        value["structure"]["boundaries"][-1] = 1.9
        value["structure"]["analyzed_duration_s"] = 1.9
        self.assertEqual(validate_studio_result(value)["structure"]["sections"][-1]["end"], 1.9)
        value["structure"]["sections"][-1].update(end=1.7, duration=0.7)
        value["structure"]["boundaries"][-1] = 1.7
        with self.assertRaises(StudioAnalysisError): validate_studio_result(value)

    def test_cuda_required_and_no_cpu_or_mps_fallback(self):
        for configured in ("cpu", "mps"):
            with patch.dict(os.environ, {"ALLIN1_DEVICE": configured}), patch("services.allin1_structure._cuda_usable", return_value=True):
                with self.assertRaises(AllInOneCudaRequiredError): require_studio_cuda()
        with patch.dict(os.environ, {"ALLIN1_DEVICE": "cuda"}), patch("services.allin1_structure._cuda_usable", return_value=False):
            with self.assertRaises(AllInOneCudaRequiredError): require_studio_cuda()
        with patch.dict(os.environ, {"ALLIN1_DEVICE": "cuda"}), patch("services.allin1_structure._cuda_usable", return_value=True):
            self.assertEqual(require_studio_cuda(), "cuda")

    def test_allin1_receives_cuda_and_preserves_end_interval(self):
        import types
        from unittest.mock import Mock
        raw = types.SimpleNamespace(segments=[
            types.SimpleNamespace(start=0, end=1, label="verse"),
            types.SimpleNamespace(start=1, end=2, label="end"),
        ], bpm=120)
        analyze = Mock(return_value=raw)
        with patch.dict("sys.modules", {"allin1": types.SimpleNamespace(analyze=analyze)}), patch("services.allin1_structure.require_studio_cuda", return_value="cuda"):
            value = analyze_structure_allin1_logic("input.wav", workspace=Path("job/scratch"), preserve_labels=True, require_cuda=True)
        self.assertEqual(analyze.call_args.kwargs["device"], "cuda")
        self.assertFalse(analyze.call_args.kwargs["multiprocess"])
        self.assertEqual(value["boundaries"], [0, 1, 2])
        self.assertEqual(value["sections"][-1]["original_label"], "end")
        self.assertEqual(value["sections"][-1]["label"], "section")


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = JobSettings(Path(self.tmp.name), max_upload_bytes=1024, max_storage_bytes=1000000,
                                    max_scratch_bytes=4096, ttl_seconds=100)
        self.managers = []

    def tearDown(self):
        for manager in self.managers: manager.stop()
        self.tmp.cleanup()

    def manager(self, analyzer=None, **options):
        manager = StudioJobs(options.pop("settings", self.settings), analyzer or (lambda p, progress: fixture()), **options)
        manager.start(); self.managers.append(manager)
        return manager

    def submit(self, manager, key="request-1", owner="test-owner-a", body=b"fake-wave"):
        token, directory = manager.begin_upload(owner, key)
        path = directory / "input.wav"; path.write_bytes(body)
        try: return manager.submit(token, path, hashlib.sha256(body).hexdigest())
        finally: manager.abort_upload(token)

    def wait(self, manager, job, expected="completed"):
        for _ in range(200):
            value = manager.get("test-owner-a", job["id"])
            if value["status"] in {"completed", "failed"}:
                self.assertEqual(value["status"], expected)
                return value
            time.sleep(0.01)
        self.fail("Worker did not finish")

    def test_result_persists_across_restart_no_recompute(self):
        calls = []
        manager = self.manager(lambda p, progress: calls.append(p) or fixture())
        job = self.submit(manager); result = self.wait(manager, job)
        manager.stop()
        restarted = self.manager(lambda p, progress: self.fail("must not recompute"))
        self.assertEqual(restarted.get("test-owner-a", job["id"]), result)
        self.assertEqual(len(calls), 1)
        self.assertFalse((self.settings.directory / job["id"] / "input.wav").exists())

    def test_owner_isolation_and_idempotency_conflict(self):
        manager = self.manager()
        first = self.submit(manager); self.wait(manager, first)
        self.assertEqual(self.submit(manager)["id"], first["id"])
        with self.assertRaises(JobError) as error: self.submit(manager, body=b"different")
        self.assertEqual(error.exception.status, 409)
        with self.assertRaises(JobError) as error: manager.get("test-owner-b", first["id"])
        self.assertEqual(error.exception.status, 404)
        second = self.submit(manager, owner="test-owner-b")
        self.assertNotEqual(first["id"], second["id"])

    def test_single_worker_bounded_queue_and_live_stage(self):
        release, started = threading.Event(), threading.Event()
        calls = []
        def analyzer(path, progress):
            calls.append(path); progress("structure"); started.set(); release.wait(2); return fixture()
        manager = self.manager(analyzer, settings=replace(self.settings, max_pending=2))
        first = self.submit(manager); self.assertTrue(started.wait(1))
        second = self.submit(manager, key="second")
        self.assertEqual(manager.get("test-owner-a", first["id"])["stage"], "structure")
        self.assertEqual(manager.get("test-owner-a", second["id"])["status"], "queued")
        self.assertEqual(len(calls), 1)
        with self.assertRaises(JobError) as error: self.submit(manager, key="third")
        self.assertEqual(error.exception.status, 429)
        release.set(); self.wait(manager, first); self.wait(manager, second)
        self.assertEqual(len(calls), 2)

    def test_failed_analysis_stays_failed_and_redacts_details(self):
        def fail(path, progress): raise ValueError("secretprovider detail /private/input.wav")
        manager = self.manager(fail)
        job = self.submit(manager); result = self.wait(manager, job, "failed")
        self.assertNotIn("secretprovider", json.dumps(result))
        self.assertNotIn("result", result)
        self.assertEqual(self.submit(manager)["status"], "failed")

    def test_worker_diagnostic_survives_cleanup_in_server_logs_only(self):
        def fail(path, progress):
            (path.parent / "worker.log").write_text("old-irrelevant-prefix" + "x" * 9000 + "\nCUDA root cause test-secret-value")
            raise ValueError("provider failed")
        manager = self.manager(fail)
        with patch.dict(os.environ, {"TEST_PROVIDER_KEY": "test-secret-value"}), self.assertLogs("services.studio_jobs", level="ERROR") as logs:
            job = self.submit(manager); result = self.wait(manager, job, "failed")
        text = "\n".join(logs.output)
        self.assertIn("CUDA root cause", text)
        self.assertNotIn("test-secret-value", text)
        self.assertNotIn("old-irrelevant-prefix", text)
        self.assertNotIn("CUDA root cause", json.dumps(result))
        # stop joins the worker after cleanup, avoiding timing-dependent assertions.
        manager.stop()
        self.assertFalse((self.settings.directory / job["id"] / "worker.log").exists())

    def test_restart_marks_queued_and_running_interrupted(self):
        manager = self.manager(); job = self.submit(manager); self.wait(manager, job); manager.stop()
        path = self.settings.directory / job["id"] / "job.json"
        record = json.loads(path.read_text()); record.update(status="running", stage="structure"); path.write_text(json.dumps(record))
        restarted = self.manager(lambda p, progress: self.fail("interrupted jobs must not retry"))
        self.assertEqual(restarted.get("test-owner-a", job["id"])["error"]["code"], "interrupted")

    def test_missing_completed_result_is_failed_on_restart_without_recompute(self):
        manager = self.manager(); job = self.submit(manager); self.wait(manager, job); manager.stop()
        (self.settings.directory / job["id"] / "result.json").unlink()
        restarted = self.manager(lambda p, progress: self.fail("must not recompute"))
        self.assertEqual(restarted.get("test-owner-a", job["id"])["error"]["code"], "result_unavailable")

    def test_expired_terminal_job_removed_and_retention_bounded(self):
        clock = [0]
        manager = self.manager(clock=lambda: clock[0], settings=replace(self.settings, max_jobs=1))
        job = self.submit(manager); self.wait(manager, job)
        with self.assertRaises(JobError): self.submit(manager, key="second")
        clock[0] = 101
        with self.assertRaises(JobError) as error: manager.get("test-owner-a", job["id"])
        self.assertEqual(error.exception.status, 404)
        self.assertFalse((self.settings.directory / job["id"]).exists())
        self.wait(manager, self.submit(manager, key="second"))

    def test_multiple_process_managers_cannot_share_worker_directory(self):
        self.manager()
        with self.assertRaises(RuntimeError): self.manager()

    def test_storage_reservation_refuses_upload_before_writing(self):
        manager = self.manager(settings=replace(self.settings, max_storage_bytes=100))
        with self.assertRaises(JobError) as error: manager.begin_upload("test-owner-a", "storage")
        self.assertEqual(error.exception.status, 507)
        self.assertFalse(any(self.settings.directory.glob("upload-*")))

    def test_chunked_request_limit_and_unauthenticated_preparse_rejection(self):
        manager = self.manager()
        app = FastAPI(); app.state.studio_jobs = manager
        app.include_router(router); app.add_middleware(StudioUploadLimits)
        with TestClient(app) as client:
            headers = {"X-API-Key": "test-owner-a", "Idempotency-Key": "chunked", "Content-Type": "multipart/form-data; boundary=test"}
            def content():
                yield b'--test\r\nContent-Disposition: form-data; name="file"; filename="x.wav"\r\n\r\n'
                for _ in range(3): yield b"x" * 512 * 1024
                yield b"\r\n--test--\r\n"
            self.assertEqual(client.post("/analyze/studio/jobs", headers=headers, content=content()).status_code, 413)
            self.assertEqual(len(manager.uploads), 0)
            self.assertEqual(client.post("/analyze/studio/jobs", headers={"Content-Length": "999999999"}, content=b"").status_code, 401)

    def test_supervisor_kills_child_on_shutdown_timeout_and_storage_limit(self):
        original = subprocess.Popen
        path = self.settings.directory / "input.wav"; path.write_bytes(b"fake")
        processes = []
        def spawn(*args, **kwargs):
            process = original([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
            processes.append(process)
            return process
        for condition, settings, stopping in [
            ("interrupted", self.settings, lambda: True),
            ("analysis_timeout", replace(self.settings, timeout_seconds=0), lambda: False),
            ("analysis_storage_limit", replace(self.settings, max_scratch_bytes=1, max_upload_bytes=1), lambda: False),
        ]:
            with self.subTest(condition=condition), patch("services.studio_jobs.subprocess.Popen", side_effect=spawn):
                with self.assertRaises(JobError) as error: isolated_analysis(path, lambda stage: None, settings, stopping)
                self.assertEqual(error.exception.code, condition)
                self.assertIsNotNone(processes[-1].poll())

    def test_http_auth_post_poll_conflict_and_size_limits(self):
        manager = self.manager()
        app = FastAPI(); app.state.studio_jobs = manager
        app.include_router(router); app.add_middleware(StudioUploadLimits)
        with TestClient(app) as client:
            headers = {"X-API-Key": "test-owner-a", "Idempotency-Key": "request-http"}
            self.assertEqual(client.post("/analyze/studio/jobs", files={"file": ("x.wav", b"fake")}).status_code, 401)
            response = client.post("/analyze/studio/jobs", headers=headers, files={"file": ("x.wav", b"fake")})
            self.assertEqual(response.status_code, 202, response.text)
            job = response.json(); self.wait(manager, job)
            poll = client.get("/analyze/studio/jobs/" + job["id"], headers=headers)
            self.assertEqual(poll.status_code, 200)
            self.assertEqual(poll.json()["result"]["schema_version"], "studio-audio-v1")
            self.assertEqual(client.get("/analyze/studio/jobs/" + job["id"], headers={"X-API-Key": "test-owner-b"}).status_code, 404)
            self.assertEqual(client.post("/analyze/studio/jobs", headers=headers, files={"file": ("x.wav", b"different")}).status_code, 409)
            self.assertEqual(client.post("/analyze/studio/jobs", headers={**headers, "Idempotency-Key": "large"}, files={"file": ("x.wav", b"x" * 1025)}).status_code, 413)
            self.assertEqual(client.post("/analyze/studio/jobs", headers={**headers, "Idempotency-Key": "exe"}, files={"file": ("x.exe", b"fake")}).status_code, 415)
            self.assertEqual(client.post("/analyze/studio/jobs", headers={"X-API-Key": "test-owner-a"}, files={"file": ("x.wav", b"fake")}).status_code, 422)
            self.assertEqual(len(manager.uploads), 0)


if __name__ == "__main__":
    unittest.main()
