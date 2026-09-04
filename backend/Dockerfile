# Build context is the repo root (see docker-compose.yml) — this image
# needs both src/ (calculation/pipeline core) and backend/ (the FastAPI
# app that wraps it directly, per CLAUDE.md). Deliberately excludes
# requirements-ui.txt/app.py/Streamlit — this image only ever runs
# `uvicorn backend.main:app`, matching requirements.txt's own doc comment
# and tests/backend/test_no_streamlit_in_api.py's guarantee.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY backend/ backend/

# src/database.py resolves its default SQLite path relative to this file
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
