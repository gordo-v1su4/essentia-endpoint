#!/bin/bash
# Build and push Essentia API to Docker Hub
# Usage: ./build-push.sh
# Or:   DOCKERHUB_USER=otherusername ./build-push.sh

set -euo pipefail
VERSION="${VERSION:-4.0.2}"
USER="${DOCKERHUB_USER:-${1:-gordov1su4}}"
PLATFORM="${PLATFORM:-linux/amd64}"
BUILDER="${BUILDER_NAME:-essentia-builder}"
SMOKE_API_KEY="${SMOKE_API_KEY:-smoke-test-key}"
SKIP_PUSH="${SKIP_PUSH:-0}"

IMAGE="$USER/essentia-api"

if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
  docker buildx create --name "$BUILDER" --driver docker-container --use >/dev/null
else
  docker buildx use "$BUILDER" >/dev/null
fi

echo "Building $IMAGE:$VERSION and $IMAGE:latest for $PLATFORM..."
docker buildx build --platform "$PLATFORM" --load \
  -t "$IMAGE:$VERSION" \
  -t "$IMAGE:latest" .

# Smoke test before push
echo "Running smoke test on /health..."
docker rm -f essentia-api-smoke >/dev/null 2>&1 || true
docker run -d --name essentia-api-smoke -p 18000:8000 \
  -e API_KEYS="$SMOKE_API_KEY" \
  "$IMAGE:$VERSION" >/dev/null
for i in {1..45}; do
  if curl -fsS --max-time 2 "http://localhost:18000/health" >/dev/null; then
    echo "Smoke test passed"
    break
  fi
  if [ "$i" -eq 45 ]; then
    echo "Smoke test failed: /health did not become ready"
    docker logs essentia-api-smoke || true
    docker rm -f essentia-api-smoke >/dev/null 2>&1 || true
    exit 1
  fi
  sleep 2
done
docker rm -f essentia-api-smoke >/dev/null 2>&1 || true

if [ "$SKIP_PUSH" = "1" ]; then
  echo "SKIP_PUSH=1 set, skipping Docker Hub push."
  exit 0
fi

echo "Pushing to Docker Hub..."
docker push "$IMAGE:$VERSION"
docker push "$IMAGE:latest"

echo "Done! Image: $IMAGE:$VERSION"
