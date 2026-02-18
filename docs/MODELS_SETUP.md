# TensorFlow Models Setup

## Auto-Download (Default)

Models auto-download on first container startup from `essentia.upf.edu/models/`. No manual setup needed.

```bash
docker-compose up -d --build
# Models download automatically, then API starts
```

Models are saved to `./models/` on the host (Docker volume mount to `/app/models`). They persist across container restarts.

## What Gets Downloaded

| Model | File | Size | Purpose |
|-------|------|------|---------|
| Discogs EffNet | `discogs-effnet-bs64-1.pb` | ~20MB | Genre classification (400 labels) + embeddings |
| MusiCNN | `msd-musicnn-1.pb` | ~10MB | Auto-tagging (50 labels) + embeddings |
| EmoMusic | `emomusic-msd-musicnn-1.pb` | ~1MB | Mood (valence/arousal) |
| Danceability | `danceability-discogs-effnet-1.pb` | ~1MB | Danceable vs not |
| Voice/Instrumental | `voice_instrumental-discogs-effnet-1.pb` | ~1MB | Vocal detection |
| Approachability | `approachability_regression-discogs-effnet-1.pb` | ~1MB | Approachability score |
| Engagement | `engagement_regression-discogs-effnet-1.pb` | ~1MB | Engagement score |
| Acoustic/Electronic | `nsynth_acoustic_electronic-discogs-effnet-1.pb` | ~1MB | Acoustic vs electronic |
| Bright/Dark | `nsynth_bright_dark-discogs-effnet-1.pb` | ~1MB | Timbral brightness |
| Instrument | `mtg_jamendo_instrument-discogs-effnet-1.pb` | ~1MB | 40 instrument classes |
| Tonal/Atonal | `tonal_atonal-discogs-effnet-1.pb` | ~1MB | Tonal vs atonal |
| TempoCNN | `deeptemp-k16-3.pb`, `deepsquare-k16-3.pb` | ~5MB | Deep-learning tempo |
| CREPE | `crepe-full-1.pb` | ~89MB | Pitch detection |

Total: ~130MB first download.

## Directory Structure on Disk

```
/app/models/
  discogs-effnet/
    discogs-effnet-bs64-1.pb
  musicnn/
    msd-musicnn-1.pb
  classification_heads/
    emomusic/emomusic-msd-musicnn-1.pb
    danceability/danceability-discogs-effnet-1.pb
    voice_instrumental/voice_instrumental-discogs-effnet-1.pb
    approachability/approachability_regression-discogs-effnet-1.pb
    engagement/engagement_regression-discogs-effnet-1.pb
    nsynth_acoustic_electronic/nsynth_acoustic_electronic-discogs-effnet-1.pb
    nsynth_bright_dark/nsynth_bright_dark-discogs-effnet-1.pb
    mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1.pb
    tonal_atonal/tonal_atonal-discogs-effnet-1.pb
  tempocnn/
    deeptemp-k16-3.pb
    deepsquare-k16-3.pb
  crepe/
    crepe-full-1.pb
  .models_version
```

## Force Re-Download

Models are versioned. When the download script changes, the entrypoint automatically re-downloads. To force manually:

```bash
# Remove models volume and rebuild
docker-compose down -v
docker-compose up -d --build

# Or manually inside container
docker-compose exec essentia-api /app/download_models.sh
```

## Model Source

All models are from the Essentia ecosystem at UPF (Universitat Pompeu Fabra):
- Download server: `https://essentia.upf.edu/models/`
- Documentation: `https://essentia.upf.edu/models.html`

The `download_models.sh` script fetches each `.pb` file directly via curl.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `ESSENTIA_MODELS_PATH` | `/app/models` | Where models are stored inside the container |

## Troubleshooting

**Models not found**: Check container logs for download errors:
```bash
docker-compose logs essentia-api | grep -i model
```

**Download fails**: Verify the container can reach `essentia.upf.edu`:
```bash
docker-compose exec essentia-api curl -I https://essentia.upf.edu/models/
```

**Classification returns null**: A specific `.pb` file is missing. Run the download script and check verification output:
```bash
docker-compose exec essentia-api /app/download_models.sh
```
