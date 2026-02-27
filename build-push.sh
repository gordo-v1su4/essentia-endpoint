#!/bin/bash
# Build and push Essentia API to Docker Hub
# Usage: ./build-push.sh
# Or:   DOCKERHUB_USER=otherusername ./build-push.sh

set -e
VERSION="${VERSION:-3.0.3}"
USER="${DOCKERHUB_USER:-${1:-gordov1su4}}"

IMAGE="$USER/essentia-api"
echo "Building $IMAGE:$VERSION and $IMAGE:latest..."
docker build -t "$IMAGE:$VERSION" -t "$IMAGE:latest" .

# Smoke test before push
echo "Running smoke test on /health..."
docker rm -f essentia-api-smoke >/dev/null 2>&1 || true
docker run -d --name essentia-api-smoke -p 18000:8000 "$IMAGE:$VERSION" >/dev/null
for i in {1..45}; do
  if curl -fsS "http://localhost:18000/health" >/dev/null; then
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

echo "Pushing to Docker Hub..."
docker push "$IMAGE:$VERSION"
docker push "$IMAGE:latest"

echo "Done! Image: $IMAGE:$VERSION"
