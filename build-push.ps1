# Build and push Essentia API to Docker Hub
# Usage: .\build-push.ps1
# Or:   .\build-push.ps1 -User otherusername

param(
    [string]$User = $env:DOCKERHUB_USER ?? "gordov1su4",
    [string]$Version = "4.0.1",
    [string]$Platform = "linux/amd64",
    [string]$BuilderName = "essentia-builder",
    [string]$SmokeApiKey = "smoke-test-key",
    [switch]$SkipPush
)


$Image = "$User/essentia-api"
if (-not (docker buildx inspect $BuilderName *> $null)) {
    docker buildx create --name $BuilderName --driver docker-container --use | Out-Null
} else {
    docker buildx use $BuilderName | Out-Null
}

Write-Host "Building $Image`:$Version and $Image`:latest for $Platform..."
docker buildx build --platform $Platform --load -t "${Image}:${Version}" -t "${Image}:latest" .

Write-Host "Running smoke test on /health..."
docker rm -f essentia-api-smoke *> $null
docker run -d --name essentia-api-smoke -p 18000:8000 -e "API_KEYS=$SmokeApiKey" "${Image}:${Version}" *> $null
$Ready = $false
for ($i = 0; $i -lt 45; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:18000/health" -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $Ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $Ready) {
    Write-Error "Smoke test failed: /health did not become ready"
    docker logs essentia-api-smoke
    docker rm -f essentia-api-smoke *> $null
    exit 1
}

docker rm -f essentia-api-smoke *> $null

if ($SkipPush) {
    Write-Host "SkipPush enabled, skipping Docker Hub push."
    exit 0
}

Write-Host "Pushing to Docker Hub..."
docker push "${Image}:${Version}"
docker push "${Image}:latest"

Write-Host "Done! Image: $Image`:$Version"
