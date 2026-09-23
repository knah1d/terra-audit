from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import get_current_user, get_owned_field, get_spatial_engine, require_writer
from backend.schemas.monitoring import (
    BenchmarkRequest, ObservationCreate, PracticeEventCreate, ReviewCreate, SeasonCorrection, SeasonCreate,
)
from src import monitoring
from src.ai.crop_benchmark import build_corpus
from src.database import get_job, list_completed_jobs
from src.jobs import create_job, request_cancel
from src.processing import MULTICROP_VERSION

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
                                    {**body.model_dump(mode="json"), "version": 1, "created_by": user["user_id"]})


@router.get("/fields/{field_id}/crop-seasons/{season_id}/evidence")
def evidence(field_id: str, season_id: str, user=Depends(get_current_user), field=Depends(_field)):
    owned_season(user["org_id"], field_id, season_id)
    return monitoring.evidence_package(user["org_id"], field_id, season_id)


@router.get("/fields/{field_id}/crop-seasons/{season_id}/versions")
def season_versions(field_id: str, season_id: str, user=Depends(get_current_user), field=Depends(_field)):
    """Every version of this season (the original, then each correction in
    order) — the current/latest one is versions[-1], same as owned_season()
    returns. Lets a reviewer see what the season looked like at any point
    without losing the corrected history."""
    owned_season(user["org_id"], field_id, season_id)
    return monitoring.season_versions(user["org_id"], field_id, season_id)


@router.post("/fields/{field_id}/crop-seasons/{season_id}/corrections", status_code=201)
def correct_season(field_id: str, season_id: str, body: SeasonCorrection,
                   user=Depends(require_writer), field=Depends(_field)):
    """Appends a corrected version of an existing season (new dates/crops/
    name/notes + a mandatory reason) WITHOUT changing its season_id —
    every observation/review/monitoring-run already recorded against this
    season stays linked to it and keeps recording which version was in
    effect when it was created (see create_observation's season_version)."""
    prior = owned_season(user["org_id"], field_id, season_id)
    payload = body.model_dump(mode="json")
    reason = payload.pop("reason")
    payload.update(
        version=prior["payload"].get("version", 1) + 1,
        correction_reason=reason,
        corrected_by=user["user_id"],
        created_by=prior["payload"]["created_by"],
    )
    return monitoring.append_record("crop_seasons", user["org_id"], field_id, season_id, payload)


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
                   season_version=season.get("version", 1),
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


@router.get("/fields/{field_id}/crop-seasons/{season_id}/practice-events")
def list_practice_events(field_id: str, season_id: str, user=Depends(get_current_user), field=Depends(_field)):
    owned_season(user["org_id"], field_id, season_id)
    return monitoring.records("practice_events", user["org_id"], field_id, season_id)


@router.post("/fields/{field_id}/crop-seasons/{season_id}/practice-events", status_code=201)
def create_practice_event(field_id: str, season_id: str, body: PracticeEventCreate,
                          user=Depends(require_writer), field=Depends(_field)):
    season = owned_season(user["org_id"], field_id, season_id)["payload"]
    if not season["start_date"] <= body.event_date.isoformat() <= season["end_date"]:
        raise HTTPException(422, "Practice event must fall within the crop season")
    payload = body.model_dump(mode="json")
    payload.update(created_by=user["user_id"], season_version=season.get("version", 1))
    return monitoring.append_record("practice_events", user["org_id"], field_id, season_id, payload)


def _monitoring_payload(field: dict, season: dict, force_refresh: bool, requested_by: str) -> dict:
    """Freezes exactly what backend/job_handlers.handle_multicrop_monitoring
    needs at SUBMISSION time — geometry, season dates, and the processing
    version in effect right now — so a later edit to the field's geometry
    or the season's dates can never silently change what an
    already-queued job computes (Phase 4's "freeze each child job's
    geometry, season dates, processing version" requirement)."""
    return {
        "field_id": field["field_id"], "season_id": season["id"],
        "geometry": field["geojson_geometry"], "season_start": season["payload"]["start_date"],
        "season_end": season["payload"]["end_date"], "processing_version": MULTICROP_VERSION,
        "force_refresh": force_refresh, "requested_by": requested_by,
    }


@router.post("/fields/{field_id}/crop-seasons/{season_id}/monitoring-runs", status_code=202)
def run_monitoring(field_id: str, season_id: str, force_refresh: bool = False,
                   user=Depends(require_writer), field=Depends(_field), engine=Depends(get_spatial_engine)):
    # Engine dependency ensures EE initialized; unlike rice signal-runs this
    # generic pipeline is deliberately available to BOTH accounting types.
    # Hands off to the durable worker (Phase 4) instead of an in-process
    # BackgroundTask — reuse-vs-refresh is explicit via force_refresh,
    # honored by backend/job_handlers.handle_multicrop_monitoring.
    season = owned_season(user["org_id"], field_id, season_id)
    if season["payload"]["end_date"] >= datetime.now(timezone.utc).date().isoformat():
        raise HTTPException(422, "Retrospective benchmarks require a completed season ending before today")
    payload = _monitoring_payload(field, season, force_refresh, user["user_id"])
    job_id = create_job(user["org_id"], "multicrop_monitoring", payload)
    return {"job_id": job_id}


@router.post("/fields/{field_id}/crop-seasons/{season_id}/monitoring-runs/{job_id}/cancel")
def cancel_monitoring(field_id: str, season_id: str, job_id: str,
                      user=Depends(require_writer), field=Depends(_field)):
    job = get_job(user["org_id"], job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    request_cancel(user["org_id"], job_id)
    return {"ok": True}


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


@router.post("/multi-crop/benchmarks", status_code=202)
def run_benchmark(body: BenchmarkRequest, user=Depends(require_writer)):
    # Freeze the dataset at submission so concurrent reviews cannot change
    # it — stored in the job's own payload (not a Python closure) so the
    # durable worker (backend/job_handlers.handle_crop_benchmark), which
    # may run in a different process, computes from the exact same frozen
    # corpus rather than re-fetching a possibly-different one later.
    corpus = build_corpus(user["org_id"])
    job_id = create_job(user["org_id"], "crop_benchmark", {
        "corpus": corpus, "split": body.split, "models": body.models, "requested_by": user["user_id"],
    })
    return {"job_id": job_id}
