# Coolify Deployment Guide

Deploy the Essentia Audio Analysis API on [Coolify](https://coolify.io/).

## GitHub Repository (Recommended)

1. **Connect your repo** in Coolify — select "Public Repository" or "Private Repository (with GitHub App)"
2. **Build context**: `.` (project root)
3. **Dockerfile path**: `Dockerfile`
4. Coolify auto-detects the Dockerfile and builds the image

### Environment Variables

Set these in the Coolify dashboard under "Environment":

| Variable | Value | Notes |
|----------|-------|-------|
| `API_KEYS` | `your_key_1,your_key_2` | **Required** — comma-separated API keys |
| `CORS_ORIGINS` | `https://yourdomain.com` | Frontend domain(s), comma-separated |
| `API_PORT` | `8000` | Internal container port |

### Persistent Volume

Add a volume mount for TensorFlow models so they persist across deploys:

- **Container path**: `/app/models`
- **Host path or named volume**: your choice

Models auto-download on first startup (~130MB). Without a persistent volume, they re-download on every deploy.

### Health Check

Coolify uses the `HEALTHCHECK` in the Dockerfile:
- **Endpoint**: `/health`
- **Interval**: 30s
- **Start period**: 120s (models need time to load)
- **Retries**: 3

### Reverse Proxy

Coolify's Traefik reverse proxy automatically:
- Handles SSL via Let's Encrypt
- Maps your domain to the container
- Routes traffic to port 8000 inside the container

You don't need to expose port 8000 publicly.

## Branch Deployments

You can create separate Coolify resources for different branches:
- `main` → Production
- `develop` → Staging

Each branch deployment can have its own environment variables and domain.

## Docker Hub Alternative (Pre-built Image)

To pull a pre-built image instead of building (faster deploy, but requires a successful pull):

Set `ESSENTIA_IMAGE=gordov1su4/essentia-api:latest` (or `:4.0.0`) in Coolify environment variables.

**Note:** If you see `archive/tar: invalid tar header` or `failed to copy: EOF` when pulling, switch to build-from-source by unsetting `ESSENTIA_IMAGE`.

## Verify

After deployment:

```bash
curl https://your-coolify-domain.com/health
# {"status":"ok","version":"3.0.1"}
```

## Troubleshooting

**`archive/tar: invalid tar header` or `failed to copy: failed to send write: EOF`**: These indicate a corrupted image pull. **Fix: Build from source instead of pulling.** Unset `ESSENTIA_IMAGE` in Coolify environment variables (or remove it). The default `essentia-api:local` triggers a local build from the Dockerfile, avoiding the registry pull. First deploy will take 10–20 minutes to build.

**Build fails**: Essentia build takes 10-20 minutes and ~2GB disk. Check Coolify build logs. Enable Docker layer caching to speed up rebuilds.

**Models not found**: Ensure the persistent volume is mounted at `/app/models`. Check logs for download errors.

**CORS errors**: Verify `CORS_ORIGINS` includes your frontend domain exactly (including `https://`).

**Health check fails**: The container needs ~60-120s to start (model loading). Check Coolify logs for startup errors.

## Checklist

- [ ] Repository connected
- [ ] `API_KEYS` set
- [ ] `CORS_ORIGINS` set to frontend domain(s)
- [ ] Persistent volume for `/app/models`
- [ ] Domain assigned
- [ ] Health check passing
- [ ] Frontend `.env` updated with API URL
