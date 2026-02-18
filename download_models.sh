#!/bin/bash
# Script to download recommended Essentia models for EDM/electronic music analysis
# Models from: https://essentia.upf.edu/models.html
# Repo: https://github.com/MTG/essentia-models

# Set models directory (default or from env var)
MODELS_DIR="${ESSENTIA_MODELS_PATH:-/app/models}"
mkdir -p "$MODELS_DIR"

echo "Downloading Essentia models to: $MODELS_DIR"
echo ""

# Check if git is available
if ! command -v git &> /dev/null; then
    echo "Git not found. Installing git..."
    apt-get update && apt-get install -y git || {
        echo "Failed to install git. Please install manually."
        exit 1
    }
fi

# GitHub repository
REPO_URL="https://github.com/MTG/essentia-models.git"
TEMP_DIR="/tmp/essentia-models"

echo "Cloning Essentia models repository..."
if [ -d "$TEMP_DIR" ]; then
    echo "   Removing existing temp directory..."
    rm -rf "$TEMP_DIR"
fi

# Clone the repository
git clone --depth 1 "$REPO_URL" "$TEMP_DIR" || {
    echo "Failed to clone repository. Trying with full history..."
    rm -rf "$TEMP_DIR"
    git clone "$REPO_URL" "$TEMP_DIR" || {
        echo "Failed to clone repository. Please check your internet connection."
        exit 1
    }
}

echo ""
echo "Available top-level dirs:"
ls -1 "$TEMP_DIR" | head -15
echo ""

# Helper: copy a model directory, trying multiple source paths
copy_model() {
    local name="$1"
    local dest="$2"
    shift 2
    local sources=("$@")

    for src in "${sources[@]}"; do
        if [ -d "$src" ]; then
            echo "   Copying $name..."
            mkdir -p "$dest"
            cp -r "$src"/* "$dest/" 2>/dev/null || cp -r "$src" "$dest/" 2>/dev/null
            echo "   -> $dest"
            return 0
        fi
    done
    echo "   $name not found in repository"
    return 1
}

echo "Copying recommended models for EDM/electronic music..."
echo ""

# --- Feature Extractors ---

# Discogs EffNet (genre classification - 400 genres + embeddings)
copy_model "discogs-effnet (genre classification)" \
    "$MODELS_DIR/discogs-effnet" \
    "$TEMP_DIR/feature-extractors/discogs-effnet" \
    "$TEMP_DIR/discogs-effnet" \
    "$TEMP_DIR/effnetdiscogs"

# MusiCNN (auto-tagging + embeddings)
copy_model "musicnn (auto-tagging)" \
    "$MODELS_DIR/musicnn" \
    "$TEMP_DIR/feature-extractors/musicnn" \
    "$TEMP_DIR/musicnn"

# --- Classification Heads ---

copy_model "classification-heads (mood, danceability, etc.)" \
    "$MODELS_DIR/classification_heads" \
    "$TEMP_DIR/classification-heads" \
    "$TEMP_DIR/classification_heads"

# --- Tempo ---

copy_model "tempocnn (deep learning tempo estimation)" \
    "$MODELS_DIR/tempocnn" \
    "$TEMP_DIR/tempo/tempocnn" \
    "$TEMP_DIR/tempocnn"

# --- Pitch ---

copy_model "crepe (pitch detection)" \
    "$MODELS_DIR/crepe" \
    "$TEMP_DIR/pitch/crepe" \
    "$TEMP_DIR/crepe"

# Verify classification heads include all needed models
echo ""
echo "Checking classification heads..."
HEADS_DIR="$MODELS_DIR/classification_heads"
if [ -d "$HEADS_DIR" ]; then
    for head in danceability voice_instrumental approachability engagement \
                nsynth_acoustic_electronic nsynth_bright_dark mtg_jamendo_instrument \
                tonal_atonal emomusic; do
        count=$(find "$HEADS_DIR" -name "*${head}*" 2>/dev/null | wc -l)
        if [ "$count" -gt 0 ]; then
            echo "   [OK] $head ($count files)"
        else
            echo "   [MISSING] $head"
        fi
    done
else
    echo "   classification_heads directory not found!"
fi

# Verify feature extractors
echo ""
echo "Checking feature extractors..."
for model_dir in discogs-effnet musicnn; do
    if [ -d "$MODELS_DIR/$model_dir" ]; then
        count=$(find "$MODELS_DIR/$model_dir" -name "*.pb" 2>/dev/null | wc -l)
        echo "   [OK] $model_dir ($count .pb files)"
    else
        echo "   [MISSING] $model_dir"
    fi
done

# Verify tempo/pitch models
echo ""
echo "Checking tempo & pitch models..."
for model_dir in tempocnn crepe; do
    if [ -d "$MODELS_DIR/$model_dir" ]; then
        count=$(find "$MODELS_DIR/$model_dir" -name "*.pb" 2>/dev/null | wc -l)
        echo "   [OK] $model_dir ($count .pb files)"
    else
        echo "   [MISSING] $model_dir"
    fi
done

# Clean up temp directory
echo ""
echo "Cleaning up temporary files..."
rm -rf "$TEMP_DIR"

echo ""
echo "Models download complete!"
echo ""
echo "Models location: $MODELS_DIR"
echo "Installed model directories:"
ls -1 "$MODELS_DIR" 2>/dev/null || echo "   (no models found)"
