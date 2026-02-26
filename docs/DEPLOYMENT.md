# Deployment Guide

## Quick Start

### Docker Compose (recommended)
```bash
docker-compose up -d --build
```
API at `http://localhost:7000`. Models auto-download on first startup.

### Local Development (uv)
```bash
uv venv
uv pip install -r requirements.txt
uv run uvicorn main:app --reload --port 8000
```
API at `http://localhost:8000`.

## Ports

| Mode | URL |
|------|-----|
| Docker Compose | `http://localhost:7000` |
| Local dev (uv) | `http://localhost:8000` |
| Production (Coolify) | `https://your-domain.com` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEYS` | (required) | Comma-separated valid API keys |
| `API_PORT` | `8000` | Container port |
| `EXTERNAL_PORT` | `7000` | Host port (docker-compose) |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `ESSENTIA_MODELS_PATH` | `/app/models` | TensorFlow models directory |
| `TF_CPP_MIN_LOG_LEVEL` | `3` | Suppress TF logs |

## Coolify

1. Connect your GitHub repo in Coolify
2. Build context: `.` (project root)
3. Set environment variables (`API_KEYS`, `CORS_ORIGINS`)
4. Add persistent volume for `/app/models`
5. Deploy — Coolify auto-detects the Dockerfile

See [COOLIFY.md](COOLIFY.md) for details.

## Docker Hub

```bash
./build-push.sh          # Linux/macOS
./build-push.ps1         # Windows
```

Then on server:
```bash
docker pull gordov1su4/essentia-api:latest
docker run -d -p 7000:8000 -v ./models:/app/models \
  -e API_KEYS=your_key \
  -e CORS_ORIGINS=https://yourdomain.com \
  gordov1su4/essentia-api:latest
```

## Verify

```bash
curl http://localhost:7000/health
# {"status":"ok","version":"3.0.2"}
```

## Production Checklist

- [ ] `API_KEYS` set
- [ ] `CORS_ORIGINS` set to frontend domain(s)
- [ ] Persistent volume for `/app/models`
- [ ] `/health` endpoint responding
- [ ] SSL via reverse proxy (Coolify/nginx/traefik)
