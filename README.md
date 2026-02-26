# Essentia Audio Analysis API

FastAPI server for comprehensive audio analysis using Essentia. Provides rhythm analysis, structural segmentation, classification (genre/mood/tags + selectable features), vocal detection, and enhanced tonal analysis with deep-learning tempo and pitch.

**Version:** 3.0.2

## Quick Start

### Docker (recommended)

```bash
docker-compose up -d --build
```

API at **http://localhost:7000**. Models auto-download on first startup from `essentia.upf.edu`.

```bash
docker-compose logs -f   # View logs
docker-compose down      # Stop
```

### Local Development (uv)

```bash
uv venv
uv pip install -r requirements.txt
uv run uvicorn main:app --reload --port 8000
```

API at **http://localhost:8000**.

## Authentication

All analysis endpoints require an API key via the `X-API-Key` header.

```bash
curl -X POST "https://essentia.v1su4.dev/analyze/rhythm" \
  -H "X-API-Key: your_api_key_here" \
  -F "file=@audio.mp3"
```

## API Endpoints

### `POST /analyze/rhythm`

BPM, beats, onsets, and high-resolution energy curve.

```json
{
  "bpm": 128.0,
  "beats": [0.0, 0.469, 0.938],
  "confidence": 0.95,
  "onsets": [0.1, 0.3, 0.6],
  "duration": 180.5,
  "energy": {
    "mean": 0.45,
    "std": 0.12,
    "curve": [0.0, 0.1, 0.3, 0.5]
  }
}
```

### `POST /analyze/structure`

Section boundaries with labels (intro, verse, chorus, bridge, outro).

```json
{
  "sections": [
    {"start": 0.0, "end": 15.2, "label": "intro", "duration": 15.2, "energy": 0.12},
    {"start": 15.2, "end": 62.8, "label": "verse", "duration": 47.6, "energy": 0.34}
  ],
  "boundaries": [0.0, 15.2, 62.8, 180.5]
}
```

### `POST /analyze/classification`

Genre, mood, tags, and selectable classification features.

**Query parameter:** `?features=genre,mood,danceability` (comma-separated, default: all)

**Available features:** `genre`, `mood`, `tags`, `danceability`, `approachability`, `engagement`, `acoustic_electronic`, `bright_dark`, `instrument`, `tonal_atonal`

```json
{
  "genres": {"label": "Electronic---Tech House", "confidence": 0.82, "all_scores": {}},
  "moods": {"label": "Happy", "confidence": 1.0, "all_scores": {"valence": 6.2, "arousal": 5.8}},
  "tags": ["electronic", "dance", "House"],
  "danceability": {"label": "Danceable", "confidence": 0.91},
  "approachability": {"label": "Approachable", "confidence": 0.73},
  "engagement": {"label": "Engaging", "confidence": 0.68},
  "acoustic_electronic": {"label": "Electronic", "confidence": 0.95},
  "bright_dark": {"label": "Bright", "confidence": 0.77},
  "instrument": [
    {"label": "synthesizer", "confidence": 0.88},
    {"label": "drums", "confidence": 0.72}
  ],
  "tonal_atonal": {"label": "Tonal", "confidence": 0.85}
}
```

### `POST /analyze/tonal`

Key, scale, deep-learning tempo (TempoCNN), and pitch detection (CREPE).

```json
{
  "key": "A",
  "scale": "minor",
  "strength": 0.72,
  "tempo_cnn": 127.5,
  "pitch": {"mean_frequency": 440.0, "confidence": 0.85}
}
```

### `POST /analyze/vocals`

Voice/instrumental detection with continuous 0-1 score.

```json
{
  "vocal_presence": 0.82,
  "label": "Voice"
}

```

`vocal_presence`: 0.0 = instrumental, 1.0 = vocals.

### `POST /analyze/full`

All of the above combined in a single response.

### `GET /health`

```json
{"status": "ok", "version": "3.0.2"}
```

### Protected vs Public

| Protected (API key required) | Public |
|-----|--------|
| `POST /analyze/rhythm` | `GET /health` |
| `POST /analyze/structure` | `GET /docs` (Swagger UI) |
| `POST /analyze/classification` | `GET /redoc` |
| `POST /analyze/tonal` | |
| `POST /analyze/vocals` | |
| `POST /analyze/full` | |

## TensorFlow Models

Models auto-download on first startup from `essentia.upf.edu/models/`. Stored in `/app/models` (Docker volume).

| Model | Wrapper | Purpose |
|-------|---------|---------|
| Discogs EffNet | `TensorflowPredictEffnetDiscogs` | Genre classification (400 labels) + embeddings |
| MusiCNN | `TensorflowPredictMusiCNN` | Auto-tagging (50 labels) + embeddings |
| Classification heads (9) | `TensorflowPredict2D` | Danceability, mood, vocals, etc. |
| TempoCNN | `TensorflowPredictTempoCNN` | Deep-learning tempo estimation |
| CREPE | `TensorflowPredictCREPE` | Pitch detection |

To force model re-download, delete the models volume and restart:

```bash
docker-compose down -v
docker-compose up -d --build
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEYS` | (required) | Comma-separated valid API keys |
| `API_PORT` | `8000` | Container port |
| `EXTERNAL_PORT` | `7000` | Host port (docker-compose) |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `ESSENTIA_MODELS_PATH` | `/app/models` | TensorFlow models directory |
| `TF_CPP_MIN_LOG_LEVEL` | `3` | Suppress TF logs |

## Architecture

```
main.py                  FastAPI app, endpoint definitions, CORS setup
api/auth.py              API key auth (X-API-Key header)
api/models.py            Pydantic response models
services/analysis.py     Core analysis (rhythm, structure, classification, tonal, vocals)
services/labels.py       Genre (400), tag (50), and instrument (40) label mappings
download_models.py       Downloads models from essentia.upf.edu
entrypoint.sh            Auto-downloads models on first run, starts uvicorn
docs/openapi.json        OpenAPI 3.1 schema
```

## Deployment

### Docker Hub

**Manual build and push:**
```bash
./build-push.sh          # Linux/macOS
./build-push.ps1         # Windows
```

**GitHub Actions (automatic):** Pushes to `gordov1su4/essentia-api` on every push to `main`. Add these secrets in GitHub repo settings:

| Secret | Description |
|--------|-------------|
| `DOCKERHUB_USERNAME` | Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token |

Workflow: [`.github/workflows/docker-build-push.yml`](.github/workflows/docker-build-push.yml)

### Cloud platforms

Works with AWS ECS/Fargate, Google Cloud Run, Azure Container Instances, DigitalOcean App Platform, or Coolify.

## Documentation

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI schema**: [`docs/openapi.json`](docs/openapi.json)
- Additional docs in [`docs/`](docs/)
