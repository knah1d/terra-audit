"""Durable job queue — Phase 4 (see docs/MULTICROP.md and the Phase 1-3
module docstrings this reuses: org-scoped everything, append-only audit
trails, immutable snapshots).

Architecture choice (asked to be explained briefly): a DATABASE-BACKED
queue, not Celery/RQ/Redis/SQS. Reasoning:
  - This app already runs on "one process + SQLite (dev/small deploy) or
    Postgres (bigger deploy)" — see src.database.create_job's original
    docstring, which made the same call for the pre-Phase-4 in-process
    background_jobs table. Introducing a broker is genuinely new
    infrastructure with its own ops burden (another service to deploy,
    monitor, and keep available) that this app's scale does not justify.
  - A worker just needs to reliably claim ONE pending row at a time
    without two workers double-claiming it. That's a single
    `UPDATE ... WHERE status='pending' AND job_id=:id AND status='pending'`
    (checked via rowcount) — which is safe on both SQLite (single-writer,
    already serialized via the WAL+busy_timeout setup in
    src.database.get_db_connection) and Postgres (real MVCC) without any
    dialect-specific SQL (no `SKIP LOCKED`, which SQLite doesn't have).
  - Everything the worker needs (job type, input payload, org scope,
    retry/lease bookkeeping) already fits naturally as columns on a job
    row — no separate broker message format to keep in sync with it.

Trade-off, stated plainly: this does not give sub-second job pickup at
high volume the way a real broker would (workers poll on an interval).
That is an explicit, acceptable cost at this app's scale; if job volume
ever grows enough to need push-based dispatch, swapping the queue
backend behind claim_next_job()/create_job() is a contained change —
callers never touch the table directly.
"""
import json
import platform
import socket
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from src.database import get_db_connection, is_sqlite

STATUSES = {"pending", "running", "done", "error", "cancel_requested", "cancelled"}
# Kept as the exact strings background_jobs already used pre-Phase-4
# (pending/running/done/error) — see backend/routers/signal.py,ai.py and
# frontend/hooks/use-job-poll.ts, which both hardcode "done"/"error".
# "cancel_requested"/"cancelled" are the only new values. Mapping for
# anyone reading Phase 4's own vocabulary: pending=queued, done=succeeded,
# error=failed.
TERMINAL_STATUSES = {"done", "error", "cancelled"}
RETRYABLE = "retryable"
INVALID = "invalid"
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LEASE_SECONDS = 300


class InvalidJobRequest(Exception):
    """Raise from a job handler for a request that retrying cannot fix
    (bad geometry, no satellite coverage, unknown model key, ...) — marks
    the job 'error' immediately with error_kind='invalid', no retry."""


class JobCancelled(Exception):
    """Raise from a job handler once it notices cancel_requested and has
    discarded its (not-yet-published) result — the worker's main loop
    catches this specifically to call mark_cancelled() rather than
    fail_job(), so a deliberate cancellation is never recorded as a
    failure."""


