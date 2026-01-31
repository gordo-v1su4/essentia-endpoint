# Essentia Audio Analysis API

FastAPI server for comprehensive audio analysis using Essentia. Provides rhythm analysis, structural segmentation, classification (genre/mood/tags), and tonal analysis.

## Documentation

Additional documentation is available in the [`docs/`](docs/) folder:
- [Energy Curve Updates](docs/ENERGY_CURVE_UPDATE.md) - Speed ramping and energy-based features
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [Coolify Setup](docs/COOLIFY.md) - Coolify-specific configuration
- [Models Setup](docs/MODELS_SETUP.md) - TensorFlow models configuration
- [CORS Configuration](docs/CORS_FIX.md) - CORS troubleshooting
- [OpenAPI Schema](docs/openapi.json) - API specification

## Quick Start

### Local Development

```bash
# Install dependencies
cd api
uv venv
uv pip install -r requirements.txt

# Run server
uvicorn main:app --reload --port 8000
```

### Docker Deployment

#### Build and Run

```bash
cd api

# Build the image
docker build -t essentia-api .

# Run the container
docker run -p 8000:8000 essentia-api
```
                                                                                                                                 
#### Using Docker Compose

```bash
cd api

# Copy environment file
cp .env.example .env

# Edit .env to set your CORS origins for production
# CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Host to bind the server to |
| `API_PORT` | `8000` | Port to run the server on |
| `CORS_ORIGINS` | `*` | Comma-separated list of allowed CORS origins |
| `API_KEYS` | (required) | Comma-separated list of valid API keys |

## Authentication

All analysis endpoints require API key authentication. Include your API key in the `X-API-Key` header with every request.

### Getting an API Key

Contact the API administrator to receive your API key.

### Using Your API Key

Include the `X-API-Key` header in all requests to protected endpoints.

**cURL Example:**
```bash
curl -X POST "https://essentia.v1su4.com/analyze/rhythm" \
  -H "X-API-Key: your_api_key_here" \
  -F "file=@audio.mp3"
```

**Python Example:**
```python
import requests

headers = {"X-API-Key": "your_api_key_here"}
files = {"file": open("audio.mp3", "rb")}

response = requests.post(
    "https://essentia.v1su4.com/analyze/rhythm",
    headers=headers,
    files=files
)

print(response.json())
```

**JavaScript Example:**
```javascript
const formData = new FormData();
formData.append('file', audioFile);

fetch('https://essentia.v1su4.com/analyze/rhythm', {
  method: 'POST',
  headers: {
    'X-API-Key': 'your_api_key_here'
  },
  body: formData
})
.then(response => response.json())
.then(data => console.log(data));
```

### Protected vs Public Endpoints

**Protected (require API key):**
- `POST /analyze/rhythm`
- `POST /analyze/structure`
- `POST /analyze/classification`
- `POST /analyze/full`

**Public (no authentication required):**
- `GET /health` - Health check for monitoring systems
- `GET /docs` - API documentation (Swagger UI)
- `GET /redoc` - API documentation (ReDoc)

## API Documentation

### Interactive Documentation

- **Swagger UI**: https://essentia.v1su4.com/docs (or `http://localhost:8000/docs` for local)
- **ReDoc**: https://essentia.v1su4.com/redoc (or `http://localhost:8000/redoc` for local)

### API Endpoints

#### `POST /analyze/rhythm`

Extract BPM, beats, confidence, onsets, and high-resolution energy curve.

**Response:**
```json
{
  "bpm": 120.5,
  "beats": [0.0, 0.5, 1.0, ...],
  "confidence": 0.95,
  "onsets": [0.1, 0.3, 0.6, ...],
  "duration": 180.5,
  "energy": {
    "mean": 0.45,
    "std": 0.12,
    "curve": [0.0, 0.1, 0.3, 0.5, ...]
  }
}
```

#### `POST /analyze/structure`

Segment audio into sections (intro, verse, chorus, etc.) with energy values.

**Response:**
```json
{
  "sections": [
    {
      "start": 0.0,
      "end": 15.2,
      "label": "intro",
      "duration": 15.2,
      "energy": 0.12
    }
  ]
}
```

#### `POST /analyze/classification`

Analyze genre, mood, and tags using Essentia TensorFlow models.

**Response:**
```json
{
  "genre": {"electronic": 0.8, "rock": 0.15, ...},
  "mood": {"energetic": 0.9, "happy": 0.7, ...},
  "tags": {"instrumental": 0.95, "dance": 0.8, ...}
}
```

#### `POST /analyze/full`

Perform complete analysis (rhythm, structure, classification, and tonal).

**Response:** Combined data from all analysis types.

#### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "version": "2.0.0"
}
```

## Deployment to Remote Server

### Option 1: Docker on Remote Server

1. **Copy files to server:**
   ```bash
   scp -r api/ user@server:/path/to/deploy/
   ```

2. **SSH into server:**
   ```bash
   ssh user@server
   cd /path/to/deploy/api
   ```

3. **Build and run:**
   ```bash
   docker-compose up -d
   ```

4. **Update frontend environment:**
   - Set `VITE_ESSENTIA_API_URL=https://essentia.v1su4.com` in your frontend `.env` file

### Option 2: Docker Hub / Container Registry

1. **Build and push:**
   ```bash
   docker build -t yourusername/essentia-api:latest .
   docker push yourusername/essentia-api:latest
   ```

2. **Pull and run on server:**
   ```bash
   docker pull yourusername/essentia-api:latest
   docker run -d -p 8000:8000 \
     -e CORS_ORIGINS=https://yourdomain.com \
     yourusername/essentia-api:latest
   ```

### Option 3: Cloud Platform (AWS, GCP, Azure)

- **AWS ECS/Fargate**: Use the Dockerfile with ECS task definitions
- **Google Cloud Run**: Deploy directly from Dockerfile
- **Azure Container Instances**: Use docker-compose or Azure CLI
- **DigitalOcean App Platform**: Connect GitHub repo, auto-deploy on push

## Production Considerations

1. **CORS Configuration**: Set `CORS_ORIGINS` to your actual frontend domain(s)
2. **Reverse Proxy**: Use nginx/traefik for SSL termination and routing
3. **Resource Limits**: Adjust CPU/memory in docker-compose.yml based on load
4. **Health Checks**: Configure your orchestrator to use `/health` endpoint
5. **Logging**: Add structured logging for production monitoring

## Troubleshooting

### Essentia Installation Issues

If Essentia fails to install in Docker, you may need to:
- Use a pre-built Essentia Docker image
- Build Essentia from source in a multi-stage build
- Use a different base image with Essentia pre-installed

### CORS Errors

If you see CORS errors from the frontend:
- Check that `CORS_ORIGINS` includes your frontend URL
- Ensure the API is accessible from the frontend domain
- Verify the API URL in frontend environment variables

### Port Conflicts

If port 8000 is already in use:
- Change `API_PORT` environment variable
- Update port mapping in docker-compose.yml
- Update frontend `VITE_ESSENTIA_API_URL` accordingly

