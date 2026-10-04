# Project review and analytics lifecycle implementation — 4 October 2026

## Three review passes

1. Architecture and operations: reviewed the current FastAPI/Next.js boundaries,
   shared database queue, cache read/write paths, worker selection, and deployed
   queue records. The durable worker remains suitable for the current workflow.
2. Methodology and processing: reviewed local VM0051 extraction, the registered
   methodology inventory, leakage implementation scope and AI evaluation status;
   checked official Verra and Earth Engine pages. This is a focused source/code
   review, not a complete numerical reconciliation of every methodology PDF.
3. Lifecycle and concurrency: reviewed request creation, cache reuse, cancellation,
   tenant/field scoping, refresh recovery, startup migrations and worker progress.
   Final queue read at 14:34 UTC: 18 completed satellite jobs, no pending satellite
   jobs, and no live registered worker. The latest worker had been stopped.

## Findings

- A worker accepting only `ai_explain` cannot run satellite jobs. Earlier waits
  were dominated by queue time. The subsequently completed live fetches took
  approximately 13–15 seconds of worker processing; individual stages were not
  previously recorded.
- Cache reads and writes use the current processing version. There was no
  confirmed version mismatch. The confirmed gap was unconditional live fetching
  inside the queued handler, even if another request had populated the cache.
- Duplicate prevention needed a database constraint rather than a SELECT alone.
- The page stored active job IDs only in component state, losing them on reload.
- Earth Engine `getInfo()` blocks until the result returns. Progress must expose
  this wait without pretending to know a completion percentage.

## Implemented analytics changes

- New `src/jobs/signals.py` centralizes request identities, active-job retrieval,
  atomic active-job reuse and lease-scoped progress publication.
- Additive `active_request_key` and `progress_json` columns are created by the
  existing startup initializer on SQLite and Postgres. A partial unique index
  prevents simultaneous equivalent active requests. Historical null-key jobs
  remain untouched; no existing job is deleted or retroactively merged.
- Request identity includes field, dates, detector, explicit refresh choice and
  processing version, with organization scoping in the database constraint.
  Completed/failed/cancelled runs do not permanently prevent another request.
- Workers check versioned observations before fetching. Explicit force refresh
  continues to request live data. Cached processing works without a live Earth
  Engine instance; a cache miss still requires configured worker credentials.
- Active-job recovery uses an authenticated, field-scoped endpoint. Reopening a
  field restores the latest active request's dates, detector and refresh choice.
  Switching fields remounts the view to avoid carrying another field's state.
- Named stages and monotonic timings cover cache checking, live extraction,
  observation persistence and analysis. The UI exposes the current stage and
  successful result timings. Queue wait and final result write are excluded
  from displayed stage totals. Failed-stage timing is in worker logs; the
  persisted progress records the last published checkpoint.
- Invalid detectors and invalid/non-ordered ISO date windows are rejected.

No satellite thresholds, 10-metre reduction resolution, carbon equations,
readiness decisions, provider configuration or methodology bundle were changed.
Cancellation during a blocking Earth Engine request remains cooperative: the
worker checks cancellation once that request returns.

## Broader remaining work

- Methodology library: finish bundle-wide indexing and improve section/equation
  ranking, range parsing and correction-aware context coverage.
- Explanations: improve wording and citation inspection. Citation provenance and
  numeric validation do not prove semantic entailment.
- Evaluation: the 20 builder-generated frozen cases remain unprepared and no
  full provider quality result can be claimed.
- Accounting: the documented displacement-leakage adapter still limits projects
  to one field, and multi-year SOC uncertainty remains explicitly blocked.
- Deployment/operations: a local worker needs the same database as the API and
  must stay awake. An architecture review is not a backup restoration or
  deployment availability check.

## Startup and verification ownership

Deploy the API and frontend from the same revision, then restart the worker:

```bash
python -m backend.worker --job-types ai_explain signal_run methodology_ingest
```

Startup applies the additive migration; no separate migration was run during
implementation. The user owns runtime testing and deployment. Review duplicate
clicks, refresh during a queued/running request, cancellation, a cache hit after
another job finishes, explicit force refresh, and cross-organization access.

No tests, builds, compilation, deployment or new satellite runs were executed.
Source diffs and whitespace were inspected. Actual speed gains from these new
changes remain unmeasured.

## Official sources checked

- Earth Engine processing environments:
  https://developers.google.com/earth-engine/guides/processing_environments
- Earth Engine client/server behavior and blocking `getInfo()`:
  https://developers.google.com/earth-engine/guides/client_server
- Earth Engine quotas and caching redundant requests:
  https://developers.google.com/earth-engine/guides/usage
- Verra VM0051 v1.1, active since 14 July 2026; flooded rice scope and
  version-transition conditions:
  https://verra.org/methodologies/vm0051-improved-management-in-rice-production-systems-v1-1/
