import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.deps import get_current_user, get_owned_field, get_spatial_engine
from backend.job_handlers import _run_signal_pipeline
from backend.schemas.signal import JobStatusOut, SignalRunAccepted, SignalResult, SignalRunRequest
from src.database import check_cache, get_job, get_latest_signal_result
from src.jobs import create_job

router = APIRouter(tags=["signal-analytics"])


def _run_pipeline(org_id: str, field_id: str, district: str, area_ha: float,
                   df_processed: pd.DataFrame, req: SignalRunRequest, cache_source: str) -> SignalResult:
    """Synchronous cache-hit path only (never touches GEE) — the
    cache-miss path now runs through the durable worker
    (backend/job_handlers.handle_signal_run), which calls the SAME
    underlying _run_signal_pipeline so both paths stay identical."""
    return SignalResult(**_run_signal_pipeline(
        org_id, field_id, district, area_ha, df_processed, req.model_dump(), cache_source,
    ))


@router.post("/fields/{field_id}/signal-runs")
def submit_signal_run(
    field_id: str, body: SignalRunRequest,
    response: Response,
    user: dict = Depends(get_current_user),
    # require_sar rejects cropland_alm_vm0042 (and any future non-satellite
    # field type) with a 422 instead of silently running the rice AWD
    # detector against a field that has no timeseries.
    field: dict = Depends(get_owned_field(require_sar=True)),
    engine=Depends(get_spatial_engine),
):
    org_id = user["org_id"]

    if not body.force_refresh:
        df_processed = check_cache(org_id, field_id, body.window_start, body.window_end)
        if not df_processed.empty:
            result = _run_pipeline(
                org_id, field_id, field["district"], field["area_ha"] or 1.0,
                df_processed, body, cache_source="Local relational data store",
            )
            return result  # 200 (default) — fast path, never touched GEE, never queued

    # Cache-miss: hand off to the durable worker instead of an in-process
    # BackgroundTask (Phase 4) — survives a web-process restart, has
    # bounded retries, and is cancellable. `engine` (get_spatial_engine)
    # is still required here just to fail fast with a clean 503 if Earth
    # Engine isn't configured at all, rather than queuing a job that can
    # only ever fail.
    job_id = create_job(org_id, "signal_run", {
        "field_id": field_id, "window_start": body.window_start, "window_end": body.window_end,
        "detector": body.detector, "force_refresh": body.force_refresh, "requested_by": user["user_id"],
    })
    response.status_code = status.HTTP_202_ACCEPTED
    return SignalRunAccepted(job_id=job_id)


@router.post("/fields/{field_id}/signal-runs/{job_id}/cancel")
def cancel_signal_run(field_id: str, job_id: str, user: dict = Depends(get_current_user),
                       field: dict = Depends(get_owned_field(require_sar=True))):
    from src.jobs import request_cancel
    job = get_job(user["org_id"], job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    request_cancel(user["org_id"], job_id)
    return {"ok": True}


@router.get("/fields/{field_id}/signal-runs/latest", response_model=SignalResult)
def get_latest_signal_run(
    field_id: str, user: dict = Depends(get_current_user),
    field: dict = Depends(get_owned_field(require_sar=True)),
):
    """Read-only — the Audit & Evidence page's readiness checklist uses
    this to show whether satellite/AWD/phenology context exists at all
    for this field, without running a new analysis. NOT tied to any
    specific committed verification (see get_latest_signal_result)."""
    signal = get_latest_signal_result(user["org_id"], field_id)
    if signal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No signal-analytics run recorded for this field yet")
    return SignalResult(**signal)


@router.get("/signal-runs/{job_id}", response_model=JobStatusOut)
def get_signal_run(job_id: str, user: dict = Depends(get_current_user)):
    job = get_job(user["org_id"], job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return JobStatusOut(**{**job, "created_at": str(job["created_at"]),
                           "finished_at": str(job["finished_at"]) if job["finished_at"] else None})
