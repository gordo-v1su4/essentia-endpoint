"""
Audio Analysis API - Uses Essentia for high-quality modular audio analysis.
Refactored for modularity and enhanced performance.

Run with: uvicorn main:app --reload --port 8000
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
import uvicorn

# Internal imports
from api.models import RhythmAnalysis, StructureAnalysis, FullAnalysis
from services.analysis import (
    load_audio, 
    analyze_rhythm_logic, 
    analyze_structure_logic
)

# Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
# Default to '*' for easiest testing, user can override in Coolify
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]

app = FastAPI(
    title="Audio Analysis API", 
    version="2.0.0",
    description="High-quality music analysis using Essentia C++ core via Python."
)

# CORS configuration
if "*" in CORS_ORIGINS:
    # When using wildcard, we must set allow_credentials=False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Specific origins allow credentials
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.post("/analyze/rhythm", response_model=RhythmAnalysis, tags=["Analysis"])
async def analyze_rhythm(file: UploadFile = File(...)):
    """Extract BPM, beats, confidence, and high-quality onsets."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    
    try:
        audio = load_audio(tmp_path)
        return analyze_rhythm_logic(audio)
    finally:
        if os.path.exists(tmp_path): 
            os.unlink(tmp_path)

@app.post("/analyze/structure", response_model=StructureAnalysis, tags=["Analysis"])
async def analyze_structure(file: UploadFile = File(...)):
    """Segment audio into sections (intro, verse, chorus, etc.) using SBic."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    
    try:
        audio = load_audio(tmp_path)
        return analyze_structure_logic(audio)
    finally:
        if os.path.exists(tmp_path): 
            os.unlink(tmp_path)

@app.post("/analyze/full", response_model=FullAnalysis, tags=["Analysis"])
async def analyze_full(file: UploadFile = File(...)):
    """Perform full rhythm and structural analysis."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    
    try:
        audio = load_audio(tmp_path)
        rhythm = analyze_rhythm_logic(audio)
        structure = analyze_structure_logic(audio)
        
        return {
            **rhythm,
            "structure": structure
        }
    finally:
        if os.path.exists(tmp_path): 
            os.unlink(tmp_path)

@app.get("/health", tags=["System"])
async def health():
    """Check API health status."""
    return {"status": "ok", "version": "2.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host=API_HOST, port=API_PORT)
