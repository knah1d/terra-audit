# Build context is the repo root (see docker-compose.yml) — this image
# needs both src/ (calculation/pipeline core) and backend/ (the FastAPI
# app that wraps it directly). This image runs FastAPI or the durable
# worker and installs only the shared Python requirements.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY backend/ backend/
COPY methodologies/ methodologies/

# src/persistence/database.py resolves its default SQLite path relative to this file
# (repo_root/data/project_store.db) and creates the directory itself —
# /app/data is where docker-compose mounts the persistent volume.
#
# Binds to $PORT when set (Railway assigns this at runtime and routes to
# whatever it is — hardcoding 8000 would only work by Railway guessing
# it from EXPOSE below), falling back to 8000 for docker-compose/local,
# which never sets $PORT. `exec` replaces the shell with uvicorn (PID 1)
# so it actually receives SIGTERM on stop/redeploy instead of the shell
# swallowing it — shell form is only used for the ${PORT:-8000} expansion.
EXPOSE 8000
CMD exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
