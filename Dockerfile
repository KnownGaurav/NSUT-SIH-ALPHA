# ==============================================================================
# Production Dockerfile for Railway ETA FastAPI Backend Service
# Multi-stage lightweight Python container with trained ML models & seed data
# ==============================================================================

FROM python:3.12-slim as base

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies (build essentials for compiling extensions if needed, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source code, models, and data
COPY src/ /app/src/
COPY models/ /app/models/
COPY data/ /app/data/
COPY pytest.ini /app/

# Expose API service port
EXPOSE 8000

# Health check probing /api/health
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Launch production ASGI server via Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
