"""
Audio Analysis API - Uses Essentia for high-quality modular audio analysis.
Refactored for modularity and enhanced performance.

Run with: uv run uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, Security, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import tempfile
import uvicorn
import os

# Internal imports
from api.models import (
    RhythmAnalysis, StructureAnalysis, EnhancedTonalAnalysis,
    FullAnalysis, ClassificationAnalysis, VocalAnalysis,
)
from api.auth import verify_api_key
from services.analysis import (
    load_audio,
    analyze_rhythm_logic,
    analyze_structure_logic,
    analyze_classification_logic,
    analyze_tonal_logic,
    analyze_vocals_logic,
    ALL_CLASSIFICATION_FEATURES,
)

# Configuration
API_VERSION = "3.0.0"
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
# Default to '*' for easiest testing, user can override in Coolify
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS") or os.getenv("CORS_ORIGIN") or "*"
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]

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

if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=API_PORT)
