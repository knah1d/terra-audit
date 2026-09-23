from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from backend.deps import get_current_user, get_owned_field, get_spatial_engine, require_writer
from backend.schemas.monitoring import BenchmarkRequest, ObservationCreate, ReviewCreate, SeasonCreate
from src import monitoring
from src.ai.crop_benchmark import benchmark, build_corpus
from src.database import create_job, get_job, list_completed_jobs, mark_job_done, mark_job_error, mark_job_running
from src.multicrop_data import extract_observations

router = APIRouter(tags=["multi-crop-monitoring"])
_field = get_owned_field()


def owned_season(org_id, field_id, season_id):
    result = monitoring.season(org_id, field_id, season_id)
    if result is None:
        raise HTTPException(404, "Crop season not found")
    return result


@router.get("/fields/{field_id}/crop-seasons")
def list_seasons(field_id: str, user=Depends(get_current_user), field=Depends(_field)):
    return monitoring.records("crop_seasons", user["org_id"], field_id)


@router.post("/fields/{field_id}/crop-seasons", status_code=201)
def create_season(field_id: str, body: SeasonCreate, user=Depends(require_writer), field=Depends(_field)):
    return monitoring.append_record("crop_seasons", user["org_id"], field_id, None,
                                    {**body.model_dump(mode="json"), "created_by": user["user_id"]})


@router.get("/fields/{field_id}/crop-seasons/{season_id}/evidence")
def evidence(field_id: str, season_id: str, user=Depends(get_current_user), field=Depends(_field)):
    owned_season(user["org_id"], field_id, season_id)
    return monitoring.evidence_package(user["org_id"], field_id, season_id)


@router.post("/fields/{field_id}/crop-seasons/{season_id}/observations", status_code=201)
def create_observation(field_id: str, season_id: str, body: ObservationCreate,
                       user=Depends(require_writer), field=Depends(_field)):
    season = owned_season(user["org_id"], field_id, season_id)["payload"]
    observed = body.observed_at.astimezone(timezone.utc)
    day = observed.date().isoformat()
    if not season["start_date"] <= day <= season["end_date"]:
        raise HTTPException(422, "Observation must fall within the crop season (UTC)")
    if observed > datetime.now(timezone.utc):
        raise HTTPException(422, "Field observations cannot be dated in the future")
    payload = body.model_dump(mode="json")
    payload.update(observed_at=observed.isoformat(), created_by=user["user_id"],
                   unit="cm_relative_to_soil_surface" if body.kind == "water_level" else
                        "percent" if body.kind == "residue_cover" else None)
    return monitoring.append_record("field_observations", user["org_id"], field_id, season_id, payload)


@router.post("/fields/{field_id}/crop-seasons/{season_id}/observations/{observation_id}/reviews", status_code=201)
def review_observation(field_id: str, season_id: str, observation_id: str, body: ReviewCreate,
                       user=Depends(require_writer), field=Depends(_field)):
    owned_season(user["org_id"], field_id, season_id)
    observation = next((r for r in monitoring.records("field_observations", user["org_id"], field_id, season_id)
                        if r["id"] == observation_id), None)
    if observation is None:
        raise HTTPException(404, "Observation not found")
    if observation["payload"]["created_by"] == user["user_id"]:
        raise HTTPException(422, "A different team member must review this observation")
    return monitoring.append_record("observation_reviews", user["org_id"], field_id, season_id,
        {**body.model_dump(), "observation_id": observation_id, "reviewed_by": user["user_id"]})


def _run_monitoring(job_id, user, field, season):
    try:
        mark_job_running(job_id)
        payload = extract_observations(field["geojson_geometry"], season["payload"]["start_date"], season["payload"]["end_date"])
        payload.update(field=field, season=season, requested_by=user["user_id"])
        saved = monitoring.append_record("monitoring_runs", user["org_id"], field["field_id"], season["id"], payload)
        mark_job_done(job_id, {"run_id": saved["id"], "season_id": season["id"], "quality": payload["quality"]})
    except Exception as exc:
        mark_job_error(job_id, str(exc))


@router.post("/fields/{field_id}/crop-seasons/{season_id}/monitoring-runs", status_code=202)
def run_monitoring(field_id: str, season_id: str, background_tasks: BackgroundTasks,
                   user=Depends(require_writer), field=Depends(_field), engine=Depends(get_spatial_engine)):
    # Engine dependency ensures EE initialized; unlike rice signal-runs this
    # generic pipeline is deliberately available to BOTH accounting types.
    season = owned_season(user["org_id"], field_id, season_id)
    if season["payload"]["end_date"] >= datetime.now(timezone.utc).date().isoformat():
        raise HTTPException(422, "Retrospective benchmarks require a completed season ending before today")
    job_id = create_job(user["org_id"], "multicrop_monitoring")
    background_tasks.add_task(_run_monitoring, job_id, user, field, season)
    return {"job_id": job_id}


@router.get("/multi-crop/jobs/{job_id}")
def job_status(job_id: str, user=Depends(get_current_user)):
    job = get_job(user["org_id"], job_id)
    if job is None or job["job_type"] not in {"multicrop_monitoring", "crop_benchmark"}:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/multi-crop/dataset")
def dataset(user=Depends(get_current_user)):
    return build_corpus(user["org_id"])


@router.get("/multi-crop/benchmarks")
def list_benchmarks(user=Depends(get_current_user)):
    return [{"job_id": j["job_id"],
             "split": j["result"]["split"], "dataset_sha256": j["result"]["dataset"]["sha256"]}
            for j in list_completed_jobs(user["org_id"], "crop_benchmark")]


def _run_benchmark(job_id, corpus, body):
    try:
        mark_job_running(job_id)
        mark_job_done(job_id, benchmark(corpus, body.split, body.models))
    except Exception as exc:
        mark_job_error(job_id, str(exc))


@router.post("/multi-crop/benchmarks", status_code=202)
def run_benchmark(body: BenchmarkRequest, background_tasks: BackgroundTasks, user=Depends(require_writer)):
    # Freeze the dataset at submission so concurrent reviews cannot change it.
    corpus = build_corpus(user["org_id"])
    job_id = create_job(user["org_id"], "crop_benchmark")
    background_tasks.add_task(_run_benchmark, job_id, corpus, body)
    return {"job_id": job_id}
