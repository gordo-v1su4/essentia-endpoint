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

## Docker Hub Alternative

Instead of building from source in Coolify, you can pull a pre-built image:

```bash
gordov1su4/essentia-api:latest
```

In Coolify, use "Docker Image" deployment and point to the image. This skips the build step entirely.

## Verify

After deployment:

```bash
curl https://your-coolify-domain.com/health
# {"status":"ok","version":"3.0.0"}
```

## Troubleshooting

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