def initialize_tables(conn):
    """background_jobs' shape changed enough (new columns, a widened and
    no-longer-DB-enforced status vocabulary) that pre-Phase-4 rows need a
    real migration, handled here rather than in
    src.database._init_shared_extra_tables (which no longer creates this
    table at all — this function is now its single source of truth,
    called from src.database.initialize_database).

    Three cases, detected explicitly rather than assumed:
      1. Table doesn't exist at all (fresh install) -> create final shape.
      2. Table exists in the pre-Phase-4 shape -> rebuild-and-copy
         (SQLite, mirroring src.database._pk_rebuilds' own
         rename/recreate/copy/drop pattern) or ALTER ADD COLUMN
         (Postgres, which supports IF NOT EXISTS natively).
      3. Table already has the new shape -> no-op.
    """
    if is_sqlite():
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(background_jobs)")).fetchall()]
        if not cols:
            _create_background_jobs_sqlite(conn, if_not_exists=True)
        elif "attempt_count" not in cols:
            conn.execute(text("ALTER TABLE background_jobs RENAME TO background_jobs_old"))
            _create_background_jobs_sqlite(conn, if_not_exists=False)
            conn.execute(text("""
                INSERT INTO background_jobs (job_id, org_id, job_type, status, result_json, error,
                                              created_at, finished_at)
                SELECT job_id, org_id, job_type, status, result_json, error, created_at, finished_at
                FROM background_jobs_old
            """))
            conn.execute(text("DROP TABLE background_jobs_old"))
    else:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS background_jobs (
                job_id           TEXT PRIMARY KEY,
                org_id           TEXT NOT NULL,
                job_type         TEXT NOT NULL,
                status           TEXT NOT NULL DEFAULT 'pending',
                payload_json     TEXT,
                result_json      TEXT,
                error            TEXT,
                error_kind       TEXT,
                attempt_count    INTEGER NOT NULL DEFAULT 0,
                max_attempts     INTEGER NOT NULL DEFAULT 3,
                next_attempt_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                locked_by        TEXT,
                locked_at        TIMESTAMP,
                heartbeat_at     TIMESTAMP,
                lease_seconds    INTEGER NOT NULL DEFAULT 300,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                batch_id         TEXT,
                idempotency_key  TEXT,
                created_at       TIMESTAMPTZ DEFAULT now(),
                finished_at      TIMESTAMPTZ
            )
        """))
        # Idempotent for both a genuinely fresh table (no-op ADDs) and an
        # existing pre-Phase-4 table (real ADDs) — Postgres supports IF
        # NOT EXISTS on both DROP CONSTRAINT and ADD COLUMN natively.
        conn.execute(text("ALTER TABLE background_jobs DROP CONSTRAINT IF EXISTS background_jobs_status_check"))
        for col, ddl in _NEW_COLUMNS:
            conn.execute(text(f"ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS {col} {ddl}"))

    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_background_jobs_org ON background_jobs(org_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_background_jobs_claim ON background_jobs(status, next_attempt_at)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_background_jobs_batch ON background_jobs(org_id, batch_id)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS job_batches (
            org_id         TEXT NOT NULL,
            batch_id       TEXT NOT NULL,
            project_id     TEXT,
            batch_type     TEXT NOT NULL,
            status         TEXT NOT NULL DEFAULT 'running',
            total_children INTEGER NOT NULL DEFAULT 0,
            created_by     TEXT NOT NULL,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, batch_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_job_batches_project ON job_batches(org_id, project_id)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS workers (
            worker_id         TEXT PRIMARY KEY,
            hostname          TEXT NOT NULL,
            pid               INTEGER NOT NULL,
            started_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_heartbeat_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            stopped_at        TIMESTAMP
        )
    """))


