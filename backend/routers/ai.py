from datetime import date

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


def _compare(detector: dict | None, ml_is_awd: bool) -> dict:
    """Practice-level comparison on the SAME Signal Analytics run (same field,
    same window). The detector's drydown count maps to VM0051's water-regime
    categories; VM0051 defines AWD as multiple (>1) drainage events, so the
    ML side "AWD" (score >= 50%) is compared with "multiple drainage" and
    "not AWD" with 0 or 1 drydowns. The count itself is never compared."""
    if detector is None or detector["candidate_drydowns"] is None:
        return {"status": "no_detector_run", "detector_category": None, "detector_drydowns": None,
                "ml_is_awd": ml_is_awd, "agrees": None}
    count = detector["candidate_drydowns"]
    category = ("continuous_flooding" if count == 0 else
                "single_drainage" if count == 1 else "multiple_drainage")
    return {
        "status": "compared",
        "detector_category": category,
        "detector_drydowns": count,
        "ml_is_awd": ml_is_awd,
        "agrees": (category == "multiple_drainage") == ml_is_awd,
    }


@router.get("/ai/awd-model/metrics")
def get_awd_model_metrics(user: dict = Depends(get_current_user)):
    """Held-out performance of the installed AWD-vs-PTR model (trained on
    microsoft/rice-irrigation-mapping-s1s2); null when no model is installed."""
    from src.ai.ml.external_awd import read_metrics

    return {"research_benchmark": read_metrics()}


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
    """Experimental, read-only AWD practice classification for one field, on
    exactly the window of the field's latest Signal Analytics run (same field
    geometry, same dates as the rule-based detector it is compared with):
    ascending Sentinel-1 gamma0 plus the window year's Satellite Embedding (or
    the latest earlier year if that one is not published yet), the same 125
    features and preprocessing as training, then the random forest. Only a
    window with too few observations to fit the radar curve (fewer than 2)
    gives a 422 instead of a score. Nothing is stored and no calculation input changes."""
    from src.ai.ml.external_awd import load_bundle, predict
    from src.ai.ml.ricemapper_features import (
        FEATURE_VERSION, embedding_year_for,
        extract_ascending_gamma0, extract_satellite_embedding, handcrafted_features,
        latest_embedding_year, observation_quality,
    )

    bundle = load_bundle()
    if bundle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "External AWD model is not installed on this server")
    if bundle.get("feature_version") != FEATURE_VERSION:
        raise HTTPException(status.HTTP_409_CONFLICT, "Model and feature pipeline versions differ")
    detector = _detector_summary(user["org_id"], field_id)
    if detector is None or not detector["window_start"] or not detector["window_end"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Run Signal Analytics for this field first — the ML classification uses "
                            "the same window as its latest run.")
    window = (detector["window_start"], detector["window_end"])
    geometry = field["geojson_geometry"]
    try:
        # The window's own year, or the latest earlier year when Google has not
        # published that year's embedding yet.
        year = latest_embedding_year(geometry, up_to=embedding_year_for(*window))
        if year is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "No prediction: no Satellite Embedding is published for this field.")
        series, relative_orbit = extract_ascending_gamma0(geometry, *window)
        n_obs, max_gap = observation_quality(series, *window)
        embedding = extract_satellite_embedding(geometry, year)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Earth Engine extraction failed: {exc}")
    try:
        features = handcrafted_features(series, *window)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"No prediction: {exc}")
    features.update(embedding)
    score = predict(bundle, features)
    is_awd = score >= 0.5
    response = {
        "field_id": field_id,
        "experimental": True,
        "task": "awd_practice_classification",
        "predicted_class": "AWD" if is_awd else "PTR",
        "awd_score": score,
        "score_calibrated": False,
        "window_start": window[0],
        "window_end": window[1],
        "observations": n_obs,
        "max_gap_days": max_gap,
        "relative_orbit": relative_orbit,
        "embedding_year": year,
        "model_version": bundle["version"],
        "feature_version": FEATURE_VERSION,
        "comparison": _compare(detector, is_awd),
        "affects_carbon_calculation": False,
    }
    # Kept as a completed job so an AI explanation can cite this exact result
    # ("why do the model and the detector agree / disagree?"). Never an input
    # to any calculation.
    from src.jobs.queue import record_completed_job
    record_completed_job(user["org_id"], "awd_ml_prediction",
                         {"field_id": field_id, "window_start": window[0], "window_end": window[1],
                          "requested_by": user["user_id"]}, response)
    return response
