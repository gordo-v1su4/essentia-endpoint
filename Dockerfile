# Optimized Essentia + FastAPI with GPU support
# This image includes libcudart and libcuda which TensorFlow needs
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Get uv binary from official image (no pip needed)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python 3.11, git, and curl (used by healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python3.11

# Install Python packages with uv
WORKDIR /app
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application code
WORKDIR /app
COPY . .

# Create models directory (will be mounted as volume in docker-compose)
RUN mkdir -p /app/models

# Copy download script and entrypoint
COPY download_models.py /app/download_models.py
COPY entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Expose port (default 8000, can be overridden)
EXPOSE 8000

# Health check tuned for orchestrators like Coolify
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=12 \
    CMD curl -fsS --max-time 3 http://127.0.0.1:8000/health || exit 1

# Use entrypoint script (auto-downloads models if missing, then starts API)
ENTRYPOINT ["/app/entrypoint.sh"]