_NEW_COLUMNS = [
    ("payload_json", "TEXT"),
    ("error_kind", "TEXT"),
    ("attempt_count", "INTEGER NOT NULL DEFAULT 0"),
    ("max_attempts", "INTEGER NOT NULL DEFAULT 3"),
    ("next_attempt_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ("locked_by", "TEXT"),
    ("locked_at", "TIMESTAMP"),
    ("heartbeat_at", "TIMESTAMP"),
    ("lease_seconds", "INTEGER NOT NULL DEFAULT 300"),
    ("cancel_requested", "INTEGER NOT NULL DEFAULT 0"),
    ("batch_id", "TEXT"),
    ("idempotency_key", "TEXT"),
]


def _create_background_jobs_sqlite(conn, if_not_exists: bool):
    exists_clause = "IF NOT EXISTS " if if_not_exists else ""
    conn.execute(text(f"""
        CREATE TABLE {exists_clause}background_jobs (
            job_id           TEXT PRIMARY KEY,
            org_id           TEXT NOT NULL,
            job_type         TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'pending',
            payload_json     TEXT,
            result_json      TEXT,
            error            TEXT,
            error_kind       TEXT,
            attempt_count    INTEGER NOT NULL DEFAULT 0,
            max_attempts     INTEGER NOT NULL DEFAULT 3,
            next_attempt_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            locked_by        TEXT,
            locked_at        TIMESTAMP,
            heartbeat_at     TIMESTAMP,
            lease_seconds    INTEGER NOT NULL DEFAULT 300,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            batch_id         TEXT,
            idempotency_key  TEXT,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at      TIMESTAMP
        )
    """))


def worker_identity() -> str:
    return f"{socket.gethostname()}:{platform.node()}:{uuid.uuid4().hex[:8]}"


def _now():
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Creating jobs
# --------------------------------------------------------------------------

def create_job(org_id: str, job_type: str, payload: dict, batch_id: str | None = None,
               idempotency_key: str | None = None, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> str:
    """Creates a durable pending job. If idempotency_key is given and a
    job with that (org_id, job_type, idempotency_key) already exists,
    returns the EXISTING job_id instead of creating a second one — a
    retried "start monitoring" click must not double-submit."""
    with get_db_connection() as conn:
        if idempotency_key:
            existing = conn.execute(text("""
                SELECT job_id FROM background_jobs
                WHERE org_id = :org_id AND job_type = :job_type AND idempotency_key = :key
            """), {"org_id": org_id, "job_type": job_type, "key": idempotency_key}).mappings().fetchone()
            if existing is not None:
                return existing["job_id"]

        job_id = uuid.uuid4().hex
        conn.execute(text("""
            INSERT INTO background_jobs (job_id, org_id, job_type, status, payload_json, batch_id,
                                          idempotency_key, max_attempts, next_attempt_at)
            VALUES (:job_id, :org_id, :job_type, 'pending', :payload_json, :batch_id,
                    :idempotency_key, :max_attempts, CURRENT_TIMESTAMP)
        """), {"job_id": job_id, "org_id": org_id, "job_type": job_type,
               "payload_json": json.dumps(payload, default=str), "batch_id": batch_id,
               "idempotency_key": idempotency_key, "max_attempts": max_attempts})
        if batch_id:
            conn.execute(text(
                "UPDATE job_batches SET total_children = total_children + 1 WHERE org_id = :org_id AND batch_id = :batch_id"
            ), {"org_id": org_id, "batch_id": batch_id})
        conn.commit()
    return job_id


# --------------------------------------------------------------------------
# Worker-side: claim / heartbeat / complete / fail / cancel
# --------------------------------------------------------------------------

def claim_next_job(worker_id: str, job_types: list[str] | None = None,
                    max_running_per_org: int | None = None) -> dict | None:
    """Atomically claims ONE pending-and-due job, oldest first. Returns
    None if nothing is claimable. Safe under multiple concurrent workers:
    the UPDATE's WHERE re-checks status='pending', so only one worker's
    UPDATE affects a row (rowcount check below); a lost race just moves
    on to the next candidate."""
    with get_db_connection() as conn:
        query = "SELECT job_id, org_id FROM background_jobs WHERE status = 'pending' AND next_attempt_at <= :now"
        params = {"now": _now().isoformat()}
        if job_types:
            placeholders = ", ".join(f":jt{i}" for i in range(len(job_types)))
            query += f" AND job_type IN ({placeholders})"
            params.update({f"jt{i}": t for i, t in enumerate(job_types)})
        query += " ORDER BY created_at LIMIT 20"
        candidates = conn.execute(text(query), params).mappings().fetchall()

        for candidate in candidates:
            if max_running_per_org is not None:
                running = conn.execute(text(
                    "SELECT COUNT(*) FROM background_jobs WHERE org_id = :org_id AND status = 'running'"
                ), {"org_id": candidate["org_id"]}).scalar()
                if running >= max_running_per_org:
                    continue
            result = conn.execute(text("""
                UPDATE background_jobs SET status = 'running', locked_by = :worker_id,
                    locked_at = CURRENT_TIMESTAMP, heartbeat_at = CURRENT_TIMESTAMP,
                    attempt_count = attempt_count + 1
                WHERE job_id = :job_id AND status = 'pending'
            """), {"worker_id": worker_id, "job_id": candidate["job_id"]})
            if result.rowcount == 1:
                conn.commit()
                return get_job_row(candidate["org_id"], candidate["job_id"])
        conn.commit()
    return None


def heartbeat(org_id: str, job_id: str) -> bool:
    """Returns False if the job no longer belongs to this worker's lease
    (e.g. it was reclaimed as abandoned) — a handler should stop and
    discard its result rather than publish anything if this ever happens."""
    with get_db_connection() as conn:
        result = conn.execute(text("""
            UPDATE background_jobs SET heartbeat_at = CURRENT_TIMESTAMP
            WHERE org_id = :org_id AND job_id = :job_id AND status = 'running'
        """), {"org_id": org_id, "job_id": job_id})
        conn.commit()
    return result.rowcount == 1


def is_cancel_requested(org_id: str, job_id: str) -> bool:
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT cancel_requested FROM background_jobs WHERE org_id = :org_id AND job_id = :job_id"
        ), {"org_id": org_id, "job_id": job_id}).mappings().fetchone()
    return bool(row and row["cancel_requested"])


