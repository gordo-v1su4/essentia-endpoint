# API Deployment Guide

## Quick Start (Project Root)

### Local Development
```bash
uv venv
uv pip install -r requirements.txt
uvicorn main:app --reload --port 7000
```

### Docker (Recommended for Production)
```bash
docker-compose up -d --build
```

## Environment Variables

Configure these in your `.env` file or directly in your deployment platform (Coolify, etc.):

| Variable | Default / Example | Description |
|----------|-------------------|-------------|
| `CORS_ORIGINS` | `https://v1su4.com` | Comma-separated allowlist of frontend domains. Use `*` to allow all. |
| `API_HOST` | `0.0.0.0` | Binding address (must be `0.0.0.0` for Docker). |
| `API_PORT` | `8000` | Internal container port. External mapping is handled by Coolify or Compose. |
| `EXTERNAL_PORT`| `7000` | The port exposed to your host machine (used in `docker-compose.yml`). |
| `ESSENTIA_MODELS_PATH` | `/app/models` | Internal container path for Essentia models. |

## Coolify Deployment Tips 🚀

1. **Repository**: Point Coolify to your GitHub repo.
2. **Build Context**: Set to `.` (the root directory).
3. **Environment**: Add `CORS_ORIGINS=https://v1su4.com`.
4. **Storage**: Add a persistent volume for `/app/models`.
5. **Port**: Coolify will automatically map its reverse proxy to the container's port `8000`.

## Testing UI
The testing UI is located in the **`app/`** folder. 
- Open [`app/index.html`](app/index.html) in your browser.
- Ensure the `API_BASE` in the script matches your running API's URL.

## Production Checklist

- [x] Pushed to GitHub
- [ ] Set `CORS_ORIGINS` to `https://v1su4.com`
- [ ] Configure volume for `/app/models` in Coolify
- [ ] Test `/health` endpoint after deployment
- [ ] Delete `app/` folder after testing is complete
