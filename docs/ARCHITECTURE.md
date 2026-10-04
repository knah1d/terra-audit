# Terra-Audit architecture

## Where code belongs

```text
frontend/
  app/                     Next.js pages, layouts and authenticated API proxy
  components/
    auth/                  Login/logout and account-recovery UI
    layout/                Shared application shell and navigation
    ui/                    Shared controls and appearance
    fields/, projects/, …  Feature components
  hooks/                   Client data queries, mutations and reusable behavior
  lib/                     Browser/server adapters, validation and formatting
  types/                   API response/request contracts
backend/
  main.py                  FastAPI composition and lifespan
  routers/                 HTTP endpoints and request orchestration
  schemas/                 Pydantic request/response DTOs
  deps.py, access.py        Authentication/authorization dependencies
  config.py, security.py   Runtime settings and JWT adapter
  worker.py                Durable worker entry point and lease lifecycle
  *_job_handlers.py        Worker orchestration using the shared core
src/
  accounts/                Account authentication and recovery primitives
  persistence/
    database.py            Connections, read scopes and shared SQL repositories
    schema.py              Existing SQLite/Postgres schema and migrations
    storage.py             Local/S3 attachment and model storage
  projects/                Project/farm membership, attachments and reviews
  evidence/                Crop seasons, crop taxonomy, soil, production and QA
  methodology/             Document registry/library, corrections and readiness
  carbon/                  Rice/ALM engines, leakage, snapshots and issuance
  signals/                 Earth Engine acquisition, processing and detectors
  jobs/                    Durable queue and signal job coordination
  ai/
    ml/                    Datasets, features, RF/XGBoost training and evaluation
    providers.py           Model-provider adapters
    packets.py, validate.py Deterministic context and explanation validation
    assistant.py, …        Draft explanations, workspace and document assistance
  reporting/               Audit/PDF report generation
  field_types/             Pathway plug-in registration
  paths.py                 Stable project/data/methodology locations
scripts/                   Operational CLIs (backup, users, ingestion, migration)
tests/                     Core and API tests; frontend tests live in frontend/tests
methodologies/             Versioned source documents, not executable code
data/                      Local runtime artifacts (not a code package)
docs/, mid/                Product documentation and historical academic artifacts
```

## Dependency boundaries

Next.js calls FastAPI through its authenticated server proxy. It does not import
Python code. FastAPI routers translate requests, enforce permissions, and call
shared core modules. The worker runs the same calculations and evidence logic.
Core modules do not import FastAPI or frontend code.

The core is grouped by capability rather than by a generic service/repository
class hierarchy. Evidence/project modules keep their existing SQL and business
operations together where splitting them would only add forwarding layers.
Shared connection handling is in persistence; schema setup is separate from
normal queries. These modules create no database at import time.

AI output remains a draft. Deterministic code owns calculations, readiness,
numbers and issuance. ML training is separate from the explanation pipeline.
The frontend query cache remains isolated by organization and user.

## Compatibility and operation

HTTP routes, JSON contracts, table names, migrations, methodology identifiers,
job types and saved model formats are unchanged. No database or stored artifact
is moved. `src.paths` resolves locations relative to the project root, so deeper
packages still use `data/project_store.db`, `data/attachments`, `data/ai_models`,
`methodologies/` and the root `.env`.

Entry points remain:

```bash
uvicorn backend.main:app
python -m backend.worker --job-types ai_explain signal_run methodology_ingest
```

Internal Python imports now use domain packages (for example,
`src.persistence.database`, `src.carbon.alm`, `src.methodology.registry`, and
`src.ai.ml.models`). Repository scripts, tests and CLI examples use those paths.
External scripts importing old flat module names must update their imports.

Vercel hosts Next.js; Render hosts FastAPI; the worker may run locally or on a
separate service. API and worker need the same database and compatible artifact
storage. Deploy/restart the API and worker from the same revision after package
moves. Deployment was not performed by this restructuring.

`backend/config.py` and `frontend/lib/server-config.ts` retain runtime validation.
Set `FRONTEND_PUBLIC_URL` on the API, `BACKEND_URL` on the frontend, and follow
`.env.example` for database, provider, email and storage settings.

## Deliberate limits

Existing calculation formulas, readiness rules and startup migrations were not
rewritten. Introducing a migration framework or splitting every domain operation
into repository/service classes is a separate change, not necessary for these
package moves. Large Next.js feature pages remain intact except for extracting
shared shell/navigation and the browser-only account recovery form.

Historical SRS/presentation documents are retained; they are not current runtime
instructions. The legacy Streamlit runtime is retired. `railway.json` remains an
optional deployment configuration.

## Restructuring verification (2026-10-04)

- Python compileall: passed for src, backend and scripts.
- Python pytest: 143 passed, 28 failed. The unchanged committed baseline
  (f870ebf) also has 143 passed and the exact same 28 failures. These are existing
  leakage/issuance fixture expectations, legacy synchronous-job assumptions and
  an outdated AI action fixture; calculation behavior was not changed to make
  old expectations pass.
- OpenAPI comparison: all 143 paths and request/response schemas match the
  baseline, excluding descriptive prose.
- Rice/ALM engine AST comparison and extracted schema-function comparison:
  unchanged apart from source-location references.
- Frontend TypeScript and existing Node test: passed.
- ESLint: no errors; three pre-existing warnings remain (unused soil plan prop
  and label synchronization effects in Select/DatePicker).
- Production Next.js build: passed with `npm run build -- --webpack`.
  The default Turbopack build was blocked by this execution environment's
  local-port restrictions. The project build configuration was not changed.
- Worker, methodology ingestion, packet-export and backup CLI help commands:
  imports resolve. No operational job or deployment was started.
