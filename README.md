# Essentia Audio Analysis API

FastAPI server for comprehensive audio analysis using Essentia. Provides rhythm analysis, structural segmentation, classification (genre/mood/tags), and tonal analysis.

## Documentation

Additional documentation is available in the [`docs/`](docs/) folder:
- [Energy Curve Updates](docs/ENERGY_CURVE_UPDATE.md) - Speed ramping and energy-based features
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [Coolify Setup](docs/COOLIFY.md) - Coolify-specific configuration
- [Models Setup](docs/MODELS_SETUP.md) - TensorFlow models configuration
- [CORS Configuration](docs/CORS_FIX.md) - CORS troubleshooting
- [OpenAPI Schema](docs/openapi.json) - API specification

## Quick Start

### Local Development (uv/uvicorn)

```bash
# Install dependencies (from project root)
uv venv
uv pip install -r requirements.txt

# Run server on port 8000
uvicorn main:app --reload --port 8000
```

### Docker Deployment

#### Build and Run (single container)

```bash
# Build the image (from project root)
docker build -t essentia-api .

# Run the container
docker run -p 8000:8000 -v ./models:/app/models essentia-api
```

#### Using Docker Compose (recommended)

```bash
# From project root
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

## Ports

| Run mode | Host port | Notes |
|----------|-----------|-------|
| **Local dev** (uvicorn) | `8000` | Direct Python run |
| **Docker Compose** | `7000` | Default; set `EXTERNAL_PORT` to change |
| **Production** (Coolify) | 80/443 | Reverse proxy handles it |

The API always runs on port **8000** inside the container. Docker Compose maps `7000` on your host to `8000` in the container by default (avoids conflicts with other services). Use `http://localhost:7000` when running via Docker Compose.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Host to bind the server to |
| `API_PORT` | `8000` | Port inside container |
| `EXTERNAL_PORT` | `7000` | Host port exposed by Docker Compose |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed CORS origins |

## API Documentation

### Interactive Documentation

- **Swagger UI**: `http://localhost:8000/docs` (uv run) or `http://localhost:7000/docs` (Docker Compose) or https://essentia.v1su4.com/docs (production)
- **ReDoc**: `http://localhost:8000/redoc` (uv run) or `http://localhost:7000/redoc` (Docker Compose) or https://essentia.v1su4.com/redoc (production)

### API Endpoints

#### `POST /analyze/rhythm`

Extract BPM, beats, confidence, onsets, and high-resolution energy curve.

**Response:**
```json
{
  "bpm": 120.5,
  "beats": [0.0, 0.5, 1.0, ...],
  "confidence": 0.95,
  "onsets": [0.1, 0.3, 0.6, ...],
  "duration": 180.5,
  "energy": {
    "mean": 0.45,
    "std": 0.12,
    "curve": [0.0, 0.1, 0.3, 0.5, ...]
  }
}
```

#### `POST /analyze/structure`

Segment audio into sections (intro, verse, chorus, etc.) with energy values.

**Response:**
```json
{
  "sections": [
    {
      "start": 0.0,
      "end": 15.2,
      "label": "intro",
      "duration": 15.2,
      "energy": 0.12
    }
  ]
}
```

#### `POST /analyze/classification`

Analyze genre, mood, and tags using Essentia TensorFlow models.

**Response:**
```json
{
  "genre": {"electronic": 0.8, "rock": 0.15, ...},
  "mood": {"energetic": 0.9, "happy": 0.7, ...},
  "tags": {"instrumental": 0.95, "dance": 0.8, ...}
}
```

#### `POST /analyze/full`

Perform complete analysis (rhythm, structure, classification, and tonal).

**Response:** Combined data from all analysis types.

#### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "version": "2.0.0"
}
```

## Deployment to Remote Server

### Option 1: Docker on Remote Server

1. **Copy files to server:**
   ```bash
   scp -r . user@server:/path/to/deploy/essentia-endpoint
   ```

2. **SSH into server:**
   ```bash
   ssh user@server
   cd /path/to/deploy/essentia-endpoint
   ```

3. **Build and run:**
   ```bash
   docker-compose up -d --build
   ```

4. **Update frontend environment:**
   - Set `VITE_ESSENTIA_API_URL=https://essentia.v1su4.com` in your frontend `.env` file

### Option 2: Docker Hub / Container Registry

1. **Build and push** (use `build-push.ps1` on Windows or `build-push.sh` on Mac/Linux):
   ```powershell
   # Windows (default: gordov1su4)
   .\build-push.ps1
   ```
   ```bash
   # Mac/Linux (default: gordov1su4)
   ./build-push.sh
   ```
   Or manually:
   ```bash
   docker build -t gordov1su4/essentia-api:2.0.1 -t gordov1su4/essentia-api:latest .
   docker push gordov1su4/essentia-api:2.0.1
   docker push gordov1su4/essentia-api:latest
   ```

2. **Pull and run on server:**
   ```bash
   docker pull gordov1su4/essentia-api:latest
   docker run -d -p 8000:8000 -v ./models:/app/models \
     -e CORS_ORIGINS=https://yourdomain.com \
     gordov1su4/essentia-api:latest
   ```

### Option 3: Cloud Platform (AWS, GCP, Azure)

- **AWS ECS/Fargate**: Use the Dockerfile with ECS task definitions
- **Google Cloud Run**: Deploy directly from Dockerfile
- **Azure Container Instances**: Use docker-compose or Azure CLI
- **DigitalOcean App Platform**: Connect GitHub repo, auto-deploy on push

## Production Considerations

1. **CORS Configuration**: Set `CORS_ORIGINS` to your actual frontend domain(s)
2. **Reverse Proxy**: Use nginx/traefik for SSL termination and routing
3. **Resource Limits**: Adjust CPU/memory in docker-compose.yml based on load
4. **Health Checks**: Configure your orchestrator to use `/health` endpoint
5. **Logging**: Add structured logging for production monitoring

## Troubleshooting

### Essentia Installation Issues

If Essentia fails to install in Docker, you may need to:
- Use a pre-built Essentia Docker image
- Build Essentia from source in a multi-stage build
- Use a different base image with Essentia pre-installed

### CORS Errors

If you see CORS errors from the frontend:
- Check that `CORS_ORIGINS` includes your frontend URL
- Ensure the API is accessible from the frontend domain
- Verify the API URL in frontend environment variables

### Port Conflicts

- **Local dev (uv)**: Change port in uvicorn: `uvicorn main:app --reload --port 9000`
- **Docker Compose**: Set `EXTERNAL_PORT=9000` in `.env` or `docker-compose.yml`
- Update frontend `VITE_ESSENTIA_API_URL` or `API_BASE` in `app/index.html` accordingly

