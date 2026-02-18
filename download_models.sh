#!/bin/bash
# Download Essentia TF models from the official distribution server
# Source: https://essentia.upf.edu/models/

set -e

MODELS_DIR="${ESSENTIA_MODELS_PATH:-/app/models}"
BASE_URL="https://essentia.upf.edu/models"
mkdir -p "$MODELS_DIR"

echo "Downloading Essentia models to: $MODELS_DIR"
echo "Source: $BASE_URL"
echo ""

# Helper: download a single model file
dl() {
    local url="$1"
    local dest="$2"
    mkdir -p "$(dirname "$dest")"
    if [ -f "$dest" ]; then
        echo "   [SKIP] $(basename "$dest") (already exists)"
        return 0
    fi
    echo "   [GET]  $(basename "$dest")"
    curl -fSL --retry 3 --connect-timeout 30 -o "$dest" "$url" || {
        echo "   [FAIL] $(basename "$dest")"
        rm -f "$dest"
        return 1
    }
}

# --- Feature Extractors ---
echo "=== Feature Extractors ==="

echo "-- discogs-effnet (genre classification + embeddings) --"
dl "$BASE_URL/feature-extractors/discogs-effnet/discogs-effnet-bs64-1.pb" \
   "$MODELS_DIR/discogs-effnet/discogs-effnet-bs64-1.pb"

echo "-- musicnn (auto-tagging + embeddings) --"
dl "$BASE_URL/feature-extractors/musicnn/msd-musicnn-1.pb" \
   "$MODELS_DIR/musicnn/msd-musicnn-1.pb"

# --- Classification Heads ---
echo ""
echo "=== Classification Heads ==="

echo "-- emomusic (mood: valence/arousal) --"
dl "$BASE_URL/classification-heads/emomusic/emomusic-msd-musicnn-1.pb" \
   "$MODELS_DIR/classification_heads/emomusic/emomusic-msd-musicnn-1.pb"

echo "-- danceability --"
dl "$BASE_URL/classification-heads/danceability/danceability-discogs-effnet-1.pb" \
   "$MODELS_DIR/classification_heads/danceability/danceability-discogs-effnet-1.pb"

echo "-- voice_instrumental --"
dl "$BASE_URL/classification-heads/voice_instrumental/voice_instrumental-discogs-effnet-1.pb" \
   "$MODELS_DIR/classification_heads/voice_instrumental/voice_instrumental-discogs-effnet-1.pb"

echo "-- approachability --"
dl "$BASE_URL/classification-heads/approachability/approachability_regression-discogs-effnet-1.pb" \
   "$MODELS_DIR/classification_heads/approachability/approachability_regression-discogs-effnet-1.pb"

echo "-- engagement --"
dl "$BASE_URL/classification-heads/engagement/engagement_regression-discogs-effnet-1.pb" \
   "$MODELS_DIR/classification_heads/engagement/engagement_regression-discogs-effnet-1.pb"

echo "-- nsynth_acoustic_electronic --"
dl "$BASE_URL/classification-heads/nsynth_acoustic_electronic/nsynth_acoustic_electronic-discogs-effnet-1.pb" \
   "$MODELS_DIR/classification_heads/nsynth_acoustic_electronic/nsynth_acoustic_electronic-discogs-effnet-1.pb"

echo "-- nsynth_bright_dark --"
dl "$BASE_URL/classification-heads/nsynth_bright_dark/nsynth_bright_dark-discogs-effnet-1.pb" \
   "$MODELS_DIR/classification_heads/nsynth_bright_dark/nsynth_bright_dark-discogs-effnet-1.pb"

echo "-- mtg_jamendo_instrument --"
dl "$BASE_URL/classification-heads/mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1.pb" \
   "$MODELS_DIR/classification_heads/mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1.pb"

echo "-- tonal_atonal --"
dl "$BASE_URL/classification-heads/tonal_atonal/tonal_atonal-discogs-effnet-1.pb" \
   "$MODELS_DIR/classification_heads/tonal_atonal/tonal_atonal-discogs-effnet-1.pb"

# --- Tempo ---
echo ""
echo "=== Tempo ==="

echo "-- tempocnn --"
dl "$BASE_URL/tempo/tempocnn/deeptemp-k16-3.pb" \
   "$MODELS_DIR/tempocnn/deeptemp-k16-3.pb"
dl "$BASE_URL/tempo/tempocnn/deepsquare-k16-3.pb" \
   "$MODELS_DIR/tempocnn/deepsquare-k16-3.pb"

# --- Pitch ---
echo ""
echo "=== Pitch ==="

echo "-- crepe (pitch detection, full model) --"
dl "$BASE_URL/pitch/crepe/crepe-full-1.pb" \
   "$MODELS_DIR/crepe/crepe-full-1.pb"

# --- Verification ---
echo ""
echo "=== Verification ==="
TOTAL=0
FOUND=0
for pb in \
    "$MODELS_DIR/discogs-effnet/discogs-effnet-bs64-1.pb" \
    "$MODELS_DIR/musicnn/msd-musicnn-1.pb" \
    "$MODELS_DIR/classification_heads/emomusic/emomusic-msd-musicnn-1.pb" \
    "$MODELS_DIR/classification_heads/danceability/danceability-discogs-effnet-1.pb" \
    "$MODELS_DIR/classification_heads/voice_instrumental/voice_instrumental-discogs-effnet-1.pb" \
    "$MODELS_DIR/classification_heads/approachability/approachability_regression-discogs-effnet-1.pb" \
    "$MODELS_DIR/classification_heads/engagement/engagement_regression-discogs-effnet-1.pb" \
    "$MODELS_DIR/classification_heads/nsynth_acoustic_electronic/nsynth_acoustic_electronic-discogs-effnet-1.pb" \
    "$MODELS_DIR/classification_heads/nsynth_bright_dark/nsynth_bright_dark-discogs-effnet-1.pb" \
    "$MODELS_DIR/classification_heads/mtg_jamendo_instrument/mtg_jamendo_instrument-discogs-effnet-1.pb" \
    "$MODELS_DIR/classification_heads/tonal_atonal/tonal_atonal-discogs-effnet-1.pb" \
    "$MODELS_DIR/tempocnn/deeptemp-k16-3.pb" \
    "$MODELS_DIR/crepe/crepe-full-1.pb"; do
    TOTAL=$((TOTAL + 1))
    if [ -f "$pb" ]; then
        FOUND=$((FOUND + 1))
        echo "   [OK]   $(basename "$pb")"
    else
        echo "   [MISS] $(basename "$pb")"
    fi
done

echo ""
echo "Models download complete: $FOUND/$TOTAL files present"
echo "Location: $MODELS_DIR"
