# Durable job worker — operations

Phase 4 replaces in-process `BackgroundTasks` execution (satellite
collection, AI training/benchmark, generic multi-crop monitoring, and
bulk monitoring batches) with a durable, database-backed queue
(`src/jobs.py`) and a separate worker process (`backend/worker.py`).

## Why a database-backed queue, not Celery/Redis/SQS

This app already runs on "one process + SQLite (dev/small deploy) or
Postgres (bigger deploy)" — see `src/jobs.py`'s module docstring for the
full reasoning. Short version: introducing a message broker is real new
infrastructure (another service to deploy and keep available) that
isn't justified at this app's scale. A worker just needs to atomically
claim one pending row — a single `UPDATE ... WHERE status='pending'`
checked by rowcount does that safely on both SQLite and Postgres with no
dialect-specific SQL. The trade-off, stated plainly: workers poll on an
interval (`WORKER_POLL_INTERVAL_SECONDS`, default 2s) rather than
receiving push-based dispatch — acceptable at this app's job volume.

## Running the worker

```sh
# Local / venv
source venv/bin/activate
python -m backend.worker

# docker-compose (a `worker` service is already defined, reusing
# backend/Dockerfile with a different command)
docker compose up worker

# Railway: create a SECOND service in the same project, pointing at this
# same repo/Dockerfile, with a custom start command overriding the
# Dockerfile's default CMD:
#   Start command: python -m backend.worker
# It needs the same environment variables as the `backend` service
# (DATABASE_URL especially — both must point at the SAME database) plus
# EE_PROJECT/EE_SERVICE_ACCOUNT_KEY if it will run signal_run/
# multicrop_monitoring jobs. It does NOT need ALLOWED_ORIGIN_REGEX/
# JWT_SECRET-serving concerns since it never accepts HTTP requests.
```

You can run more than one worker process against the same database —
claiming is race-safe (see `src/jobs.claim_next_job`). Each worker
registers itself in the `workers` table (visible to admins at
`/admin/queue`) and heartbeats every job it's holding.

## Configuration (env vars, all optional with sane defaults)

| Var | Default | Meaning |
|---|---|---|
| `WORKER_POLL_INTERVAL_SECONDS` | `2` | How often an idle worker checks for new work |
| `WORKER_HEARTBEAT_INTERVAL_SECONDS` | `15` | How often a busy worker refreshes its job's heartbeat |
| `MAX_CONCURRENT_JOBS_PER_ORG` | `3` | Per-org running-job cap enforced at claim time |
| `MAX_BULK_MONITORING_ITEMS` | `100` | Max field-seasons per bulk-monitoring batch request |

A job's own `lease_seconds` (default 300) governs abandonment detection:
if a job's heartbeat goes stale past its lease (worker crashed, was
OOM-killed, or was deployed over mid-job), any live worker's next loop
iteration reclaims it via `src.jobs.reclaim_abandoned_jobs()` — retried
if attempts remain, else marked terminally failed.

## Restart / shutdown behavior

- **Worker crash / kill -9**: the job it was holding is reclaimed by
  another (or the same, once restarted) worker once its heartbeat lease
  expires — no manual intervention needed. Its side effects are
  idempotent-per-job (see "Duplicate delivery" below), so reclaiming
  never duplicates a monitoring run.
- **Graceful stop (SIGTERM/SIGINT)**: the worker finishes the job
  currently in hand, deregisters itself, and exits — it does not accept
  new jobs once signaled. `docker compose stop` / a Railway redeploy both
  send SIGTERM first, so this is the normal path.
- **Web app restart**: unaffected — job state lives entirely in the
  database, not in the web process.

## Duplicate delivery / idempotency

Two distinct concerns, both handled:
- **A job row is claimed by two workers at once**: prevented structurally
  — `claim_next_job`'s UPDATE only succeeds for one caller (rowcount
  check), so this can't happen.
- **A job is re-run after a crash mid-execution** (abandoned, reclaimed,
  retried): its non-idempotent side effect (appending a `monitoring_runs`
  record) is guarded by `src.monitoring.append_record_once_per_job`,
  which tags the payload with the job's own id and checks for a prior
  successful append under that same id before creating a second one.
  `signal_run`/`ai_train` are naturally idempotent (cache replace / model
  file overwrite), so no extra guard was needed there.

## Legacy unfinished jobs (pre-Phase-4 deployments)

If you're upgrading a deployment that had `background_jobs` rows from
before Phase 4 (jobs submitted via the old `BackgroundTasks` path):
- Any row still `status='running'` at the moment of upgrade was an
  in-process job whose Python thread no longer exists — it will sit
  `running` forever with `heartbeat_at IS NULL` (that column didn't
  exist pre-Phase-4), so `reclaim_abandoned_jobs()` will **not** pick it
  up automatically (its stale-heartbeat check requires a non-null
  heartbeat). These are cosmetic: their `result`/`error` will never
  populate. If this matters to you, mark them manually:
  `UPDATE background_jobs SET status='error', error='Abandoned by the Phase 4 upgrade' WHERE status='running';`
- Rows already `status IN ('pending','done','error')` are unaffected —
  `pending` ones will be picked up and correctly RUN by the new worker
  the next time it polls (their `payload_json` will be NULL, though,
  since pre-Phase-4 submissions never wrote one — a handler reading a
  legacy pending row raises a clear `InvalidJobRequest` naming the
  missing payload key rather than crashing unhelpfully; in practice,
  submit a fresh request instead of waiting on one of these).

## Streamlit / FastAPI coexistence

`app.py` (the original Streamlit UI) is untouched by Phase 4 and does
**not** use the durable queue — its long-running operations (GEE calls,
AI training) remain synchronous/in-process, exactly as before. This is a
deliberate, bounded scope decision: retrofitting Streamlit's own
execution model onto the new worker architecture is out of scope for
this phase. Both UIs continue to share the same database and the same
`src/*` calculation core; a job queued via the FastAPI+Next.js stack
runs on the worker, while the same operation triggered from the
Streamlit app still blocks that Streamlit session until it completes,
same as it always has.

## Admin visibility

`GET /admin/queue-status` (admin role required) and the `/admin/queue`
page show job counts by status/type, the oldest pending job's age, and
every worker that has ever registered (alive if `stopped_at IS NULL` and
`last_heartbeat_at` is recent).