def complete_job(org_id: str, job_id: str, result: dict) -> None:
    with get_db_connection() as conn:
        conn.execute(text("""
            UPDATE background_jobs SET status = 'done', result_json = :result, finished_at = CURRENT_TIMESTAMP
            WHERE org_id = :org_id AND job_id = :job_id
        """), {"result": json.dumps(result, default=str), "org_id": org_id, "job_id": job_id})
        conn.commit()
    _maybe_finalize_batch(org_id, job_id)


def mark_cancelled(org_id: str, job_id: str, note: str = "Cancelled before publishing a result") -> None:
    with get_db_connection() as conn:
        conn.execute(text("""
            UPDATE background_jobs SET status = 'cancelled', error = :note, finished_at = CURRENT_TIMESTAMP
            WHERE org_id = :org_id AND job_id = :job_id
        """), {"note": note, "org_id": org_id, "job_id": job_id})
        conn.commit()
    _maybe_finalize_batch(org_id, job_id)


def fail_job(org_id: str, job_id: str, error: str, error_kind: str = RETRYABLE) -> None:
    """Retries (back to 'pending', with exponential-ish backoff) if
    error_kind is 'retryable' and attempts remain; otherwise terminal
    'error'. An 'invalid' error never retries regardless of attempts
    left — retrying a bad request just wastes another attempt."""
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT attempt_count, max_attempts, cancel_requested FROM background_jobs "
            "WHERE org_id = :org_id AND job_id = :job_id"
        ), {"org_id": org_id, "job_id": job_id}).mappings().fetchone()
        if row is None:
            return
        will_retry = (
            error_kind == RETRYABLE and not row["cancel_requested"]
            and row["attempt_count"] < row["max_attempts"]
        )
        if will_retry:
            backoff = min(300, 15 * (2 ** (row["attempt_count"] - 1)))
            conn.execute(text("""
                UPDATE background_jobs SET status = 'pending', error = :error, error_kind = :error_kind,
                    next_attempt_at = :next_attempt_at, locked_by = NULL, locked_at = NULL, heartbeat_at = NULL
                WHERE org_id = :org_id AND job_id = :job_id
            """), {"error": error, "error_kind": error_kind,
                   "next_attempt_at": (_now() + timedelta(seconds=backoff)).isoformat(),
                   "org_id": org_id, "job_id": job_id})
        else:
            final_status = "cancelled" if row["cancel_requested"] else "error"
            conn.execute(text("""
                UPDATE background_jobs SET status = :status, error = :error, error_kind = :error_kind,
                    finished_at = CURRENT_TIMESTAMP
                WHERE org_id = :org_id AND job_id = :job_id
            """), {"status": final_status, "error": error, "error_kind": error_kind,
                   "org_id": org_id, "job_id": job_id})
        conn.commit()
    if not will_retry:
        _maybe_finalize_batch(org_id, job_id)


