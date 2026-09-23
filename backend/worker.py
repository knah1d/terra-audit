"""Durable job worker — Phase 4. Runs OUT OF PROCESS from the FastAPI web
app (backend.main:app); the two communicate only through the
background_jobs table (src.jobs), never in-memory.

Run with:  python -m backend.worker
Stop with: SIGINT/SIGTERM (graceful — finishes the job currently in
hand, then deregisters and exits; does not accept new jobs once signaled).

See docs/OPERATIONS.md for deployment instructions (separate Railway
service / docker-compose service, env vars, restart behavior).
"""
import logging
import os
import signal
import socket
import sys
import threading
import time

from backend.config import (
    MAX_CONCURRENT_JOBS_PER_ORG, WORKER_HEARTBEAT_INTERVAL_SECONDS, WORKER_POLL_INTERVAL_SECONDS,
)
from backend.job_handlers import HANDLERS
from src.database import initialize_database
from src.jobs import (
    JobCancelled, InvalidJobRequest, claim_next_job, complete_job, deregister_worker, fail_job,
    get_job_row, heartbeat, heartbeat_worker, is_cancel_requested, mark_cancelled,
    reclaim_abandoned_jobs, register_worker, worker_identity,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(message)s")
log = logging.getLogger("worker")

# Never log payload/result contents verbatim — they can carry field
# geometry and other org-internal data. Only identifiers and short,
# truncated error text are logged.
_MAX_LOGGED_ERROR_CHARS = 300


class WorkerContext:
    """Passed to every handler in backend/job_handlers.py. `engine` is
    built once per worker process (mirrors backend/main.py's lifespan
    building one SpatialDataEngine per web process) — never recreated
    per job."""
    def __init__(self, job: dict, engine):
        self._org_id = job["org_id"]
        self._job_id = job["job_id"]
        self.engine = engine

    def heartbeat(self) -> None:
        heartbeat(self._org_id, self._job_id)

    def cancel_requested(self) -> bool:
        return is_cancel_requested(self._org_id, self._job_id)


class _HeartbeatThread(threading.Thread):
    """Keeps a job's heartbeat_at fresh WHILE its handler is blocked on a
    single long synchronous call (e.g. Earth Engine) — without this, a
    genuinely slow-but-alive job would look abandoned to
    reclaim_abandoned_jobs() and get reclaimed out from under itself."""
    def __init__(self, ctx: WorkerContext, interval: float):
        super().__init__(daemon=True)
        self._ctx = ctx
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.wait(self._interval):
            self._ctx.heartbeat()

    def stop(self):
        self._stop_event.set()


def _run_one(job: dict, engine) -> None:
    org_id, job_id, job_type = job["org_id"], job["job_id"], job["job_type"]
    handler = HANDLERS.get(job_type)
    if handler is None:
        fail_job(org_id, job_id, f"Unknown job_type {job_type!r}", "invalid")
        return

    ctx = WorkerContext(job, engine)
    hb_thread = _HeartbeatThread(ctx, WORKER_HEARTBEAT_INTERVAL_SECONDS)
    hb_thread.start()
    try:
        result = handler(job, ctx)
        complete_job(org_id, job_id, result)
        log.info("job %s (%s) done", job_id, job_type)
    except JobCancelled as exc:
        mark_cancelled(org_id, job_id, str(exc)[:_MAX_LOGGED_ERROR_CHARS])
        log.info("job %s (%s) cancelled", job_id, job_type)
    except InvalidJobRequest as exc:
        fail_job(org_id, job_id, str(exc)[:_MAX_LOGGED_ERROR_CHARS], "invalid")
        log.warning("job %s (%s) invalid: %s", job_id, job_type, str(exc)[:_MAX_LOGGED_ERROR_CHARS])
        _maybe_notify_exhausted(org_id, job_id)
    except KeyError as exc:
        # A required payload key is missing — never fixable by retrying
        # (e.g. a pre-Phase-4 legacy job row with no payload_json at all;
        # see docs/OPERATIONS.md's "Legacy unfinished jobs" section).
        msg = f"Malformed or legacy job payload — missing key {exc}"
        fail_job(org_id, job_id, msg, "invalid")
        log.warning("job %s (%s) invalid: %s", job_id, job_type, msg)
        _maybe_notify_exhausted(org_id, job_id)
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any other failure is retryable
        fail_job(org_id, job_id, str(exc)[:_MAX_LOGGED_ERROR_CHARS], "retryable")
        log.warning("job %s (%s) failed (retryable): %s", job_id, job_type, str(exc)[:_MAX_LOGGED_ERROR_CHARS])
        _maybe_notify_exhausted(org_id, job_id)
    finally:
        hb_thread.stop()


def _maybe_notify_exhausted(org_id: str, job_id: str) -> None:
    job = get_job_row(org_id, job_id)
    if job is None or job["status"] != "error":
        return  # still retrying — only notify once attempts are truly exhausted
    requested_by = (job.get("payload") or {}).get("requested_by")
    if requested_by:
        from src import reviews as reviews_db
        reviews_db.notify(
            org_id, requested_by, "job_retries_exhausted",
            f"A {job['job_type']} job failed after {job['attempt_count']} attempt(s) and will not retry further.",
        )


def run(job_types=None, max_iterations: int | None = None) -> None:
    """max_iterations is used by tests/manual runs that want the worker
    to process what's queued and then return, instead of polling
    forever."""
    initialize_database()
    from src.data_engine import SpatialDataEngine
    try:
        engine = SpatialDataEngine()
    except RuntimeError as exc:
        engine = None
        log.warning("Earth Engine not initialized (%s) — signal_run/multicrop_monitoring jobs will fail "
                    "with a retryable error until this is fixed.", exc)

    worker_id = worker_identity()
    register_worker(worker_id, socket.gethostname(), os.getpid())
    log.info("worker %s started (pid %s)", worker_id, os.getpid())

    stop = threading.Event()

    def _handle_signal(signum, _frame):
        log.info("received signal %s — finishing current job, then exiting", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    iterations = 0
    try:
        while not stop.is_set():
            reclaim_abandoned_jobs()
            job = claim_next_job(worker_id, job_types=job_types, max_running_per_org=MAX_CONCURRENT_JOBS_PER_ORG)
            if job is None:
                heartbeat_worker(worker_id)
                if max_iterations is not None:
                    iterations += 1
                    if iterations >= max_iterations:
                        break
                stop.wait(WORKER_POLL_INTERVAL_SECONDS)
                continue
            _run_one(job, engine)
            heartbeat_worker(worker_id)
    finally:
        deregister_worker(worker_id)
        log.info("worker %s stopped", worker_id)


if __name__ == "__main__":
    run()
    sys.exit(0)
