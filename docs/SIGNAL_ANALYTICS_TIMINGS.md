# Signal analytics database optimization

The deployed check on 4 October 2026 completed one forced-refresh request for
field 112233, January–May 2026, using the threshold detector. It returned 12
observations and successfully recovered the same job after a page reload.

Measured before this optimization:

| Stage | Seconds |
|---|---:|
| Cache/field check | 0.8577 |
| Earth Engine extraction | 2.0066 |
| Observation persistence and read-back | 5.8527 |
| Analysis | 0.0228 |
| Worker total, including checkpoint overhead | 15.5625 |

This is one observation, not a latency benchmark. Earth Engine and database
latency vary. A separate cached request returned directly without creating a job.

## Changes

- Version checking and reading cached rows use one scoped JOIN query, avoiding
  a separate version SELECT and ensuring both refer to one statement snapshot.
- Cache replacement uses explicit multi-row INSERT batches of at most 100 rows.
  This avoids driver-level per-row executions of SQLAlchemy text executemany.
  Nine binds per row keep batches below SQLite's older 999-variable limit.
- Version upsert, complete-window replacement and inserts stay in one
  transaction. Taking the version-row write lock before replacement serializes
  concurrent writers of the same window on Postgres; SQLite serializes writes.
- The cache writer returns the exact normalized raw columns it commits, ordered
  by date with last-row duplicate semantics. Workers analyze those values without
  a database reload. Smoothing still runs through the same threshold pipeline.
  Both supported database schemas store these numeric columns at double precision.
- The conditional progress UPDATE already checks org/job scope, cancellation,
  status and worker ownership. Stage entry uses that check without a preceding
  redundant cancellation SELECT. Checkpoint durations now appear separately as
  `progress_checkpoints`, including the final pre-publication checkpoint.

The successful result's total includes progress checks and excludes queue waiting
and the final result write. Per-stage times exclude checkpoint publication.
Persisted in-flight progress is a checkpoint snapshot; the completed result has
the final timing totals. Heartbeats, cancellation boundaries, force refresh and
processing-version invalidation remain active.

No schema changes are needed for this optimization. Deploy the code and restart
the worker to use it. No tests, builds, deployment or new satellite requests were
run during this implementation. Measure a fresh run before claiming a speedup.
