"""Scoped satellite request reuse and operational progress; no methodology decisions."""
import hashlib
import json
import uuid

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from src.persistence.database import get_db_connection, is_sqlite
from src.signals.processing import PROCESSING_VERSION


def initialize_tables(conn):
    for column in ("active_request_key", "progress_json"):
        if is_sqlite():
            try:
                conn.execute(text(f"ALTER TABLE background_jobs ADD COLUMN {column} TEXT"))
            except OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
        else:
            conn.execute(text(f"ALTER TABLE background_jobs ADD COLUMN IF NOT EXISTS {column} TEXT"))
    # Historical jobs have a null key and remain intact. Terminal/cancelling
    # jobs release the key so a deliberate new run can be submitted.
    conn.execute(text("""CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_active_request
        ON background_jobs(org_id,job_type,active_request_key)
        WHERE active_request_key IS NOT NULL AND status IN ('pending','running')
              AND cancel_requested=0"""))


def request_key(payload):
    values = {k: payload[k] for k in ("field_id", "window_start", "window_end", "detector", "force_refresh")}
    values["processing_version"] = PROCESSING_VERSION
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def matching_active_job(org_id, payload):
    with get_db_connection() as conn:
        return conn.execute(text("""SELECT job_id FROM background_jobs
            WHERE org_id=:o AND job_type='signal_run' AND active_request_key=:k
              AND status IN ('pending','running') AND cancel_requested=0"""),
                            {"o": org_id, "k": request_key(payload)}).scalar()


def active_jobs(org_id, field_id):
    with get_db_connection() as conn:
        rows = conn.execute(text("""SELECT job_id,payload_json FROM background_jobs
            WHERE org_id=:o AND job_type='signal_run'
              AND status IN ('pending','running','cancel_requested') ORDER BY created_at DESC"""),
                            {"o": org_id}).mappings().all()
    return [{"job_id": row["job_id"], "request": json.loads(row["payload_json"] or "{}")}
            for row in rows if json.loads(row["payload_json"] or "{}").get("field_id") == field_id]


def create_or_reuse(org_id, payload):
    key = request_key(payload)
    # The partial unique index is the cross-process guard; a SELECT alone
    # would allow simultaneous API requests to create duplicates.
    for _ in range(3):
        existing = matching_active_job(org_id, payload)
        if existing:
            return existing
        job_id = uuid.uuid4().hex
        try:
            with get_db_connection() as conn:
                conn.execute(text("""INSERT INTO background_jobs
                    (job_id,org_id,job_type,payload_json,active_request_key)
                    VALUES (:id,:o,'signal_run',:p,:k)"""),
                             {"id": job_id, "o": org_id, "p": json.dumps(payload), "k": key})
                conn.commit()
            return job_id
        except IntegrityError:
            # Winner may have finished between conflict and lookup; retry
            # with a new ID rather than permanently reusing a completed run.
            continue
    raise RuntimeError("Analysis request changed concurrently; please retry")


def update_progress(org_id, job_id, worker_id, stage, timings):
    with get_db_connection() as conn:
        count = conn.execute(text("""UPDATE background_jobs SET progress_json=:p
            WHERE org_id=:o AND job_id=:id AND locked_by=:w
              AND status='running' AND cancel_requested=0"""),
                             {"p": json.dumps({"stage": stage, "timings_seconds": timings}),
                              "o": org_id, "id": job_id, "w": worker_id}).rowcount
        conn.commit()
    if not count:
        from src.jobs.queue import JobCancelled
        raise JobCancelled("Analysis cancelled or worker lease changed")
