#!/usr/bin/env python3
"""Download Essentia TF models from the official distribution server.
Uses only stdlib (urllib) so no extra packages are needed in the Docker image.
"""

import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

MODELS_DIR = Path(os.environ.get("ESSENTIA_MODELS_PATH", "/app/models"))
BASE_URL = "https://essentia.upf.edu/models"

MODELS = [
    # Feature extractors
    ("feature-extractors/discogs-effnet/discogs-effnet-bs64-1.pb", "discogs-effnet/discogs-effnet-bs64-1.pb"),
    ("feature-extractors/musicnn/msd-musicnn-1.pb", "musicnn/msd-musicnn-1.pb"),
    # Classification heads
    ("classification-heads/emomusic/emomusic-msd-musicnn-1.pb", "classification_heads/emomusic/emomusic-msd-musicnn-1.pb"),
    ("classification-heads/danceability/danceability-discogs-effnet-1.pb", "classification_heads/danceability/danceability-discogs-effnet-1.pb"),
    ("classification-heads/voice_instrumental/voice_instrumental-discogs-effnet-1.pb", "classification_heads/voice_instrumental/voice_instrumental-discogs-effnet-1.pb"),
    ("classification-heads/approachability/approachability_regression-discogs-effnet-1.pb", "classification_heads/approachability/approachability_regression-discogs-effnet-1.pb"),
    ("classification-heads/engagement/engagement_regression-discogs-effnet-1.pb", "classification_heads/engagement/engagement_regression-discogs-effnet-1.pb"),
    ("classification-heads/nsynth_acoustic_electronic/nsynth_acoustic_electronic-discogs-effnet-1.pb", "classification_heads/nsynth_acoustic_electronic/nsynth_acoustic_electronic-discogs-effnet-1.pb"),
    ("classification-heads/nsynth_bright_dark/nsynth_bright_dark-discogs-effnet-1.pb", "classification_heads/nsynth_bright_dark/nsynth_bright_dark-discogs-effnet-1.pb"),
    ("classification-heads/mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1.pb", "classification_heads/mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1.pb"),
    ("classification-heads/tonal_atonal/tonal_atonal-discogs-effnet-1.pb", "classification_heads/tonal_atonal/tonal_atonal-discogs-effnet-1.pb"),
    # Tempo
    ("tempo/tempocnn/deeptemp-k16-3.pb", "tempocnn/deeptemp-k16-3.pb"),
    ("tempo/tempocnn/deepsquare-k16-3.pb", "tempocnn/deepsquare-k16-3.pb"),
    # Pitch
    ("pitch/crepe/crepe-full-1.pb", "crepe/crepe-full-1.pb"),
]


def download(url_path: str, local_path: Path) -> bool:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if local_path.exists():
        print(f"   [SKIP] {local_path.name} (already exists)")
        return True
    url = f"{BASE_URL}/{url_path}"
    print(f"   [GET]  {local_path.name}")
    for attempt in range(3):
        try:
            urllib.request.urlretrieve(url, local_path)
            return True
        except (urllib.error.URLError, OSError) as e:
            if attempt == 2:
                print(f"   [FAIL] {local_path.name}: {e}")
                local_path.unlink(missing_ok=True)
                return False
    return False


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Essentia models to: {MODELS_DIR}")
    print(f"Source: {BASE_URL}")
    print()

    total = len(MODELS)
    found = 0
    for url_path, local_rel in MODELS:
        if download(url_path, MODELS_DIR / local_rel):
            found += 1

    print()
    print(f"Models download complete: {found}/{total} files present")
    print(f"Location: {MODELS_DIR}")

    if found < total:
        print(f"WARNING: {total - found} model(s) failed to download", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
