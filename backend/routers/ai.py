from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.deps import get_current_user, get_owned_field, require_writer
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


@router.get("/fields/{field_id}/awd-external-comparison")
def get_external_awd_comparison(
    field_id: str,
    user: dict = Depends(get_current_user),
    field: dict = Depends(get_owned_field(expect_type="rice_awd")),
):
    """Read-only shadow comparison. Never calls prediction or the carbon engine.

    External research dataset features are not interoperable with the existing
    GEE sigma0 median features without independent preprocessing work.
    Absence of benchmark results is explicit instead of faking accuracy.
    """
    from src.ai.ml.external_awd import read_metrics
    from src.paths import DATA_DIR
    from src.persistence.database import get_latest_signal_result

    metrics = read_metrics(DATA_DIR / "external_awd_benchmark")
    signal = get_latest_signal_result(user["org_id"], field_id)
    if signal is None:
        detector = None
    else:
        detector = {
            "window_start": signal.get("window_start"),
            "window_end": signal.get("window_end"),
            "detector_used": signal.get("detector_used"),
            "candidate_drydowns": signal.get("total_awd"),
            "source": signal.get("cache_source"),
        }
    return {
        "field_id": field_id,
        "experimental": True,
        "research_benchmark": metrics,
        "existing_signal": detector,
        "field_ml_prediction": None,
        "comparison_status": "feature_adapter_not_validated",
        "ground_truth_status": "not_provided",
        "affects_carbon_calculation": False,
        "message": (
            "This research benchmark measures external AWD-practice labels, "
            "not independent drydown counts. Terra Audit's Sentinel-1 preprocessing "
            "differs; no field-level ML inference is activated."
        ),
    }
