# CORS Configuration

## Current Behavior

The API defaults to `allow_origins=["*"]` for maximum compatibility. Override via environment variable.

## Configuration

### Allow all origins (default)
```bash
CORS_ORIGINS=*
```

### Specific origins (recommended for production)
```bash
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

Set in your `.env`, `docker-compose.yml`, or Portainer stack/service environment variables.

## Testing

```bash
curl -I -X OPTIONS http://localhost:7000/analyze/rhythm \
  -H "Origin: https://yourdomain.com" \
  -H "Access-Control-Request-Method: POST"
```

Should return `Access-Control-Allow-Origin` header matching your origin.
