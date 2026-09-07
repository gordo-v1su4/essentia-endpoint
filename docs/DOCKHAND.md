# Dockhand deployment guide

The Essentia API runs on **VM100 `app-vm`** (Proxmox homelab), managed via **Dockhand**, exposed publicly as `https://essentia.v1su4.dev`. Beatsmaxxer and sibling apps call that **hosted** URL — they do not run Essentia on the laptop or in the browser.

## Where to look (documentation chain)

Agents and operators should follow this order (see also `proxmox-home/docs/operator-source-of-truth.md`):

1. **Hermes notebook vault** (`hermes-notebook-vault` Obsidian) — fast network map; points into the repo below.
2. **`proxmox-home` repo** — canonical homelab topology, runbooks, endpoint index, BWS secret *names* (not values).
3. **Bitwarden Secrets Manager** / gitignored private files — actual credentials (`ESSENTIA_API_KEY`, etc.).
4. **Live host** — Dockhand, SSH, health checks — final truth for what is running.

If Hermes, `proxmox-home`, and this file disagree, check the live host and fix the stale layer.

**Essentia is not a Hostinger workload.** Hostinger hosts other lanes (e.g. Dockhand UI access, external VPS apps). The API container runs on **`app-vm`**.

| Repo / doc | Path |
|------------|------|
| Endpoint index | `proxmox-home/docs/endpoint-index.md` |
| App VM + Dockhand runbook | `proxmox-home/docs/app-vm-dockhand-runbook.md` |
| IP / Tailscale map | `proxmox-home/docs/ip-address-map.md` |
| Service repo (this API) | `essentia-endpoint` |

## Production shape (verified)

| Item | Value |
|------|--------|
| **VM** | Proxmox VM100 **`app-vm`** |
| **LAN** | `192.168.8.222` |
| **Tailscale** | `app-vm` / `100.118.78.13` |
| **Orchestration** | **Dockhand** (app-vm environment) |
| **Compose path** | `/opt/essentia-endpoint` (env: `/opt/essentia-endpoint/.env`) |
| **Container** | `essentia-api` |
| **Host port** | `18000` → container `8000` |
| **Public URL** | `https://essentia.v1su4.dev` |
| **Health** | `GET /health` → `{"status":"ok","version":"4.0.2"}` |
| **Internal upload URL** | `http://192.168.8.222:18000` or Tailscale `http://100.118.78.13:18000` |

Models volume: `essentia-models` at `/app/models`. GPU: NVIDIA passthrough on VM100 when enabled (`gpus: all` in compose).

Use the **Tailscale or LAN URL** for large server-to-server uploads from sibling apps on the tailnet.

## Environment variables

Set these in the Dockhand stack/service environment (or the host `.env` the stack reads). Do not commit secret values.

| Variable | Required | Notes |
|----------|----------|-------|
| `API_KEYS` | yes | Comma-separated API keys. Only the `X-API-Key` header is checked — `Authorization: Bearer ...` is **not** accepted by `api/auth.py`. |
| `CORS_ORIGINS` | yes | Public browser origins that call the API |
| `METRICS_TOKEN` | optional | Bearer token for `/internal/metrics` if Prometheus/Grafana scrape it |
| `ESSENTIA_MODELS_PATH` | yes | Usually `/app/models` |
| `NVIDIA_VISIBLE_DEVICES` | optional | Usually `all` when GPU is exposed |
| `NVIDIA_DRIVER_CAPABILITIES` | optional | Usually `compute,utility` |
| `TONAL_CREPE_MODEL` | optional | `auto` by default |
| `TONAL_PITCH_MAX_SECONDS` | optional | Limits slower pitch analysis |
| `TONAL_TEMPO_MAX_SECONDS` | optional | Limits slower TempoCNN analysis |

### Dual-key configuration

`API_KEYS` may hold **two** comma-separated keys (shared project key + rotation/rebuild key). Neither value is recorded in this repo. Both slots authenticate until you retire the old one.

Verify a key without printing it:

```bash
curl -o /dev/null -s -w '%{http_code}\n' \
  -X POST https://essentia.v1su4.dev/analyze/fast \
  -H "X-API-Key: $ESSENTIA_API_KEY" \
  -F "file=@song.wav"
```

`200` = accepted; `401` = missing from `API_KEYS` on the host.

## Persistent model volume

Keep `/app/models` on a Docker volume so TensorFlow models persist across restarts. Without it, models re-download on every redeploy.

## Health checks

```bash
curl https://essentia.v1su4.dev/health
```

Expected:

```json
{"status":"ok","version":"4.0.2"}
```

## API paths used by client apps

- `/analyze/fast` — first-pass upload path (rhythm + energy + **structure**). Preferred for interactive editors.
- `/analyze/rhythm` — beats/onsets only (lighter, no structure).
- `/analyze/full` — rhythm, structure, classification, tonal, vocals.
- `/analyze/structure` — SBic section boundaries (legacy).
- `/analyze/structure/allin1` — functional labels via mir-aidj/all-in-one (intro/verse/chorus/…). Set `ALLIN1_DEVICE=cuda` on GPU hosts (4090).
- `/docs` — Swagger UI.
- `/health` — public health check.
- `/internal/metrics` — optional Prometheus endpoint (`METRICS_TOKEN`).

## Deploy updates (GitHub → Docker Hub → server)

1. **Push to `main`** on `gordo-v1su4/essentia-endpoint` — GitHub Actions builds and pushes `gordov1su4/essentia-api:4.1.0` and `:latest` to Docker Hub (does **not** restart the server by itself).
2. **On app-vm** (Dockhand or SSH to `/opt/essentia-endpoint`):
   ```bash
   docker compose pull
   docker compose up -d
   ```
   Or use Dockhand **Redeploy** after the workflow finishes (~20–40 min first allin1 build).
3. **Verify:**
   ```bash
   curl -s https://essentia.v1su4.dev/health
   curl -s -o /dev/null -w '%{http_code}\n' -X POST https://essentia.v1su4.dev/analyze/structure/allin1 \
     -H "X-API-Key: $ESSENTIA_API_KEY" -F "file=@song.wav"
   ```

Pin `ESSENTIA_IMAGE=gordov1su4/essentia-api:4.1.0` in the host `.env` when you want a fixed tag instead of compose default.

## Troubleshooting

- **Large upload fails on public URL**: use the internal host URL from Dockhand/Tailscale for server-side apps.
- **`401` with a key that used to work**: confirm the key is in the host `.env` `API_KEYS` list, then recreate the stack (`docker compose up -d --force-recreate` on the server).
- **Auth works with `X-API-Key` but fails with `Authorization: Bearer`**: expected — only `X-API-Key` is implemented.
- **No boundaries found**: not fatal — structure falls back to estimated intro/verse/chorus sections.

## Hosting note

- **Workload:** VM100 `app-vm` on Proxmox homelab — **not** a Hostinger VPS container.
- **Control plane:** Dockhand (see `proxmox-home/docs/app-vm-dockhand-runbook.md`).
- **Index:** Hermes notebook vault → **`proxmox-home`** repo → BWS for secrets.
- **Public edge:** Caddy routes `essentia.v1su4.dev` → `app-vm:18000`.

Update this file when compose or DNS moves; cross-check `proxmox-home/docs/endpoint-index.md` first.
