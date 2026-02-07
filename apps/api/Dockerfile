# syntax=docker/dockerfile:1.7
# apps/api/Dockerfile
#
# CPU-first image for:
# - FastAPI API service
# - One-shot ingest job
# - Alembic migrations (run inside container)
#
# GPU embeddings are handled via a separate CUDA-based image later (recommended).

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps:
# - curl/ca-certificates: healthchecks, debugging, TLS
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better layer caching
COPY requirements.base.txt /app/requirements.base.txt
COPY requirements.cpu.txt /app/requirements.cpu.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && pip install -r /app/requirements.cpu.txt

# Copy the API application code (including alembic files)
COPY . /app/apps/api
COPY curated_tags.txt /app/curated_tags.txt

# Make apps/api the default working directory so `alembic` just works
WORKDIR /app/apps/api

EXPOSE 8000

# Default command for the API container.
# docker-compose can override this for ingest jobs.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
