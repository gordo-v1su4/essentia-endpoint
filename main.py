"""
Audio Analysis API - Uses Essentia for high-quality modular audio analysis.
Refactored for modularity and enhanced performance.

Run with: uv run uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, Security, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import tempfile
import uvicorn
import os
import secrets
import time

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
except ModuleNotFoundError:
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    generate_latest = None

    class _NoopMetric:
        def labels(self, **_kwargs):
            return self

        def inc(self):
            return None

        def dec(self):
            return None

        def observe(self, _value):
            return None

    class Counter(_NoopMetric):
        def __init__(self, *_args, **_kwargs):
            pass

    class Gauge(_NoopMetric):
        def __init__(self, *_args, **_kwargs):
            pass

    class Histogram(_NoopMetric):
        def __init__(self, *_args, **_kwargs):
            pass

# Internal imports
from api.models import (
    RhythmAnalysis, StructureAnalysis, EnhancedTonalAnalysis,
    FullAnalysis, ClassificationAnalysis, VocalAnalysis,
    TonalAnalysis, TempoAnalysis, PitchAnalysis, FastAnalysis,
)
from api.auth import verify_api_key
from services.analysis import (
    load_audio,
    analyze_rhythm_logic,
    analyze_structure_logic,
    analyze_classification_logic,
    analyze_tonal_logic,
    analyze_tonal_key_logic,
    analyze_tonal_tempo_logic,
    analyze_tonal_pitch_logic,
    analyze_vocals_logic,
    ALL_CLASSIFICATION_FEATURES,
)

# Configuration
API_VERSION = "4.0.2"
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "").strip()
# Default to '*' for easiest testing, user can override in Coolify
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS") or os.getenv("CORS_ORIGIN") or "*"
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]

REQUEST_COUNT = Counter(
    "essentia_http_requests_total",
    "Total HTTP requests handled by the Essentia API.",
    ["handler", "method", "status"],
)
REQUEST_LATENCY = Histogram(
    "essentia_http_request_duration_seconds",
    "Request latency for the Essentia API.",
    ["handler", "method"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)
REQUESTS_IN_PROGRESS = Gauge(
    "essentia_http_requests_in_progress",
    "In-flight Essentia API requests.",
    ["handler", "method"],
)
SKIP_METRICS_PATHS = frozenset(("/internal/metrics",))

app = FastAPI(
    title="Audio Analysis API",
    version=API_VERSION,
    description="High-quality music analysis using Essentia C++ core via Python."
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _verify_metrics_token(request: Request) -> None:
    if not METRICS_TOKEN:
        raise HTTPException(status_code=404, detail="Not found")

    authorization = request.headers.get("authorization", "")
    expected = f"Bearer {METRICS_TOKEN}"
    if not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.middleware("http")
async def instrument_requests(request: Request, call_next):
    handler = request.url.path or "/"
    method = request.method

    if handler in SKIP_METRICS_PATHS:
        return await call_next(request)

    start = time.perf_counter()
    status_code = "500"
    REQUESTS_IN_PROGRESS.labels(handler=handler, method=method).inc()

    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        duration = time.perf_counter() - start
        REQUEST_LATENCY.labels(handler=handler, method=method).observe(duration)
        REQUEST_COUNT.labels(handler=handler, method=method, status=status_code).inc()
        REQUESTS_IN_PROGRESS.labels(handler=handler, method=method).dec()


@app.post("/analyze/rhythm", response_model=RhythmAnalysis, tags=["Analysis"])
async def analyze_rhythm(
    file: UploadFile = File(...),
    api_key: str = Security(verify_api_key)
):
    """Extract BPM, beats, confidence, and high-quality onsets."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        return analyze_rhythm_logic(audio)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@app.post("/analyze/structure", response_model=StructureAnalysis, tags=["Analysis"])
