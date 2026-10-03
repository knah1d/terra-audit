# Terra-Audit architecture

## Supported runtime

- Vercel: Next.js frontend and authenticated API proxy.
- Render: FastAPI service and a separate durable job worker.
- Shared Python core: calculation engines, methodology rules, project evidence,
  snapshots, and persistence under `src/`.
- API and worker must use the same database and compatible attachment storage.

The Streamlit dashboard, session helpers, theme, and UI requirements were
retired. Historical SRS and presentation artifacts retain their original
architecture descriptions; they are not current setup instructions.
`railway.json` remains an optional legacy deployment configuration, not the
configuration for the current Render service.

## Dependency boundaries

Next.js calls FastAPI through its proxy; it never imports Python modules.
FastAPI routers and workers reuse the core rather than implementing alternate
calculation equations. Core calculation modules must remain independent of
HTTP and UI frameworks. Authorization is enforced by the backend, including
organization, project, and active-field checks. Frontend session claims only
control display; they do not grant access.

The frontend query cache is isolated by organization and user. Login/logout
replace the document, and logout cancels queries and clears cached account data.

AI output is a draft explanation. Deterministic code owns numbers, readiness,
and issuance decisions. Preserve this boundary in future refactors.

## Deployment configuration

Set `FRONTEND_PUBLIC_URL` on the Render API to the public HTTPS frontend origin
for account invitation and recovery links. Set `BACKEND_URL` on Vercel to the
backend origin. Localhost defaults are for development only. Follow
`.env.example` for database, email, storage, and provider settings.

## Incremental reorganization roadmap

Completed: remove the legacy Streamlit runtime files and correct the primary
setup and operations documentation. Existing calculation modules and import
paths remain stable.

Next, centralize deployment configuration validation and introduce versioned
migrations. Inventory every existing initializer and establish a baseline for
existing SQLite and Postgres databases before replacing startup DDL. Do not
create a parallel migration system that leaves startup migrations competing
with it. Production URL validation needs an explicit environment policy;
never infer the public frontend origin from untrusted request headers.

Then group Python modules incrementally into `src/methodology/`,
`src/evidence/`, `src/calculations/`, and `src/persistence/`. `src/ai/` and
`src/field_types/` already have useful boundaries. Move one group per change,
update API/worker/script/test imports, and check persisted handler names,
paths, registry identifiers, and database locations before removing any
compatibility imports. A directory move must not change methodology outputs
or relocate an existing database.

Keep Next.js route files in `frontend/app/`; extract substantial feature
components into the existing `components/` and `hooks/` directories as needed.
Do not add a second parallel frontend organization just for naming symmetry.

No Python module moves, migration replacement, or deployment have been
performed by this cleanup. Verification remains the user's responsibility.
