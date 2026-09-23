"""Job handler functions run by the durable worker (backend/worker.py).

Each handler takes (job, ctx) and returns a JSON-serializable result
dict on success. `job` is a decoded background_jobs row (src.jobs.
get_job_row shape: org_id, job_id, payload, attempt_count, ...). `ctx`
(WorkerContext, defined in backend/worker.py) provides the shared
SpatialDataEngine, a heartbeat() callback, and cancel_requested().

These replace the old BackgroundTasks closures in backend/routers/
signal.py, ai.py, monitoring.py — the logic is unchanged, only how it
receives its inputs (a JSON payload instead of already-fetched Python
objects, since the worker runs in a separate process/request lifecycle)
and how it reports outcomes (src.jobs.complete_job/fail_job instead of
src.database.mark_job_done/mark_job_error).
"""
import pandas as pd

from src.ai import evaluate as ai_evaluate
from src.ai.crop_benchmark import benchmark
from src.ai.dataset_builder import load_dataset
from src.ai.feature_engineering import build_features
from src.ai.models import save_model, train_and_evaluate
from src.ai.predictor import predict_awd_states
from src.database import check_cache, get_field, save_cache
from src.jobs import InvalidJobRequest, JobCancelled
from src.multicrop_data import extract_observations
from src import monitoring
from src import monitoring_ops
from src import reviews as reviews_db
from src.threshold_gate import AdaptiveAWDGate


def _run_signal_pipeline(org_id, field_id, district, area_ha, df_processed, req, cache_source):
    """Identical logic to the pre-Phase-4 shared helper in
    backend/routers/signal.py — moved here so both the synchronous
    cache-hit path (still in the router, never touches the queue) and
    this worker handler use exactly one implementation."""
    gate = AdaptiveAWDGate()
    df_final = gate.analyze_irrigation_behavior(df_processed)
    df_final = gate.extract_phenology(df_final)

    detector_used = "Threshold Gate (rule-based)"
    model_fallback_msg = None
    if req["detector"] != "threshold":
        try:
            df_final = predict_awd_states(
                df_final, f"{org_id}_{req['detector']}", field_id, district,
                area_ha, req["window_start"], req["window_end"],
            )
            detector_used = req["detector"]
        except FileNotFoundError:
            model_fallback_msg = (
                f"'{req['detector']}' has not been trained yet — showing Threshold Gate results instead."
            )

    total_awd = int(df_final["drydown_event"].sum())
    sowing_row = df_final[df_final["is_sowing"] == 1]
    harvest_row = df_final[df_final["is_harvest"] == 1]
    sowing_date_str = sowing_row["date"].iloc[0] if not sowing_row.empty else "N/A"
    harvest_date_str = harvest_row["date"].iloc[0] if not harvest_row.empty else "N/A"

    from_phenology = sowing_date_str != "N/A" and harvest_date_str != "N/A"
    if from_phenology:
        season_length_days = (pd.to_datetime(harvest_date_str) - pd.to_datetime(sowing_date_str)).days
    else:
        season_length_days = 120

    return {
        "field_id": field_id, "cache_source": cache_source, "total_awd": total_awd,
        "sowing_date": sowing_date_str, "harvest_date": harvest_date_str,
        "season_length_days": season_length_days, "from_phenology": from_phenology,
        "detector_used": detector_used, "model_fallback_msg": model_fallback_msg,
        "n_observations": len(df_final), "vv_mean": float(df_final["vv_smoothed"].mean()),
        "vv_std": float(df_final["vv_smoothed"].std()),
        "awd_dates": df_final[df_final["drydown_event"] == 1]["date"].tolist(),
        "window_start": req["window_start"], "window_end": req["window_end"],
        "area_ha": area_ha, "timeseries": df_final.to_dict(orient="records"),
    }


def handle_signal_run(job: dict, ctx) -> dict:
    org_id, payload = job["org_id"], job["payload"]
    field_id = payload["field_id"]
    field = get_field(org_id, field_id)
    if field is None:
        raise InvalidJobRequest(f"Field {field_id!r} no longer exists")

    geom = field["geojson_geometry"]["features"][0]["geometry"]
    df_raw = ctx.engine.extract_clean_timeseries(geom, payload["window_start"], payload["window_end"])
    if ctx.cancel_requested():
        raise JobCancelled("Cancelled before publishing the signal-run result")
    if df_raw.empty:
        raise InvalidJobRequest("No valid Sentinel-1 observations found for this field and window.")

    save_cache(org_id, field_id, df_raw, payload["window_start"], payload["window_end"])
    df_processed = check_cache(org_id, field_id, payload["window_start"], payload["window_end"])
    return _run_signal_pipeline(
        org_id, field_id, field["district"], field["area_ha"] or 1.0,
        df_processed, payload, cache_source="Live Google Earth Engine Core API",
    )


