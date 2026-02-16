#!/bin/bash
# Build and push Essentia API to Docker Hub
# Usage: ./build-push.sh
# Or:   DOCKERHUB_USER=otherusername ./build-push.sh

set -e
VERSION="${VERSION:-2.0.2}"
USER="${DOCKERHUB_USER:-${1:-gordov1su4}}"

IMAGE="$USER/essentia-api"
echo "Building $IMAGE:$VERSION and $IMAGE:latest..."
docker build -t "$IMAGE:$VERSION" -t "$IMAGE:latest" .

echo "Pushing to Docker Hub..."
docker push "$IMAGE:$VERSION"
docker push "$IMAGE:latest"

echo "Done! Image: $IMAGE:$VERSION"