def request_cancel(org_id: str, job_id: str) -> bool:
    """Marks the job for cancellation. A 'pending' job is cancelled
    immediately (it never started). A 'running' job keeps running — its
    handler must check is_cancel_requested() and, on the next safe
    checkpoint, discard its result and call mark_cancelled() instead of
    complete_job(). This function never claims to have stopped an
    in-flight external call — see this module's docstring."""
    with get_db_connection() as conn:
        pending = conn.execute(text("""
            UPDATE background_jobs SET status = 'cancelled', finished_at = CURRENT_TIMESTAMP,
                error = 'Cancelled before it started'
            WHERE org_id = :org_id AND job_id = :job_id AND status = 'pending'
        """), {"org_id": org_id, "job_id": job_id})
        if pending.rowcount == 0:
            conn.execute(text("""
                UPDATE background_jobs SET cancel_requested = 1, status = 'cancel_requested'
                WHERE org_id = :org_id AND job_id = :job_id AND status = 'running'
            """), {"org_id": org_id, "job_id": job_id})
        conn.commit()
    if pending.rowcount:
        _maybe_finalize_batch(org_id, job_id)
    return True


def reclaim_abandoned_jobs() -> int:
    """Sweeps 'running' jobs whose heartbeat has gone stale past their
    lease — the worker that held them is presumed dead (crashed, OOM-
    killed, deployed over). Requeues them through the same fail_job()
    retry/terminal logic used for a normal failure, so attempt limits and
    cancellation are honored identically either way. Returns how many
    were reclaimed. Meant to be called periodically by any live worker's
    main loop, not just at startup — a worker can die at any time."""
    with get_db_connection() as conn:
        stale = conn.execute(text("""
            SELECT job_id, org_id FROM background_jobs
            WHERE status IN ('running', 'cancel_requested')
              AND heartbeat_at IS NOT NULL
        """)).mappings().fetchall()
    reclaimed = 0
    now = _now()
    for row in stale:
        job = get_job_row(row["org_id"], row["job_id"])
        if job is None or job["heartbeat_at"] is None:
            continue
        hb = job["heartbeat_at"]
        if isinstance(hb, str):
            hb = datetime.fromisoformat(hb.replace(" ", "T"))
        if hb.tzinfo is None:
            hb = hb.replace(tzinfo=timezone.utc)
        if (now - hb).total_seconds() > (job["lease_seconds"] or DEFAULT_LEASE_SECONDS):
            fail_job(row["org_id"], row["job_id"],
                      "Worker heartbeat lost — job abandoned and reclaimed", RETRYABLE)
            reclaimed += 1
    return reclaimed


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def get_job_row(org_id: str, job_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM background_jobs WHERE org_id = :org_id AND job_id = :job_id"
        ), {"org_id": org_id, "job_id": job_id}).mappings().fetchone()
    if row is None:
        return None
    result = dict(row)
    result["payload"] = json.loads(result["payload_json"]) if result.get("payload_json") else {}
    result["result"] = json.loads(result["result_json"]) if result.get("result_json") else None
    return result


def list_batch_jobs(org_id: str, batch_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text(
            "SELECT * FROM background_jobs WHERE org_id = :org_id AND batch_id = :batch_id ORDER BY created_at"
        ), {"org_id": org_id, "batch_id": batch_id}).mappings().fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["payload"] = json.loads(d["payload_json"]) if d.get("payload_json") else {}
        d["result"] = json.loads(d["result_json"]) if d.get("result_json") else None
        out.append(d)
    return out


# --------------------------------------------------------------------------
# Batches
# --------------------------------------------------------------------------

