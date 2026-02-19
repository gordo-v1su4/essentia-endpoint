#!/bin/bash
# Entrypoint script that can download models and starts the API.
# By default downloads run in background so healthcheck can pass quickly.

set -e

MODELS_DIR="${ESSENTIA_MODELS_PATH:-/app/models}"
MODELS_VERSION="3"
VERSION_FILE="$MODELS_DIR/.models_version"
MODEL_DOWNLOAD_BLOCKING="${MODEL_DOWNLOAD_BLOCKING:-0}"

echo "Starting Essentia API..."
echo "Models directory: $MODELS_DIR"

# Re-download if: no models, or models version changed (structure/source changed)
CURRENT_VERSION=""
if [ -f "$VERSION_FILE" ]; then
    CURRENT_VERSION=$(cat "$VERSION_FILE" 2>/dev/null)
fi

needs_download=0
if [ ! -d "$MODELS_DIR" ] || [ -z "$(ls -A "$MODELS_DIR" 2>/dev/null)" ] || [ "$CURRENT_VERSION" != "$MODELS_VERSION" ]; then
    needs_download=1
fi

if [ "$needs_download" -eq 1 ]; then
    if [ "$CURRENT_VERSION" != "$MODELS_VERSION" ] && [ -n "$CURRENT_VERSION" ]; then
        echo "Models version changed ($CURRENT_VERSION -> $MODELS_VERSION), re-downloading..."
        rm -rf "$MODELS_DIR"
        mkdir -p "$MODELS_DIR"
    else
        echo "No models found in $MODELS_DIR"
    fi

    if [ "$MODEL_DOWNLOAD_BLOCKING" = "1" ]; then
        echo "Auto-downloading models (blocking mode)..."
        echo ""
        python /app/download_models.py
        echo "$MODELS_VERSION" > "$VERSION_FILE"
        echo ""
        echo "Model download complete!"
    else
        echo "Auto-downloading models in background (non-blocking mode)..."
        (
            if python /app/download_models.py; then
                echo "$MODELS_VERSION" > "$VERSION_FILE"
                echo "Model download complete!"
            else
                echo "Model download failed. API is running, classification endpoints may fail until models are present." >&2
            fi
        ) &
    fi
else
    echo "Models already present (v$CURRENT_VERSION)"
fi

echo ""
echo "Starting FastAPI server..."
echo ""

# Start the API
exec uvicorn main:app --host 0.0.0.0 --port 8000
