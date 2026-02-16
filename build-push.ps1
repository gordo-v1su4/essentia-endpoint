# Build and push Essentia API to Docker Hub
# Usage: .\build-push.ps1
# Or:   .\build-push.ps1 -User otherusername

param(
    [string]$User = $env:DOCKERHUB_USER ?? "gordov1su4",
    [string]$Version = "2.0.1"
)


$Image = "$User/essentia-api"
Write-Host "Building $Image`:$Version and $Image`:latest..."
docker build -t "${Image}:${Version}" -t "${Image}:latest" .

Write-Host "Pushing to Docker Hub..."
docker push "${Image}:${Version}"
docker push "${Image}:latest"

Write-Host "Done! Image: $Image`:$Version"
