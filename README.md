# Terra Audit

Turns satellite/field data into verifiable carbon credits for two Verra
methodologies:

- **VM0051** (rice AWD — Alternate Wetting & Drying) — driven by Sentinel-1
  SAR backscatter from Google Earth Engine, detecting flood/drydown cycles.
- **VM0042** (cropland Improved Agricultural Land Management) — driven by
  manually entered practice-schedule and lab-measured soil organic carbon
  (SOC) data; no satellite signal.

Primary geographic focus is Bangladesh/South Asia. Field types are
pluggable (`src/field_types/`), so a third methodology can be added
without reworking the first two.

## Two UIs, one calculation core

This repo currently ships **two** frontends against the **same** `src/`
calculation/pipeline logic and the same database — a Streamlit app
(the original, still fully featured) and a newer FastAPI + Next.js
stack (`backend/` + `frontend/`). Nothing under `backend/` forks or
duplicates `src/*` logic; every router calls it directly.

```
src/                    ← calculation engines, SAR pipeline, AI models, DB (shared by both UIs)
app.py                  ← Streamlit UI (original)
backend/                ← FastAPI REST API
frontend/               ← Next.js UI (talks to backend/, not to src/ directly)
```

## Setup

```bash
# Python side (Streamlit app + FastAPI backend)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt        # full stack, incl. Streamlit
# or, for an API-only deployment that never renders Streamlit:
pip install -r requirements-ui.txt

# One-time Earth Engine auth (needed for the SAR pipeline / signal-analytics)
earthengine authenticate
earthengine set_project <GCP_PROJECT_ID>

# Frontend
cd frontend && npm install
```

Create a `.env` in the project root:

```
EE_PROJECT=your-gcp-project-id
JWT_SECRET=some-long-random-string        # required for the FastAPI backend
```

Optional: `DATABASE_URL` (e.g. `postgresql+psycopg2://user:pass@host:5432/dbname`)
points `src/database.py` at Postgres instead of the default local SQLite
file (`data/project_store.db`). See `backend/README.md` for SMTP/OTP
registration-email settings.

## Running it

**Streamlit app** (original UI):

```bash
source venv/bin/activate
streamlit run app.py
# http://localhost:8501
```

**FastAPI + Next.js** (newer stack):

```bash
source venv/bin/activate
uvicorn backend.main:app --reload      # http://127.0.0.1:8000, Swagger at /docs

cd frontend
npm run dev                            # http://localhost:3000
```

Both UIs can run against the same database at the same time.

## Tests

```bash
# Calculation engines (pure logic, no Streamlit/GEE dependency)
pytest tests/test_carbon_calculator.py tests/test_carbon_calculator_alm.py

# FastAPI backend (isolated throwaway SQLite per test, GEE stubbed out)
pytest tests/backend/ -v

# everything
pytest

# Frontend
cd frontend
npx tsc --noEmit
npx eslint .
npm run build
```

## Architecture pointers

- **Pluggable field types** — `src/field_types/registry.py` maps a
  `field_type` key to a detector + methodology engine + `uses_sar` flag.
  `field_type` is immutable after a field is registered.
- **Carbon engines** — `src/carbon_calculator.py` (VM0051, rice AWD) and
  `src/carbon_calculator_alm.py` (VM0042, cropland ALM) — see their module
  docstrings for exact scope/exclusions before changing an emission factor.
- **SAR pipeline** — `src/data_engine.py` (Earth Engine query) →
  `src/threshold_gate.py` (rule-based AWD/phenology detection) →
  optionally `src/ai/` (Random Forest/XGBoost trained to reproduce the
  Threshold Gate's own labels — not an independent accuracy check).
- **Database** — `src/database.py`, SQLAlchemy Core, multi-tenant
  (`org_id` is the first parameter of every public function).
- **Reports/exports** — `src/report_generator.py` (PDF/JSON/CSV evidence
  packages), exposed over the API at `GET /fields/{id}/export/{pdf,json,csv}`.
- Full details, key design constraints, and file-by-file architecture
  notes live in `CLAUDE.md`.

See `backend/README.md` for FastAPI-specific notes (auth, background
jobs, self-serve signup).
