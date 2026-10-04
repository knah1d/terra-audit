"""Tenant-scoped, read-access AI explanation requests and history."""
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from backend.deps import get_current_user, require_admin
from src.ai import workspace as ws
from src.ai.explanations import packet_for, cached
from src.ai.providers import configured, provider_name
from src.jobs.queue import create_job, get_job_row

router = APIRouter(prefix="/projects/{project_id}/ai", tags=["AI explanations"])


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["explain_block", "missing_evidence", "applicable_requirements", "explain_leakage", "diff_since_previous"]
    field_id: str = Field(min_length=1)
    calculation_id: str | None = None
    assessment_id: str | None = None
    monitoring_period_start: str | None = None
    monitoring_period_end: str | None = None
    season_ids: list[str] | None = None
    requirement_id: str | None = None


def access(user, project_id, field_id=None):
    try:
        ws.authorize(user["org_id"], project_id, user["user_id"])
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    if field_id is not None and field_id not in ws.active_fields(user["org_id"], project_id):
        raise HTTPException(404, "Field is not an active member of this project. Assign it under Project fields and check membership dates before requesting an explanation.")


@router.post("/explain")
def request_explanation(project_id: str, body: ExplainRequest, user=Depends(get_current_user)):
    from src.ai.timing import StageTimings
    timings = StageTimings("api")
    with timings.measure("authorization"):
        access(user, project_id, body.field_id)
    request = body.model_dump(exclude_none=True)
    try:
        with timings.measure("packet_build"):
            packet = packet_for(user["org_id"], project_id, user["user_id"], request)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except TypeError as exc:
        raise HTTPException(422, "Parameters do not match the selected explanation action") from exc
    with timings.measure("cache_lookup"):
        saved = cached(user["org_id"], project_id, packet)
    if saved:
        return {"explanation": saved["payload"], "record_id": saved["id"], "request_timings_seconds": timings.snapshot()}
    name = provider_name()
    if packet.get("call_model", True) and name in {"openai", "groq"} and not ws.provider_allowed(user["org_id"], name):
        raise HTTPException(403, f"An organization administrator must enable {name} external-provider access")
    if packet.get("call_model", True) and not configured(for_generation=False):
        raise HTTPException(503, "Configure the selected AI_PROVIDER and model on the API and worker; Groq additionally needs GROQ_API_KEY on the worker")
    payload = {"project_id": project_id, "requested_by": user["user_id"], "request": request,
               "context_sha256": packet["context_sha256"], "evidence_fingerprint": packet["evidence_fingerprint"],
               "generation_signature": packet["generation_signature"]}
    # Include requester/project identity: a revoked user's pending request must
    # never be shared as the executable job for another reader.
    key = f"{project_id}:{user['user_id']}:{body.action}:{body.field_id}:{packet['context_sha256']}:{packet['generation_signature']}"
    # Terminal failures may be retried explicitly; successful/in-flight jobs
    # retain their stable key and cache behavior.
    from sqlalchemy import text
    from src.persistence.database import get_db_connection
    with get_db_connection() as conn:
        previous = conn.execute(text("SELECT job_id,status FROM background_jobs WHERE org_id=:o AND job_type='ai_explain' AND idempotency_key=:k"),
                                {"o": user["org_id"], "k": key}).mappings().first()
    while previous and previous["status"] in {"error", "cancelled"}:
        key += ":retry:" + previous["job_id"]
        with get_db_connection() as conn:
            previous = conn.execute(text("SELECT job_id,status FROM background_jobs WHERE org_id=:o AND job_type='ai_explain' AND idempotency_key=:k"),
                                    {"o": user["org_id"], "k": key}).mappings().first()
    with timings.measure("enqueue"):
        job_id = create_job(user["org_id"], "ai_explain", payload, idempotency_key=key, max_attempts=1)
    return JSONResponse({"job_id": job_id, "request_timings_seconds": timings.snapshot()}, status_code=202)


@router.get("/explain/jobs/{job_id}")
def explanation_job(project_id: str, job_id: str, user=Depends(get_current_user)):
    access(user, project_id)
    job = get_job_row(user["org_id"], job_id)
    if not job or job["job_type"] != "ai_explain":
        raise HTTPException(404, "Explanation job not found")
    payload = json.loads(job["payload_json"])
    if payload.get("project_id") != project_id:
        raise HTTPException(404, "Explanation job not found")
    access(user, project_id, payload["request"]["field_id"])
    result = {k: job.get(k) for k in ("job_id", "status", "error", "created_at")}
    if job["status"] == "done":
        result["explanation"] = ws.get_entry(user["org_id"], project_id, job_id, "explanation")["payload"]
    return result


@router.get("/explanations")
def explanation_history(project_id: str, field_id: str | None = None, calculation_id: str | None = None,
                        user=Depends(get_current_user)):
    access(user, project_id, field_id)
    active = ws.active_fields(user["org_id"], project_id)
    return [row for row in ws.entries(user["org_id"], project_id, "explanation")
            if row["payload"].get("field_id") in active
            and (field_id is None or row["payload"].get("field_id") == field_id)
            and (calculation_id is None or row["payload"].get("calculation_id") == calculation_id)]


class ProviderPermission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed: bool
    provider: Literal["openai", "groq"] = "openai"


@router.get("/provider-permission")
def provider_permission(project_id: str, provider: Literal["openai", "groq"] = "openai", user=Depends(get_current_user)):
    access(user, project_id)
    return {"provider": provider, "allowed": ws.provider_allowed(user["org_id"], provider)}


@router.put("/provider-permission")
def update_provider_permission(project_id: str, body: ProviderPermission, user=Depends(require_admin)):
    access(user, project_id)
    return ws.set_provider_allowed(user["org_id"], body.provider, body.allowed, user["user_id"])
