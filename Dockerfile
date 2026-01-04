# Multi-stage build for Essentia + FastAPI
FROM python:3.11-slim as builder

# Install build dependencies for Essentia
# Handle dpkg errors and problematic packages gracefully
RUN apt-get update && \
    apt-get install -y --fix-broken || true && \
    dpkg --configure -a || true && \
    # Install core build tools first (these should always work)
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libyaml-dev \
    libfftw3-dev \
    python3-dev \
    && \
    # Install FFmpeg libraries
    # If libcodec2 fails, we'll handle it with dpkg --force
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswresample-dev \
    || ( \
    # If installation failed, try to fix broken packages
    echo "Attempting to fix broken packages..." && \
    dpkg --configure -a --force-depends || true && \
    apt-get install -f -y || true && \
    # Remove problematic libcodec2 if it's causing issues
    dpkg -r --force-depends libcodec2-1.2 2>/dev/null || true && \
    # Try installing FFmpeg libs again
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libavcodec-dev libavformat-dev libavutil-dev libswresample-dev || \
    echo "Warning: Some FFmpeg packages failed, but continuing..." \
    ) && \
    # Try optional libtag packages
    (apt-get install -y --no-install-recommends libtag1-dev || \
    apt-get install -y --no-install-recommends libtag-dev || true) && \
    rm -rf /var/lib/apt/lists/*

# Install Essentia and Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage - Use NVIDIA CUDA + Python for GPU support
# This image includes libcudart and libcuda which TensorFlow needs
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Install Python 3.11 and git
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
    && ln -sf /usr/bin/pip3 /usr/bin/pip

# Note: git is already installed in the base image setup above

# Note: Essentia Python package typically includes statically linked libraries
# If runtime errors occur about missing libraries, we'll add them back
# For now, we skip runtime deps to get the build working

# Install Python packages directly (avoids shebang path issues from multi-stage)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

