# Optimized Essentia + FastAPI with GPU support
# This image includes libcudart and libcuda which TensorFlow needs
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Get uv binary from official image (no pip needed)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python 3.11 and git
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    git \
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

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Use entrypoint script (auto-downloads models if missing, then starts API)
ENTRYPOINT ["/app/entrypoint.sh"]

