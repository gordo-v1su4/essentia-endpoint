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
| Production (Portainer) | `https://essentia.v1su4.dev` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEYS` | (required) | Comma-separated valid API keys |
| `METRICS_TOKEN` | unset | Bearer token for internal Prometheus scraping |
| `API_PORT` | `8000` | Container port |
| `EXTERNAL_PORT` | `7000` | Host port (docker-compose) |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `ESSENTIA_MODELS_PATH` | `/app/models` | TensorFlow models directory |
| `TF_CPP_MIN_LOG_LEVEL` | `3` | Suppress TF logs |

## Portainer / home server

1. Manage the service from Portainer on the home-server Docker lane.
2. Use the stack/service environment for `API_KEYS`, `CORS_ORIGINS`, and optional `METRICS_TOKEN`.
3. Keep the `essentia-models` Docker volume mounted at `/app/models`.
4. Expose container port `8000` on host port `18000`.
5. Use `https://essentia.v1su4.dev` for public docs/health and `http://100.121.236.75:18000` for internal server-to-server uploads.

See [PORTAINER.md](PORTAINER.md) for details.

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
  -e METRICS_TOKEN=your_internal_metrics_token \
  -e CORS_ORIGINS=https://yourdomain.com \
  gordov1su4/essentia-api:latest
```

## Verify

```bash
curl http://localhost:7000/health
# {"status":"ok","version":"3.0.1"}
```

## Production Checklist

- [ ] `API_KEYS` set
- [ ] `METRICS_TOKEN` set if Prometheus will scrape `/internal/metrics`
- [ ] `CORS_ORIGINS` set to frontend domain(s)
- [ ] Persistent volume for `/app/models`
- [ ] `/health` endpoint responding
- [ ] SSL via reverse proxy/Tailscale/Portainer host routing
