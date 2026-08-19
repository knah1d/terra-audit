from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from backend.deps import get_current_user, require_writer
from backend.schemas.ai import DatasetBuildResult, TrainAccepted, TrainRequest
from src.ai.dataset_builder import build_dataset, save_dataset, load_dataset
from src.ai.feature_engineering import build_features
from src.ai.models import save_model, train_and_evaluate
from src.ai import evaluate as ai_evaluate
from src.database import (
    create_job, get_job, list_completed_jobs,
    mark_job_done, mark_job_error, mark_job_running,
)

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


def _run_train_job(job_id: str, org_id: str, model_key: str, k: int):
    try:
        mark_job_running(job_id)
        df = load_dataset(org_id)
        if df.empty:
            mark_job_error(job_id, "No training dataset found. Build the dataset first.")
            return
        X, y = build_features(df)
        result = train_and_evaluate(model_key, X, y, k)
        # Namespace the artifact per org — same convention app.py uses for
        # predict_awd_states, so a model trained here is servable there too.
        result["model_name"] = f"{org_id}_{model_key}"
        save_model(result)
        summary = ai_evaluate.summarize_fold_predictions(result)
        mark_job_done(job_id, {
            "summary": summary,
            "feature_importance": ai_evaluate.feature_importance(result),
            "roc_curve": ai_evaluate.roc_curve_data(result),
        })
    except Exception as exc:
        mark_job_error(job_id, str(exc))


@router.post("/ai/train")
def submit_train_job(
    body: TrainRequest, background_tasks: BackgroundTasks, response: Response,
    user: dict = Depends(require_writer),
):
    org_id = user["org_id"]
    job_id = create_job(org_id, "ai_train")
    background_tasks.add_task(_run_train_job, job_id, org_id, body.model_key, body.k)
    response.status_code = status.HTTP_202_ACCEPTED
    return TrainAccepted(job_id=job_id)


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
    # payload; the query itself now belongs to src/database.py.
    for job in list_completed_jobs(org_id, "ai_train"):
        result = job["result"]
        if result and result.get("summary", {}).get("model_name") == f"{org_id}_{model_key}":
            return result
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"No completed training run found for '{model_key}'")
