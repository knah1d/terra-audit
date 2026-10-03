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
