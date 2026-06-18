# Portainer Deployment Guide

This Essentia API is deployed on the home-server Docker/Portainer lane.

## Production shape

- **App/container**: `essentia-api`
- **Internal app port**: `8000`
- **Host port**: `18000`
- **Public URL**: `https://essentia.v1su4.dev`
- **Tailscale/internal URL**: `http://100.121.236.75:18000`
- **Models volume**: `essentia-models` mounted at `/app/models`
- **GPU**: NVIDIA GPU exposed with Docker `gpus: all`

Use the internal Tailscale URL for server-to-server uploads from sibling apps so large audio files avoid public proxy limits.

## Environment variables

Set these in the Portainer stack/service environment. Do not commit secret values.

| Variable | Required | Notes |
|----------|----------|-------|
| `API_KEYS` | yes | Comma-separated API keys accepted by `X-API-Key` or `Authorization: Bearer ...` |
| `CORS_ORIGINS` | yes | Public browser origins, normally `https://essentia.v1su4.dev` |
| `METRICS_TOKEN` | optional | Bearer token for `/internal/metrics` if Prometheus/Grafana scrape it |
| `ESSENTIA_MODELS_PATH` | yes | Usually `/app/models` |
| `NVIDIA_VISIBLE_DEVICES` | yes | Usually `all` |
| `NVIDIA_DRIVER_CAPABILITIES` | yes | Usually `compute,utility` |
| `TONAL_CREPE_MODEL` | optional | `auto` by default |
| `TONAL_PITCH_MAX_SECONDS` | optional | Limits slower pitch analysis |
| `TONAL_TEMPO_MAX_SECONDS` | optional | Limits slower TempoCNN analysis |

## Persistent model volume

Keep `/app/models` on a Docker volume so TensorFlow models persist across container restarts/redeploys. Without this volume, models will be re-downloaded.

## Health checks

```bash
curl https://essentia.v1su4.dev/health
curl http://100.121.236.75:18000/health
```

Expected response:

```json
{"status":"ok","version":"4.0.2"}
```

## Useful runtime checks

```bash
# From a machine on Tailnet
tailscale ssh gordo@portainer 'docker ps --filter name=essentia-api'
tailscale ssh gordo@portainer 'docker logs --tail 120 essentia-api'
```

## API paths used by Stack Structure

- `/analyze/fast` — blocking first-pass path for Stack Structure uploads. Returns rhythm, energy, and structure only.
- `/analyze/full` — deeper enrichment path. Returns rhythm, structure, classification, tonal, and vocals.
- `/docs` — Swagger UI.
- `/health` — public health check.
- `/internal/metrics` — optional Prometheus endpoint, requires `METRICS_TOKEN`.

## Troubleshooting

- **Large upload fails through public URL**: use `http://100.121.236.75:18000` from server-side apps instead of the public Cloudflare/proxy path.
- **Classifier head shape mismatch**: verify EffNet `PartitionedCall:0` is used for 400-class genre activations and `PartitionedCall:1` is used for 1280-wide embeddings.
- **Models reload every request**: verify `services/analysis.py` uses the process-level model cache.
- **No boundaries found**: this is not fatal. The service falls back to estimated song sections such as intro/verse/chorus/bridge/outro.
