# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Essentia Audio Analysis API — a FastAPI server providing audio analysis (rhythm, structure, genre/mood classification, tonal, vocals) using the Essentia library with TensorFlow models. Targets electronic/EDM music. Current version: 4.1.0.

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

Run the lightweight Studio contract/lifecycle suite with
`python -m unittest discover -s tests -p 'test_studio*.py' -v`.
It fakes inference; `verify_setup.py` checks local analysis dependencies separately.

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
- `POST /analyze/studio/jobs` and `GET /analyze/studio/jobs/{id}` — additive durable Studio analysis jobs in this same FastAPI service; see `docs/STUDIO_AUDIO_JOBS.md`
- `GET /health` — Health check (public, no auth)

### Analysis details
- **Rhythm**: RhythmExtractor2013 (multifeature), dual-ODF onset detection (HFC + Complex), high-res RMS energy curve (512 hop size for ~86Hz / 60fps video sync)
- **Structure**: Legacy SBic endpoints use detected MFCC change points and position/energy labels; failure returns422, with no duration-based fallback. Studio jobs use CUDA-only all-in-one functional structure and preserve raw model labels.
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

- **Failure behavior**: SBic structure fails explicitly when usable boundaries are missing. Studio never substitutes heuristic structure or CPU/MPS model inference. Studio storage/startup errors disable only Studio routes (503), preserving legacy API availability. Classification and tonal legacy behavior is unchanged.
- **Temp file cleanup**: Audio uploads written to temp files and deleted immediately after processing.
- **Legacy section labeling heuristic**: First/last-position intro/outro and energy-relative verse/chorus labels are estimates. This heuristic does not apply to the dedicated Studio all-in-one pipeline.
- Python 3.11 required. Docker base image is NVIDIA CUDA 11.8.0 + cuDNN8.

## Deployment

Production runs on **VM100 `app-vm`** (Proxmox homelab), orchestrated via **Dockhand**. Public URL: `https://essentia.v1su4.dev`.

**Infra docs (lookup order):**

1. Hermes notebook vault (Obsidian) — quick map
2. [`proxmox-home`](https://github.com/gordo-v1su4/proxmox-home) — runbooks, endpoints, secret *names*
3. BWS / private files — secret *values*

See [docs/DOCKHAND.md](docs/DOCKHAND.md) and `proxmox-home/docs/app-vm-dockhand-runbook.md` (Essentia section).
