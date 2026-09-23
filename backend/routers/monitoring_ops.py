"""Bulk monitoring, the project monitoring dashboard, data-quality
issues, and admin queue visibility — Phase 4.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from backend.config import MAX_BULK_MONITORING_ITEMS
from backend.deps import get_current_user, require_admin, require_writer
from backend.schemas.monitoring_ops import BulkMonitoringRequest, IssueDecision, IssueResolve, RetryFailedRequest
from src import jobs as jobs_db
from src import monitoring
from src import monitoring_ops
from src import projects as projects_db
from backend.access import require_project_access
from src.database import get_field
from src.processing import MULTICROP_VERSION

router = APIRouter(tags=["monitoring-ops"])


def _owned_batch(org_id: str, batch_id: str) -> dict:
    batch = jobs_db.get_batch(org_id, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    return batch


@router.post("/projects/{project_id}/monitoring/bulk-run", status_code=status.HTTP_202_ACCEPTED)
def bulk_run_monitoring(project_id: str, body: BulkMonitoringRequest, user=Depends(require_writer)):
    """Creates one batch + one independently tracked child job per
    selected field-season. Bulk actions are restricted to project
    members (or org admins) — never a bare org-writer check alone."""
    org_id = user["org_id"]
    require_project_access(org_id, project_id, user)
    if projects_db.get_project(org_id, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if len(body.field_seasons) > MAX_BULK_MONITORING_ITEMS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"At most {MAX_BULK_MONITORING_ITEMS} field-seasons per batch (got {len(body.field_seasons)}).",
        )

    open_field_ids = {m["field_id"] for m in projects_db.list_project_fields(org_id, project_id)
                       if m["removed_at"] is None}

    # Validate every pair BEFORE creating anything — a partially-invalid
    # batch request should fail cleanly, not create a batch with some
    # children silently skipped.
    resolved = []
    for pair in body.field_seasons:
        if pair.field_id not in open_field_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Field {pair.field_id!r} is not currently assigned to this project.",
            )
        field = get_field(org_id, pair.field_id)
        if field is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Field {pair.field_id!r} not found")
        season = monitoring.season(org_id, pair.field_id, pair.season_id)
        if season is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                 f"Season {pair.season_id!r} not found on field {pair.field_id!r}")
        resolved.append((field, season))

    batch_id = jobs_db.create_batch(org_id, project_id, "multicrop_monitoring_bulk", user["user_id"])
    job_ids = []
    for field, season in resolved:
        payload = {
            "field_id": field["field_id"], "season_id": season["season_id"],
            "geometry": field["geojson_geometry"], "season_start": season["payload"]["start_date"],
            "season_end": season["payload"]["end_date"], "processing_version": MULTICROP_VERSION,
            "force_refresh": body.force_refresh, "requested_by": user["user_id"],
        }
        job_ids.append(jobs_db.create_job(org_id, "multicrop_monitoring", payload, batch_id=batch_id))
    return {"batch_id": batch_id, "job_ids": job_ids}


@router.get("/projects/{project_id}/monitoring/batches")
def list_monitoring_batches(project_id: str, user=Depends(get_current_user)):
    require_project_access(user["org_id"], project_id, user)
    return jobs_db.list_batches(user["org_id"], project_id=project_id)


@router.get("/batches/{batch_id}")
def get_batch_progress(batch_id: str, user=Depends(get_current_user)):
    org_id = user["org_id"]
    batch = _owned_batch(org_id, batch_id)
    if batch["project_id"]:
        require_project_access(org_id, batch["project_id"], user)
    return {"batch": batch, **jobs_db.batch_progress(org_id, batch_id)}


@router.post("/batches/{batch_id}/cancel")
def cancel_batch(batch_id: str, user=Depends(require_writer)):
    org_id = user["org_id"]
    batch = _owned_batch(org_id, batch_id)
    if batch["project_id"]:
        require_project_access(org_id, batch["project_id"], user)
    cancelled = []
    for child in jobs_db.list_batch_jobs(org_id, batch_id):
        if child["status"] in ("pending", "running", "cancel_requested"):
            jobs_db.request_cancel(org_id, child["job_id"])
            cancelled.append(child["job_id"])
    return {"cancelled_job_ids": cancelled}


@router.post("/batches/{batch_id}/retry-failed")
def retry_failed(batch_id: str, body: RetryFailedRequest, user=Depends(require_writer)):
    """Re-queues only the FAILED children (new job rows, same frozen
    payload) — successful children are untouched, never recomputed."""
    org_id = user["org_id"]
    batch = _owned_batch(org_id, batch_id)
    if batch["project_id"]:
        require_project_access(org_id, batch["project_id"], user)
    new_job_ids = []
    for child in jobs_db.list_batch_jobs(org_id, batch_id):
        if child["status"] == "error":
            new_job_ids.append(jobs_db.create_job(org_id, child["job_type"], child["payload"], batch_id=batch_id))
    if new_job_ids:
        from sqlalchemy import text
        from src.database import get_db_connection
        with get_db_connection() as conn:
            conn.execute(text("UPDATE job_batches SET status = 'running' WHERE org_id = :o AND batch_id = :b"),
                         {"o": org_id, "b": batch_id})
            conn.commit()
    return {"new_job_ids": new_job_ids}


@router.get("/projects/{project_id}/monitoring/dashboard")
def get_monitoring_dashboard(project_id: str, user=Depends(get_current_user)):
    require_project_access(user["org_id"], project_id, user)
    if projects_db.get_project(user["org_id"], project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return monitoring_ops.project_monitoring_dashboard(user["org_id"], project_id)


@router.get("/projects/{project_id}/monitoring/issues")
def get_issues(project_id: str, status_filter: str | None = None, user=Depends(get_current_user)):
    require_project_access(user["org_id"], project_id, user)
    return monitoring_ops.list_issues(user["org_id"], project_id=project_id, status_filter=status_filter)


@router.post("/issues/{issue_id}/acknowledge")
def acknowledge_issue(issue_id: str, body: IssueDecision, user=Depends(require_writer)):
    issue = monitoring_ops.get_issue(user["org_id"], issue_id)
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found")
    return monitoring_ops.acknowledge_issue(user["org_id"], issue_id, user["user_id"], body.reason)


@router.post("/issues/{issue_id}/resolve")
def resolve_issue(issue_id: str, body: IssueResolve, user=Depends(require_writer)):
    issue = monitoring_ops.get_issue(user["org_id"], issue_id)
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Issue not found")
    return monitoring_ops.resolve_issue(user["org_id"], issue_id, user["user_id"], body.reason)


@router.get("/admin/queue-status")
def get_queue_status(user=Depends(require_admin)):
    """Admin-only operational visibility into the durable job queue and
    live workers — not tenant data, so intentionally not org-scoped."""
    return jobs_db.queue_status()
