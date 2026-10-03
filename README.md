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

The Next.js **Crop Seasons** workspace adds multi-crop season records, sourced
field observations and independent review, shared Sentinel-1/Sentinel-2
observation snapshots, and a field-isolated RF/XGBoost crop benchmark to both
accounting pathways. It is a research pilot, not a validated classifier for
every crop. See [multi-crop scope and workflow](docs/MULTICROP.md).

## Architecture

The supported application is Next.js + FastAPI. Next.js calls the API
through its server-side proxy; FastAPI and the durable job worker reuse
`src/` for calculations, evidence, methodology rules, and persistence.
The legacy Streamlit UI has been retired.

```text
frontend/               Next.js pages, components, hooks, API proxy
backend/                FastAPI routes, schemas, authorization, worker
src/                    Shared Python application and calculation core
methodologies/          Source methodology documents
scripts/                Operational tools
tests/                  Backend, core, and frontend verification fixtures
docs/                   Product, methodology, and operations documentation
```

Production uses Vercel for the frontend and Render for the backend.
See [architecture and cleanup roadmap](docs/ARCHITECTURE.md).

## Setup

```bash
# Python API and worker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

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
FRONTEND_PUBLIC_URL=https://your-app.vercel.app  # Render backend: account links
```

Optional: `DATABASE_URL` (e.g. `postgresql+psycopg2://user:pass@host:5432/dbname`)
points `src/database.py` at Postgres instead of the default local SQLite
file (`data/project_store.db`). See `backend/README.md` for Brevo/OTP
registration-email settings.

## Running it

```bash
source venv/bin/activate
uvicorn backend.main:app --reload      # http://127.0.0.1:8000, Swagger at /docs

cd frontend
npm run dev                            # http://localhost:3000
```

Run the durable worker separately with `python -m backend.worker` for queued jobs.

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
