# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Essentia Audio Analysis API — a FastAPI server providing audio analysis (rhythm, structure, genre/mood classification, tonal, vocals) using the Essentia library with TensorFlow models. Targets electronic/EDM music. Current version: 3.0.1.

## Build & Run Commands

### Local development (uv)
```bash
uv venv
uv pip install -r requirements.txt
uv run uvicorn main:app --reload --port 8000
```

### Docker
```bash
docker-compose up -d --build          # Runs on host port 7000 → container 8000
docker build -t essentia-api .        # Standalone build
```

### Push to Docker Hub
```bash
./build-push.sh                       # Linux/macOS
./build-push.ps1                      # Windows
```

### Verify setup
```bash
python verify_setup.py                # Tests imports and basic rhythm analysis
```

There is no test suite — `verify_setup.py` is the only automated check.

## Architecture

```
main.py                  FastAPI app, endpoint definitions, CORS setup
├── api/auth.py          API key auth (X-API-Key header, loaded from API_KEYS env)
├── api/models.py        Pydantic response models (RhythmAnalysis, StructureAnalysis, etc.)
├── services/analysis.py Core analysis algorithms (rhythm, structure, classification, tonal, vocals)
└── services/labels.py   Genre (400 Discogs labels), tag (50 MusiCNN), and instrument (40 Jamendo) mappings
```

### Request flow
1. Client sends audio file + `X-API-Key` header to `POST /analyze/{type}`
2. `api/auth.py` validates key via constant-time comparison
3. Audio loaded as mono 44.1kHz via Essentia's MonoLoader
4. Analysis functions in `services/analysis.py` process audio
5. Response returned using Pydantic models from `api/models.py`

### Endpoints
- `POST /analyze/rhythm` — BPM, beats, onsets, energy curve
- `POST /analyze/structure` — Section boundaries with labels (intro/verse/chorus/bridge/outro)
- `POST /analyze/classification` — Genre, mood, tags + selectable features via `?features=` query param (danceability, approachability, engagement, acoustic_electronic, bright_dark, instrument, tonal_atonal)
- `POST /analyze/tonal` — Key, scale, strength + TempoCNN tempo + CREPE pitch
- `POST /analyze/vocals` — Voice/instrumental detection with confidence
- `POST /analyze/full` — All of the above combined
- `GET /health` — Health check (public, no auth)

### Analysis details
- **Rhythm**: RhythmExtractor2013 (multifeature), dual-ODF onset detection (HFC + Complex), high-res RMS energy curve (512 hop size for ~86Hz / 60fps video sync)
- **Structure**: MFCC-based segmentation via SBic with heuristic fallback; section labels assigned by position + energy relative to mean
- **Classification**: TensorFlow models resampled to 16kHz — EffNetDiscogs (genres + embeddings for classification heads), EmoMusic (mood), MusiCNN (tags). Selectable features: genre, mood, tags, danceability, approachability, engagement, acoustic_electronic, bright_dark, instrument, tonal_atonal.
- **Vocals**: EffNet embeddings + voice_instrumental classification head
- **Tonal**: Essentia KeyExtractor + TempoCNN (deep learning tempo at 11025Hz) + CREPE (pitch detection at 16kHz)

### TensorFlow models
Located in `models/` directory (Docker volume mount). Auto-downloaded on first container startup via `entrypoint.sh` from `https://github.com/MTG/essentia-models.git`. Model sets: `effnetdiscogs/`, `classification_heads/`, `musicnn/`, `tempocnn/`, `crepe/`.

## Key Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `API_KEYS` | (required) | Comma-separated valid API keys |
| `API_PORT` | `8000` | Container port |
| `EXTERNAL_PORT` | `7000` | Host port (docker-compose) |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `ESSENTIA_MODELS_PATH` | `/app/models` | TensorFlow models directory |
| `TF_CPP_MIN_LOG_LEVEL` | `3` | Suppress TF logs |

## Important Patterns

- **Graceful degradation**: Structure analysis falls back to heuristic if SBic fails; classification handles missing TF models; tonal returns "Unknown" on failure.
- **Temp file cleanup**: Audio uploads written to temp files and deleted immediately after processing.
- **Section labeling heuristic**: intro (0-15% position), outro (80%+), chorus (>110% mean energy), verse (<110%), bridge (50-75% with different energy).
- Python 3.11 required. Docker base image is NVIDIA CUDA 11.8.0 + cuDNN8.
