"""Authenticated, short HTTP calls around durable background audio analysis."""
import hashlib
import os
from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, Request, Security, UploadFile
from starlette.responses import JSONResponse

from api.auth import verify_api_key
from api.studio_models import StudioJobResponse
from services.studio_jobs import JobError

PATH = "/analyze/studio/jobs"
router = APIRouter(tags=["Studio"])
ALLOWED_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aif", ".aiff", ".webm", ".mp4"}


class StudioUploadLimits:
    """Authenticate/reserve capacity BEFORE multipart spooling, including chunked uploads."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"].rstrip("/") != PATH:
            return await self.app(scope, receive, send)
        manager = scope["app"].state.studio_jobs
        headers = {k.decode("latin1").lower(): v.decode("latin1") for k, v in scope["headers"]}
        token = None
        try:
            owner = await verify_api_key(headers.get("x-api-key"))
            if manager is None:
                raise JobError(503, "unavailable", "Studio analysis worker is unavailable.")
            # Account for bounded multipart framing while enforcing exact file size
            # again in the route. Also enforced for missing/untrusted Content-Length.
            limit = manager.settings.max_upload_bytes + 1024 * 1024
            length = headers.get("content-length")
            if length is not None:
                try:
                    length = int(length)
                except ValueError:
                    raise HTTPException(400, "Invalid Content-Length")
                if length < 0 or length > limit:
                    raise HTTPException(413, "Audio upload exceeds the request size limit")
            token, directory = manager.begin_upload(owner, headers.get("idempotency-key", ""))
            scope.setdefault("state", {})["studio_upload"] = (token, directory)
            received = 0
            async def bounded_receive():
                nonlocal received
                message = await receive()
                if message["type"] == "http.request":
                    received += len(message.get("body", b""))
                    if received > limit:
                        raise HTTPException(413, "Audio upload exceeds the request size limit")
                return message
            await self.app(scope, bounded_receive, send)
        except (JobError, HTTPException) as exc:
            status = exc.status if isinstance(exc, JobError) else exc.status_code
            detail = {"code": exc.code, "message": exc.message} if isinstance(exc, JobError) else exc.detail
            await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
        finally:
            if token:
                manager.abort_upload(token)


@router.post(PATH, response_model=StudioJobResponse, response_model_exclude_none=True, status_code=202)
async def submit_studio_job(request: Request, file: UploadFile = File(...), api_key: str = Security(verify_api_key),
                            idempotency_key: str = Header(..., alias="Idempotency-Key", max_length=200)):
    """Upload once with Idempotency-Key; poll the returned ID without resubmission.

    Jobs and results are isolated by the authenticated API key. Reusing an
    idempotency key with different bytes returns 409. Terminal jobs expire after
    the configured retention period. No failed job runs again automatically.
    """
    manager = request.app.state.studio_jobs
    token, directory = request.state.studio_upload
    suffix = Path(file.filename or "").suffix.lower()
    try:
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(415, "Unsupported audio file extension")
        target = directory / ("input" + suffix)
        digest, size = hashlib.sha256(), 0
        with target.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > manager.settings.max_upload_bytes:
                    raise HTTPException(413, "Audio exceeds the upload size limit")
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        return manager.submit(token, target, digest.hexdigest())
    except JobError as exc:
        raise HTTPException(exc.status, {"code": exc.code, "message": exc.message}) from exc
    finally:
        await file.close()


@router.get(PATH + "/{job_id}", response_model=StudioJobResponse, response_model_exclude_none=True)
async def get_studio_job(job_id: str, request: Request, api_key: str = Security(verify_api_key)):
    """Read queued/running/completed/failed state; only completed jobs contain a result."""
    try:
        if request.app.state.studio_jobs is None:
            raise JobError(503, "unavailable", "Studio analysis worker is unavailable.")
        return request.app.state.studio_jobs.get(api_key, job_id)
    except JobError as exc:
        raise HTTPException(exc.status, {"code": exc.code, "message": exc.message}) from exc
