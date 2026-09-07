# Optimized Essentia + FastAPI with GPU support
# This image includes libcudart and libcuda which TensorFlow needs
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04

# Install Python 3.11, git, curl, then uv via standalone installer (avoids COPY --from which can fail on overlayfs)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    git \
    curl \
    ca-certificates \
    ffmpeg \
    cmake \
    build-essential \
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

# all-in-one structure analysis (mir-aidj/all-in-one)
RUN uv pip install --system --no-cache \
    torch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 \
    --index-url https://download.pytorch.org/whl/cu118
# Docker builds normally have no visible GPU. NATTEN otherwise silently builds
# CPU-only kernels even though Torch has CUDA; VM100 uses an RTX 4090 (SM89).
ARG NATTEN_CUDA_ARCH=8.9
ARG NATTEN_N_WORKERS=1
RUN uv pip install --system --no-cache "numpy>=1.24,<2" "setuptools==69.5.1" wheel packaging ninja cmake \
    && git clone --depth 1 --branch v0.17.1 https://github.com/SHI-Labs/NATTEN.git /tmp/natten \
    && cd /tmp/natten && NATTEN_WITH_CUDA=1 NATTEN_CUDA_ARCH="${NATTEN_CUDA_ARCH}" NATTEN_N_WORKERS="${NATTEN_N_WORKERS}" uv pip install --system --no-cache --no-build-isolation . \
    && python -c 'from natten import libnatten; assert libnatten.has_cuda(), "NATTEN was built without CUDA support"' \
    && rm -rf /tmp/natten
RUN uv pip install --system --no-cache git+https://github.com/CPJKU/madmom
COPY requirements-allin1.txt .
RUN uv pip install --system --no-cache -r requirements-allin1.txt

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

# Health check tuned for orchestrators like Dockhand/Docker
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=12 \
    CMD curl -fsS --max-time 3 http://127.0.0.1:8000/health || exit 1

# Use entrypoint script (auto-downloads models if missing, then starts API)
ENTRYPOINT ["/app/entrypoint.sh"]
