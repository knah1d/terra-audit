# Terra Audit API

FastAPI backend wrapping the existing `src/` calculation/pipeline logic
behind REST endpoints — Part A of `.claude/plans/misty-growing-yao.md`.
Coexists with the Streamlit app (`app.py`) against the same database.

## Run

```bash
source venv/bin/activate
uvicorn backend.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs

Set `JWT_SECRET` in `.env` before running this anywhere but a local
laptop — without it, a loud `UserWarning` fires and an insecure
development-only default is used so `uvicorn` still boots.

## Tests

```bash
pytest tests/backend/ -v
```

Each test runs against an isolated throwaway SQLite file (never the real
`data/project_store.db`) and stubs out `SpatialDataEngine` so no test
requires real Earth Engine credentials — see `tests/backend/conftest.py`.

## Notes

- Every router calls `src.*` directly — nothing under `backend/` forks or
  duplicates calculation/persistence logic.
- `org_id` always comes from the JWT, never from a URL path or request
  body.
- Signal-analytics (GEE fetch) and AI training run as background jobs
  (`background_jobs` table in `src/database.py`) when the DB cache
  misses; a cache hit stays synchronous. See plan Part A4.
