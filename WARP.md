# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a FastAPI-based audio analysis API that uses Essentia (C++ core via Python bindings) for high-quality music analysis. It provides rhythm detection, structural segmentation, genre/mood classification, and tonal analysis for audio files.

**Key Technology Stack:**
- FastAPI for REST API endpoints
- Essentia (essentia-tensorflow) for audio processing and ML inference
- Python 3.11
- NumPy for numerical operations
- Docker with NVIDIA CUDA support for GPU-accelerated classification

## Common Commands

### Local Development
```bash
# Set up virtual environment (uses uv per user preference)
uv venv
uv pip install -r requirements.txt

# Run development server with hot reload
uvicorn main:app --reload --port 7000

# Verify setup (tests imports and basic rhythm analysis)
python verify_setup.py

# Type checking (Pyright configured in pyrightconfig.json)
pyright .
```

### Docker Commands
```bash
# Build and run with Docker Compose (recommended for production)
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Build image only
docker build -t essentia-api .

# Run container manually
docker run -p 7000:8000 -e CORS_ORIGINS="*" essentia-api
```

### Model Management
```bash
# Download Essentia TensorFlow models (runs automatically in Docker)
./download_models.sh

# Models are stored in ./models/ directory and mounted as volume
# Key models: effnetdiscogs (genre), classification_heads (mood), musicnn (tags)
```

### Testing
```bash
# No formal test suite currently - use verify_setup.py for basic validation
python verify_setup.py

# Manual testing via the included UI
# Open app/index.html in browser (ensure API_BASE matches your running server)
```

## Code Architecture

### Module Structure
```
essentia-endpoint/
├── main.py                 # FastAPI app definition, CORS config, endpoint handlers
├── api/
│   └── models.py          # Pydantic models for request/response schemas
├── services/
│   ├── analysis.py        # Core audio analysis logic (rhythm, structure, classification, tonal)
│   └── labels.py          # Label mappings for genre/tag classification models
└── models/                # Essentia TensorFlow models (downloaded at runtime)
```

### API Endpoints
All endpoints accept audio files via multipart/form-data:

1. **POST /analyze/rhythm** → RhythmAnalysis
   - BPM, beats, confidence, high-quality onsets, energy curve

2. **POST /analyze/structure** → StructureAnalysis
   - Sections (intro/verse/chorus/outro), boundaries using SBic segmentation

3. **POST /analyze/classification** → ClassificationAnalysis
   - Genre (400 Discogs genres), mood (valence/arousal model), tags

4. **POST /analyze/full** → FullAnalysis
   - Combines rhythm + structure + classification + tonal analysis

5. **GET /health** → Health check

### Key Design Patterns

**Audio Processing Pipeline:**
1. Upload received → temporary file created
2. Audio loaded via `es.MonoLoader` (44.1kHz mono)
3. Analysis logic applied (modular per endpoint)
4. Temporary file cleaned up in finally block

**Classification Model Loading:**
- Models loaded from `ESSENTIA_MODELS_PATH` (default: `/app/models`)
- Falls back gracefully if models missing (returns "Unknown" or "Unavailable")
- Audio resampled to 16kHz for classification models
- Uses specialized TensorFlow wrappers (TensorflowPredictEffNetDiscogs, TensorflowPredictMusiCNN)

**Energy Curve Generation:**
- Frame size: 1024, hop size: 512 (11.6ms resolution at 44.1kHz, ~86Hz)
- RMS calculated per frame, normalized to 0-1 range
- Designed for video synchronization at 60fps

**Structural Segmentation:**
- MFCC features extracted from audio
- SBic algorithm detects segment boundaries
- Heuristic labeling based on position and energy (intro/outro at edges, chorus=high energy, verse=lower energy)

## Environment Configuration

### Required Environment Variables
- `API_HOST`: Binding address (default: `0.0.0.0`)
- `API_PORT`: Internal port (default: `8000`)
- `CORS_ORIGINS`: Comma-separated allowed origins (default: `*`)
- `EXTERNAL_PORT`: Host-exposed port in docker-compose (default: `7000`)
- `ESSENTIA_MODELS_PATH`: Models directory (default: `/app/models`)

### CORS Handling
- Currently set to allow all origins (`allow_origins=["*"]`)
- For production, update main.py:40 to use `CORS_ORIGINS` env var
- Note: `allow_credentials=True` with `*` origin may be ignored by browsers

## Deployment

### Coolify Deployment (Recommended)
See COOLIFY.md for detailed instructions. Key points:
- Use GitHub repository deployment for auto-updates
- Set build context to repository root (`.`)
- Dockerfile auto-detected
- Configure persistent volume for `/app/models` (models downloaded on first run via entrypoint.sh)
- Always use .yaml extension for Coolify configs (not .yml)

### Docker Considerations
- Base image: nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 (GPU support)
- Python 3.11 installed via apt
- Uses `uv` for fast package installation
- entrypoint.sh auto-downloads models if missing on container start
- Health check configured: `/health` endpoint every 30s

### Resource Limits
Configured in docker-compose.yml:
- CPU: 1-4 cores
- Memory: 2-8GB
- GPU: 1 NVIDIA GPU (optional but recommended for classification)

## Development Guidelines

### Adding New Analysis Features
1. Add new Pydantic model in `api/models.py`
2. Implement analysis logic function in `services/analysis.py` (follows `analyze_*_logic` pattern)
3. Add endpoint in `main.py` (follows `/analyze/*` pattern with tempfile handling)
4. Update FullAnalysis model and endpoint if applicable

### Working with Essentia
- Always use `essentia.standard` module (streaming mode not used)
- Check algorithm availability with `hasattr(es, 'AlgorithmName')`
- Essentia algorithms return numpy arrays or tuples - convert to float/list for JSON serialization
- Sample rate: 44.1kHz for rhythm/structure, 16kHz for classification models

### Model Dependencies
- Classification features require TensorFlow models downloaded to `models/` directory
- Models from https://github.com/MTG/essentia-models
- Key models: effnetdiscogs-bs64-1.pb, msd-musicnn-1.pb, emomusic-msd-musicnn-1.pb
- Label mappings in `services/labels.py` (GENRE_LABELS, TAG_LABELS)

### Python Virtual Environment
User prefers `uv` for virtual environment management (not pip/venv directly).

## Known Limitations

- No formal test suite (only verify_setup.py for smoke tests)
- Heuristic structural labeling (intro/verse/chorus) is basic - not ML-based
- Classification models optional but recommended for full functionality
- CORS currently allows all origins in code (should be env-var controlled for production)
- No authentication/rate limiting implemented
- Duplicate code in main.py (lines 80-81 repeat os.unlink)

## Related Documentation

- README.md: Quick start and API endpoint documentation
- COOLIFY.md: Detailed Coolify deployment guide with GitHub integration
- DEPLOYMENT.md: Environment variables and deployment checklist
- MODELS_SETUP.md: Model download instructions and EDM-specific recommendations
- CORS_FIX.md: CORS troubleshooting guide
- DOCKER_MODELS.md: Docker model handling details
- ENERGY_CURVE_UPDATE.md: Energy curve implementation notes
