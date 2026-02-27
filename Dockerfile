# Optimized Essentia + FastAPI with GPU support
# This image includes libcudart and libcuda which TensorFlow needs
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Install Python 3.11, git, curl, then uv via standalone installer (avoids COPY --from which can fail on overlayfs)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python3.11 \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

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
