from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.deps import get_current_user, get_owned_field, get_spatial_engine, require_writer
from backend.schemas.ai import DatasetBuildResult, TrainAccepted, TrainRequest
from src.ai.ml.dataset_builder import build_dataset, save_dataset, load_dataset
from src.persistence.database import get_job, list_completed_jobs
from src.jobs.queue import create_job

router = APIRouter(tags=["ai-validation"])


@router.post("/ai/dataset/build", response_model=DatasetBuildResult)
def build_ai_dataset(user: dict = Depends(require_writer)):
    """Synchronous — this is a DB scan + threshold-gate recompute, same
    class of cost as analyze_irrigation_behavior, not the unbounded-time
    category that justifies a background job (that's /ai/train, below)."""
    org_id = user["org_id"]
    df = build_dataset(org_id)
    save_dataset(org_id, df)
    if df.empty:
        return DatasetBuildResult(row_count=0, field_window_groups=0, label_counts={})
    groups = df[["field_id", "window_start", "window_end"]].drop_duplicates().shape[0]
    return DatasetBuildResult(
        row_count=len(df), field_window_groups=groups,
        label_counts=df["label"].value_counts().to_dict(),
    )


@router.get("/ai/dataset")
def get_ai_dataset(user: dict = Depends(get_current_user)):
    df = load_dataset(user["org_id"])
    return {"row_count": len(df), "columns": list(df.columns)}


@router.post("/ai/train")
def submit_train_job(body: TrainRequest, response: Response, user: dict = Depends(require_writer)):
    """Hands off to the durable worker (backend/job_handlers.
    handle_ai_train) instead of an in-process BackgroundTask — Phase 4."""
    org_id = user["org_id"]
    job_id = create_job(org_id, "ai_train", {
        "model_key": body.model_key, "k": body.k, "requested_by": user["user_id"],
    })
    response.status_code = status.HTTP_202_ACCEPTED
    return TrainAccepted(job_id=job_id)


@router.post("/ai/train/{job_id}/cancel")
def cancel_train_job(job_id: str, user: dict = Depends(require_writer)):
    from src.jobs.queue import request_cancel
    job = get_job(user["org_id"], job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    request_cancel(user["org_id"], job_id)
    return {"ok": True}


@router.get("/ai/train/{job_id}")
def get_train_job(job_id: str, user: dict = Depends(get_current_user)):
    job = get_job(user["org_id"], job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


@router.get("/ai/validate/{model_key}")
def get_last_validation(model_key: str, user: dict = Depends(get_current_user)):
    """Serves the LAST COMPLETED training job's stored metrics, not a
    live recomputation — a saved .joblib bundle (model/classes/
    feature_names only) doesn't retain y_true/y_pred/y_proba, so
    evaluate.py's functions can't be re-derived from load_model() alone.
    This is a deliberate design correction, not an oversight."""
    org_id = user["org_id"]
    # Scans this org's completed training jobs newest-first and returns the
    # first whose stored metrics belong to the requested model. The scan is
    # caller-side because the predicate lives inside the opaque result
    # payload; the query itself now belongs to src/persistence/database.py.
    for job in list_completed_jobs(org_id, "ai_train"):
        result = job["result"]
        if result and result.get("summary", {}).get("model_name") == f"{org_id}_{model_key}":
            return result
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"No completed training run found for '{model_key}'")


def _detector_summary(org_id: str, field_id: str) -> dict | None:
    from src.persistence.database import get_latest_signal_result
    signal = get_latest_signal_result(org_id, field_id)
    if signal is None:
        return None
    return {
        "window_start": signal.get("window_start"),
        "window_end": signal.get("window_end"),
        "detector_used": signal.get("detector_used"),
        "candidate_drydowns": signal.get("total_awd"),
        "source": signal.get("cache_source"),
    }


def _compare(detector: dict | None, ml_is_awd: bool, window: tuple[str, str]) -> dict:
    """Practice-level comparison only. The detector's drydown count maps to
    VM0051's water-regime categories; the model only says AWD-like vs
    PTR-like, so the count itself is never compared."""
    if detector is None or detector["candidate_drydowns"] is None:
        return {"status": "no_detector_run", "detector_category": None, "agrees": None}
    count = detector["candidate_drydowns"]
    category = ("continuous_flooding" if count == 0 else
                "single_drainage" if count == 1 else "multiple_drainage")
    overlaps = bool(detector["window_start"] and detector["window_end"]
                    and detector["window_start"] <= window[1] and detector["window_end"] >= window[0])
    return {
        "status": "compared" if overlaps else "different_windows",
        "detector_category": category,
        # VM0051 defines AWD as multiple (>1) drainage events.
        "agrees": (category == "multiple_drainage") == ml_is_awd,
    }


@router.get("/fields/{field_id}/awd-external-comparison")
def get_external_awd_comparison(
    field_id: str,
    user: dict = Depends(get_current_user),
    field: dict = Depends(get_owned_field(expect_type="rice_awd")),
):
    """Read-only: research benchmark metrics + the latest detector run.
    Never calls the carbon engine."""
    from src.ai.ml.external_awd import read_metrics

    return {
        "field_id": field_id,
        "experimental": True,
        "research_benchmark": read_metrics(),
        "existing_signal": _detector_summary(user["org_id"], field_id),
        "affects_carbon_calculation": False,
        "message": (
            "AWD practice classification from an external research model (Punjab, India). "
            "It is not an independently verified AWD cycle count and does not change "
            "drydown counting, carbon calculations, readiness or issuance."
        ),
    }


@router.post("/fields/{field_id}/awd-external-prediction")
def predict_external_awd(
    field_id: str,
    user: dict = Depends(get_current_user),
    field: dict = Depends(get_owned_field(expect_type="rice_awd")),
    engine=Depends(get_spatial_engine),
):
    """Experimental, read-only AWD practice classification for one field:
    ascending Sentinel-1 gamma0 over the research window, the same 61
    Ricemapper handcrafted features the model was trained on, then the
    random forest. Nothing is stored and no calculation input changes."""
    from datetime import date
    from src.ai.ml.external_awd import load_bundle, predict
    from src.ai.ml.ricemapper_features import (
        FEATURE_VERSION, extract_ascending_gamma0, handcrafted_features, research_window,
    )

    bundle = load_bundle()
    if bundle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "External AWD model is not installed on this server")
    if bundle.get("feature_version") != FEATURE_VERSION:
        raise HTTPException(status.HTTP_409_CONFLICT, "Model and feature pipeline versions differ")
    window = research_window(date.today())
    try:
        series, relative_orbit = extract_ascending_gamma0(field["geojson_geometry"], *window)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Sentinel-1 extraction failed: {exc}")
    try:
        features = handcrafted_features(series, *window)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    score = predict(bundle, features)
    is_awd = score >= 0.5
    return {
        "field_id": field_id,
        "experimental": True,
        "task": "awd_practice_classification",
        "predicted_class": "AWD" if is_awd else "PTR",
        "awd_score": score,
        "score_calibrated": False,
        "window_start": window[0],
        "window_end": window[1],
        "observations": int(series["date"].nunique()),
        "relative_orbit": relative_orbit,
        "model_version": bundle["version"],
        "feature_version": FEATURE_VERSION,
        "comparison": _compare(_detector_summary(user["org_id"], field_id), is_awd, window),
        "affects_carbon_calculation": False,
    }