async def analyze_structure(
    file: UploadFile = File(...),
    api_key: str = Security(verify_api_key)
):
    """Segment audio into sections (intro, verse, chorus, etc.) using SBic."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        return analyze_structure_logic(audio)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@app.post("/analyze/classification", response_model=ClassificationAnalysis, tags=["Analysis"])
async def analyze_classification(
    file: UploadFile = File(...),
    features: Optional[str] = Query(
        default=None,
        description="Comma-separated list of features to analyze. "
                    "Available: genre, mood, tags, danceability, approachability, engagement, "
                    "acoustic_electronic, bright_dark, instrument, tonal_atonal. Default: all."
    ),
    api_key: str = Security(verify_api_key)
):
    """Analyze Genre, Mood, Tags, and additional classification features using Essentia TensorFlow models."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        feature_set = None
        if features:
            feature_set = {f.strip() for f in features.split(",") if f.strip()}
            invalid = feature_set - ALL_CLASSIFICATION_FEATURES
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid features: {', '.join(sorted(invalid))}. "
                           f"Available: {', '.join(sorted(ALL_CLASSIFICATION_FEATURES))}"
                )
        return analyze_classification_logic(audio, features=feature_set)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@app.post("/analyze/tonal", response_model=EnhancedTonalAnalysis, tags=["Analysis"])
async def analyze_tonal(
    file: UploadFile = File(...),
    api_key: str = Security(verify_api_key)
):
    """Extract key, scale, deep-learning tempo (TempoCNN), and pitch (CREPE)."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        return analyze_tonal_logic(audio)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/analyze/tonal/key", response_model=TonalAnalysis, tags=["Analysis"])
async def analyze_tonal_key(
    file: UploadFile = File(...),
    api_key: str = Security(verify_api_key)
):
    """Extract key, scale, and key strength only."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        return analyze_tonal_key_logic(audio)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/analyze/tonal/tempo", response_model=TempoAnalysis, tags=["Analysis"])
async def analyze_tonal_tempo(
    file: UploadFile = File(...),
    api_key: str = Security(verify_api_key)
):
    """Extract deep-learning tempo only (TempoCNN)."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        return analyze_tonal_tempo_logic(audio)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/analyze/tonal/pitch", response_model=PitchAnalysis, tags=["Analysis"])
async def analyze_tonal_pitch(
    file: UploadFile = File(...),
    api_key: str = Security(verify_api_key)
):
    """Extract pitch only (CREPE)."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        return analyze_tonal_pitch_logic(audio)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@app.post("/analyze/vocals", response_model=VocalAnalysis, tags=["Analysis"])
async def analyze_vocals(
    file: UploadFile = File(...),
    api_key: str = Security(verify_api_key)
):
    """Detect whether audio contains vocals or is instrumental."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        return analyze_vocals_logic(audio)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@app.post("/analyze/fast", response_model=FastAnalysis, tags=["Analysis"])
async def analyze_fast(
    file: UploadFile = File(...),
    api_key: str = Security(verify_api_key)
):
    """Fast first-pass analysis for interactive editing.

    Returns only rhythm, energy, and song structure. This is enough to build
    beat/section previews without waking classifier, tonal, pitch, or vocal
    TensorFlow models on the blocking upload path.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        rhythm = analyze_rhythm_logic(audio)
        structure = analyze_structure_logic(audio)

        return {
            **rhythm,
            "structure": structure,
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@app.post("/analyze/full", response_model=FullAnalysis, tags=["Analysis"])
async def analyze_full(
    file: UploadFile = File(...),
    api_key: str = Security(verify_api_key)
):
    """Perform full rhythm, structural, classification, tonal, and vocal analysis."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        audio = load_audio(tmp_path)
        rhythm = analyze_rhythm_logic(audio)
        structure = analyze_structure_logic(audio)
        classification = analyze_classification_logic(audio)
        tonal = analyze_tonal_logic(audio)
        vocals = analyze_vocals_logic(audio)

        return {
            **rhythm,
            "structure": structure,
            "classification": classification,
            "tonal": tonal,
            "vocals": vocals,
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@app.get("/health", tags=["System"])
async def health():
    """Check API health status."""
    return {"status": "ok", "version": API_VERSION}


@app.get("/internal/metrics", include_in_schema=False, tags=["System"])
async def internal_metrics(request: Request):
    """Expose Prometheus metrics for internal scraping only."""
    _verify_metrics_token(request)
    if generate_latest is None:
        raise HTTPException(status_code=503, detail="Prometheus metrics dependency is not installed")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=API_PORT)
