# API Deployment Guide

## Quick Start (Project Root)

### Local Development (uv/uvicorn)
```bash
uv venv
uv pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
API available at `http://localhost:8000`.

### Docker (Recommended for Production)
```bash
docker-compose up -d --build
```
API available at `http://localhost:7000` (host port 7000 → container port 8000).

## Ports

| Mode | URL |
|------|-----|
| Local dev (uv) | `http://localhost:8000` |
| Docker Compose | `http://localhost:7000` |
| Production (Coolify) | `https://your-domain.com` |

## Environment Variables

Configure these in your `.env` file or directly in your deployment platform (Coolify, etc.):

| Variable | Default / Example | Description |
|----------|-------------------|-------------|
| `CORS_ORIGINS` | `https://v1su4.com` | Comma-separated allowlist of frontend domains. Use `*` to allow all. |
| `API_HOST` | `0.0.0.0` | Binding address (must be `0.0.0.0` for Docker). |
| `API_PORT` | `8000` | Internal container port. |
| `EXTERNAL_PORT` | `7000` | Host port exposed by Docker Compose. Set to `8000` to match local dev. |
| `ESSENTIA_MODELS_PATH` | `/app/models` | Internal container path for Essentia models. |

## Coolify Deployment Tips 🚀

1. **Repository**: Point Coolify to your GitHub repo.
2. **Build Context**: Set to `.` (the root directory).
3. **Environment**: Add `CORS_ORIGINS=https://v1su4.com`.
4. **Storage**: Add a persistent volume for `/app/models`.
5. **Port**: Coolify will automatically map its reverse proxy to the container's port `8000`.

## Testing UI
The testing UI is located in the **`app/`** folder. 
- Open [`app/index.html`](app/index.html) in your browser (or serve via `python -m http.server`).
- Ensure `API_BASE` in the script matches your API: `http://localhost:8000` (uv) or `http://localhost:7000` (Docker).

## Production Checklist

- [x] Pushed to GitHub
- [ ] Set `CORS_ORIGINS` to `https://v1su4.com`
- [ ] Configure volume for `/app/models` in Coolify
- [ ] Test `/health` endpoint after deployment
- [ ] Delete `app/` folder after testing is complete