def create_batch(org_id: str, project_id: str | None, batch_type: str, created_by: str) -> str:
    batch_id = uuid.uuid4().hex
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO job_batches (org_id, batch_id, project_id, batch_type, created_by)
            VALUES (:org_id, :batch_id, :project_id, :batch_type, :created_by)
        """), {"org_id": org_id, "batch_id": batch_id, "project_id": project_id,
               "batch_type": batch_type, "created_by": created_by})
        conn.commit()
    return batch_id


def get_batch(org_id: str, batch_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM job_batches WHERE org_id = :org_id AND batch_id = :batch_id"
        ), {"org_id": org_id, "batch_id": batch_id}).mappings().fetchone()
    return dict(row) if row else None


def list_batches(org_id: str, project_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM job_batches WHERE org_id = :org_id"
    params = {"org_id": org_id}
    if project_id is not None:
        query += " AND project_id = :project_id"
        params["project_id"] = project_id
    query += " ORDER BY created_at DESC"
    with get_db_connection() as conn:
        rows = conn.execute(text(query), params).mappings().fetchall()
    return [dict(r) for r in rows]


def _maybe_finalize_batch(org_id: str, job_id: str) -> None:
    """Flips a batch to 'completed'/'partial_failure'/'cancelled' once
    every child has reached a terminal state — checked opportunistically
    whenever a child finishes rather than via a separate poller."""
    job = get_job_row(org_id, job_id)
    if job is None or not job.get("batch_id"):
        return
    children = list_batch_jobs(org_id, job["batch_id"])
    if any(c["status"] not in TERMINAL_STATUSES for c in children):
        return
    if all(c["status"] == "cancelled" for c in children):
        final = "cancelled"
    elif any(c["status"] == "error" for c in children):
        final = "partial_failure" if any(c["status"] == "done" for c in children) else "failed"
    else:
        final = "completed"
    with get_db_connection() as conn:
        conn.execute(text(
            "UPDATE job_batches SET status = :status WHERE org_id = :org_id AND batch_id = :batch_id"
        ), {"status": final, "org_id": org_id, "batch_id": job["batch_id"]})
        conn.commit()


def batch_progress(org_id: str, batch_id: str) -> dict:
    children = list_batch_jobs(org_id, batch_id)
    by_status = {}
    for c in children:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    return {"total": len(children), "by_status": by_status, "children": children}


# --------------------------------------------------------------------------
# Worker registry (admin visibility)
# --------------------------------------------------------------------------

def register_worker(worker_id: str, hostname: str, pid: int) -> None:
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO workers (worker_id, hostname, pid) VALUES (:worker_id, :hostname, :pid)
        """), {"worker_id": worker_id, "hostname": hostname, "pid": pid})
        conn.commit()


def heartbeat_worker(worker_id: str) -> None:
    with get_db_connection() as conn:
        conn.execute(text(
            "UPDATE workers SET last_heartbeat_at = CURRENT_TIMESTAMP WHERE worker_id = :worker_id"
        ), {"worker_id": worker_id})
        conn.commit()


def deregister_worker(worker_id: str) -> None:
    with get_db_connection() as conn:
        conn.execute(text(
            "UPDATE workers SET stopped_at = CURRENT_TIMESTAMP WHERE worker_id = :worker_id"
        ), {"worker_id": worker_id})
        conn.commit()


def list_workers() -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text("SELECT * FROM workers ORDER BY started_at DESC LIMIT 50")).mappings().fetchall()
    return [dict(r) for r in rows]


def queue_status() -> dict:
    """Org-agnostic operational view for admins (counts across all
    orgs — this is infra health, not tenant data, so it deliberately
    isn't org-scoped the way every other query in this app is)."""
    with get_db_connection() as conn:
        by_status = conn.execute(text(
            "SELECT status, COUNT(*) AS n FROM background_jobs GROUP BY status"
        )).mappings().fetchall()
        by_type = conn.execute(text(
            "SELECT job_type, status, COUNT(*) AS n FROM background_jobs GROUP BY job_type, status"
        )).mappings().fetchall()
        oldest_pending = conn.execute(text(
            "SELECT MIN(created_at) FROM background_jobs WHERE status = 'pending'"
        )).scalar()
    return {
        "by_status": {r["status"]: r["n"] for r in by_status},
        "by_type": [dict(r) for r in by_type],
        "oldest_pending_since": oldest_pending,
        "workers": list_workers(),
    }