def handle_ai_train(job: dict, ctx) -> dict:
    org_id, payload = job["org_id"], job["payload"]
    df = load_dataset(org_id)
    if df.empty:
        raise InvalidJobRequest("No training dataset found. Build the dataset first.")
    X, y = build_features(df)
    result = train_and_evaluate(payload["model_key"], X, y, payload["k"])
    if ctx.cancel_requested():
        raise JobCancelled("Cancelled before saving the trained model")
    result["model_name"] = f"{org_id}_{payload['model_key']}"
    save_model(result)
    return {
        "summary": ai_evaluate.summarize_fold_predictions(result),
        "feature_importance": ai_evaluate.feature_importance(result),
        "roc_curve": ai_evaluate.roc_curve_data(result),
    }


def handle_crop_benchmark(job: dict, ctx) -> dict:
    payload = job["payload"]
    return benchmark(payload["corpus"], payload["split"], payload["models"])


def handle_multicrop_monitoring(job: dict, ctx) -> dict:
    """Version-aware: reuses a prior run with an identical fingerprint
    (geometry + season dates + source collections + processing version)
    unless force_refresh was explicit. Re-collection always appends a
    new immutable run (never edits one) — reuse only ever means "don't
    call Earth Engine again," never "modify history." Also idempotent
    across a crash-retry of THIS job (append_record_once_per_job)."""
    org_id, payload = job["org_id"], job["payload"]
    field_id, season_id = payload["field_id"], payload["season_id"]
    field = get_field(org_id, field_id)
    if field is None:
        raise InvalidJobRequest(f"Field {field_id!r} no longer exists")
    season = monitoring.season(org_id, field_id, season_id)
    if season is None:
        raise InvalidJobRequest(f"Season {season_id!r} no longer exists on this field")

    sources = ["COPERNICUS/S1_GRD", "COPERNICUS/S2_SR_HARMONIZED"]
    fingerprint = monitoring_ops.compute_fingerprint(
        payload["geometry"], payload["season_start"], payload["season_end"],
        payload["processing_version"], sources,
    )

    if not payload.get("force_refresh"):
        reusable = monitoring_ops.find_reusable_run(org_id, field_id, season_id, fingerprint)
        if reusable is not None:
            return {"run_id": reusable["id"], "season_id": season_id, "source": "reused",
                    "quality": reusable["payload"]["quality"]}

    run_payload = extract_observations(payload["geometry"], payload["season_start"], payload["season_end"])
    if ctx.cancel_requested():
        raise JobCancelled("Cancelled before publishing the monitoring run")
    run_payload.update(field={"field_id": field_id, "district": field["district"]}, season=season,
                        requested_by=job.get("requested_by"), fingerprint=fingerprint, source="collected")

    saved = monitoring.append_record_once_per_job(
        "monitoring_runs", org_id, field_id, season_id, job["job_id"], run_payload,
    )

    for issue, created in monitoring_ops.evaluate_run_quality(org_id, field_id, season_id, saved["id"], run_payload):
        if created:
            _notify_issue(org_id, field_id, issue)
    crop_result = monitoring_ops.evaluate_crop_evidence(org_id, field_id, season_id)
    if crop_result and crop_result[1]:
        _notify_issue(org_id, field_id, crop_result[0])

    return {"run_id": saved["id"], "season_id": season_id, "source": "collected",
            "quality": run_payload["quality"]}


def _notify_issue(org_id: str, field_id: str, issue: dict) -> None:
    """One notification per NEWLY created issue, sent to the field's
    project leads — never per re-detection (that's the whole point of
    monitoring_ops' dedup-by-open-issue logic upstream of this call)."""
    from src import projects as projects_db
    for project_membership in projects_db.list_projects_for_field(org_id, field_id):
        if project_membership["removed_at"] is not None:
            continue
        for member in projects_db.list_project_members(org_id, project_membership["project_id"]):
            if member["project_role"] == "lead":
                reviews_db.notify(
                    org_id, member["user_id"], "data_quality_issue",
                    f"New data-quality issue on field {field_id}: {issue['issue_type'].replace('_', ' ')}.",
                    issue_id=issue["issue_id"],
                )


HANDLERS = {
    "signal_run": handle_signal_run,
    "ai_train": handle_ai_train,
    "crop_benchmark": handle_crop_benchmark,
    "multicrop_monitoring": handle_multicrop_monitoring,
}

from backend.ai_job_handlers import handle_workspace
HANDLERS.update({"workspace_" + kind: handle_workspace
                 for kind in ("train", "prediction", "answer", "document")})
