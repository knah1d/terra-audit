# Local worker for the deployed app

Run from the repository root using the current deployed revision. Your local
`.env` must contain a DATABASE_URL reaching the same Postgres database as the
Render API (an external connection address, not a Render-only internal host)
and the same JWT_SECRET. Keep these in the ignored `.env`, never in commands
or committed documents.

For the current fake explanation pilot:

```bash
source venv/bin/activate
APP_ENV=production FRONTEND_PUBLIC_URL=https://terra-audit.vercel.app AI_PROVIDER=fake python -m backend.worker --job-types ai_explain
```

This overrides only the worker process settings. Set AI_PROVIDER=fake on the
Render API too. The filter prevents this worker from consuming older training
or satellite jobs. The worker still records heartbeats in the shared database.

Keep the terminal open and computer awake. Press Ctrl+C to stop gracefully.
Requests submitted while it is stopped remain pending. No public endpoint,
port forwarding, or tunnel to the computer is required. Verify the worker in
the deployed app's Worker & queue page, then request an explanation.

A real self-hosted provider requires separate model configuration; fake mode
is solely a pipeline check. This document does not claim a worker has started
or that the local database matches the deployed database.

## Satellite analytics and methodology indexing

An explanation-only worker does not process `signal_run` jobs. New fields have
no cached satellite observations, so their first analysis waits for a worker
that accepts that job type. A missing latest-result response is expected until
an analysis completes.

Stop your existing worker with Ctrl+C, then restart it using your current `.env`
provider settings:

```bash
python -m backend.worker --job-types ai_explain signal_run methodology_ingest
```

Satellite processing also requires working Earth Engine credentials on the
worker computer. Existing pending signal jobs become eligible after this
restart; do not submit duplicate runs. The analytics page distinguishes queued,
running, cancellation requested and cancelled states, and offers cancellation.

After updating to the analytics lifecycle implementation, restart the API and
worker so normal startup adds the progress and active-request columns. Matching
active submissions share one job; workers recheck the versioned observation
cache unless live refresh was explicitly requested. Reopening the field restores
its latest active job. The page shows named stages and successful worker timing
details. No percentage estimate is supplied for Earth Engine processing.
