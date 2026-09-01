import datetime

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from backend.deps import get_current_user, get_owned_field, get_spatial_engine
from backend.schemas.signal import JobStatusOut, SignalRunAccepted, SignalResult, SignalRunRequest
from src.ai.predictor import predict_awd_states
from src.database import check_cache, get_job, get_latest_signal_result, save_cache
from src.database import create_job, mark_job_done, mark_job_error, mark_job_running
from src.threshold_gate import AdaptiveAWDGate

router = APIRouter(tags=["signal-analytics"])


def _run_pipeline(org_id: str, field_id: str, district: str, area_ha: float,
                   df_processed: pd.DataFrame, req: SignalRunRequest, cache_source: str) -> SignalResult:
    """Shared by the cache-hit (synchronous) and cache-miss (background
    job) paths — both must run identical logic so behavior never diverges
    by which path served the request. Mirrors app.py's
    render_signal_analytics_tab() sequence: analyze_irrigation_behavior ->
    extract_phenology -> (optionally) predict_awd_states, with the same
    FileNotFoundError fallback-to-threshold-gate behavior."""
    gate = AdaptiveAWDGate()
    df_final = gate.analyze_irrigation_behavior(df_processed)
    df_final = gate.extract_phenology(df_final)

    detector_used = "Threshold Gate (rule-based)"
    model_fallback_msg = None
    if req.detector != "threshold":
        try:
            df_final = predict_awd_states(
                df_final, f"{org_id}_{req.detector}", field_id, district,
                area_ha, req.window_start, req.window_end,
            )
            detector_used = req.detector
        except FileNotFoundError:
            model_fallback_msg = (
                f"'{req.detector}' has not been trained yet — showing "
                "Threshold Gate results instead."
            )

    total_awd = int(df_final["drydown_event"].sum())
    sowing_row = df_final[df_final["is_sowing"] == 1]
    harvest_row = df_final[df_final["is_harvest"] == 1]
    sowing_date_str = sowing_row["date"].iloc[0] if not sowing_row.empty else "N/A"
    harvest_date_str = harvest_row["date"].iloc[0] if not harvest_row.empty else "N/A"

    from_phenology = sowing_date_str != "N/A" and harvest_date_str != "N/A"
    if from_phenology:
        season_length_days = (
            pd.to_datetime(harvest_date_str) - pd.to_datetime(sowing_date_str)
        ).days
    else:
        season_length_days = 120  # fallback, matches app.py's own default

    return SignalResult(
        field_id=field_id,
        cache_source=cache_source,
        total_awd=total_awd,
        sowing_date=sowing_date_str,
        harvest_date=harvest_date_str,
        season_length_days=season_length_days,
        from_phenology=from_phenology,
        detector_used=detector_used,
        model_fallback_msg=model_fallback_msg,
        n_observations=len(df_final),
        vv_mean=float(df_final["vv_smoothed"].mean()),
        vv_std=float(df_final["vv_smoothed"].std()),
        awd_dates=df_final[df_final["drydown_event"] == 1]["date"].tolist(),
        window_start=req.window_start,
        window_end=req.window_end,
        area_ha=area_ha,
        timeseries=df_final.to_dict(orient="records"),
    )


def _run_signal_job(job_id: str, org_id: str, field_id: str, field: dict, req: SignalRunRequest, engine):
    try:
        mark_job_running(job_id)
        geom = field["geojson_geometry"]["features"][0]["geometry"]
        df_raw = engine.extract_clean_timeseries(geom, req.window_start, req.window_end)
        if df_raw.empty:
            mark_job_error(job_id, "No valid Sentinel-1 observations found for this field and window.")
            return
        save_cache(org_id, field_id, df_raw, req.window_start, req.window_end)
        df_processed = check_cache(org_id, field_id, req.window_start, req.window_end)
        result = _run_pipeline(
            org_id, field_id, field["district"], field["area_ha"] or 1.0,
            df_processed, req, cache_source="Live Google Earth Engine Core API",
        )
        mark_job_done(job_id, result.model_dump())
    except Exception as exc:
        mark_job_error(job_id, str(exc))


@router.post("/fields/{field_id}/signal-runs")
def submit_signal_run(
    field_id: str, body: SignalRunRequest, background_tasks: BackgroundTasks,
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
            return result  # 200 (default) — fast path, never touched GEE

    job_id = create_job(org_id, "signal_run")
    background_tasks.add_task(_run_signal_job, job_id, org_id, field_id, field, body, engine)
    response.status_code = status.HTTP_202_ACCEPTED
    return SignalRunAccepted(job_id=job_id)


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
