# Next.js v0 Proxy for Essentia API

This subproject makes the FastAPI Essentia backend usable from v0/Next.js apps.

The proxy runs in Next.js route handlers and forwards multipart upload requests to:

- `POST /analyze/rhythm`
- `POST /analyze/structure`
- `POST /analyze/classification`
- `POST /analyze/tonal`
- `POST /analyze/vocals`
- `POST /analyze/full`
- `GET /health`

## Why this pattern

Essentia + TensorFlow + CUDA do not run in normal Vercel serverless/edge runtime.
Keep the analysis engine on your existing FastAPI service, and let Next.js proxy requests.

## Local run

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment variables

- `ESSENTIA_API_BASE_URL` (required)
- `ESSENTIA_API_KEY` (required)

## API shape in Next.js app

- `POST /api/essentia/rhythm`
- `POST /api/essentia/structure`
- `POST /api/essentia/classification`
- `POST /api/essentia/tonal`
- `POST /api/essentia/vocals`
- `POST /api/essentia/full`
- `GET /api/essentia/health`

Pass `file` in multipart form data.  
For classification feature filtering, include query params, for example:

`/api/essentia/classification?features=genre,mood,tags`
