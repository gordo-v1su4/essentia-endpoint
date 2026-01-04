# Optimized Essentia + FastAPI with GPU support
# This image includes libcudart and libcuda which TensorFlow needs
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Install Python 3.11, git, and uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3-pip \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python3.11 \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && pip install --no-cache-dir uv

# Note: git is already installed in the base image setup above

# Note: Essentia Python package typically includes statically linked libraries
# If runtime errors occur about missing libraries, we'll add them back
# For now, we skip runtime deps to get the build working

# Install Python packages directly using uv (much faster!)
WORKDIR /app
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Make sure scripts in .local are usable (if any get installed there)
ENV PATH=/root/.local/bin:$PATH

# Copy application code
WORKDIR /app
COPY . .

# Create models directory (will be mounted as volume in docker-compose)
RUN mkdir -p /app/models

# Copy download script and entrypoint
COPY download_models.sh /app/download_models.sh
COPY entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/download_models.sh && \
    sed -i 's/\r$//' /app/entrypoint.sh && \
    chmod +x /app/download_models.sh /app/entrypoint.sh

# Expose port (default 8000, can be overridden)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Use entrypoint script (auto-downloads models if missing, then starts API)
ENTRYPOINT ["/app/entrypoint.sh"]

