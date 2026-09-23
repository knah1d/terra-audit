"""Project AI workspace; jobs never mutate accounting or review approvals."""
import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from backend.deps import get_current_user
from backend.schemas.monitoring import ObservationCreate
from src.ai import workspace as ws
from src.ai.assistant import configured
from src.database import get_db_connection, get_field
from src.jobs import create_job, get_job_row, request_cancel
from src.monitoring import records, season, digest
from src.projects import get_attachment, get_project_member

router = APIRouter(prefix="/projects/{project_id}/ai", tags=["AI workspace"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Train(Strict):
    name: str = Field(min_length=1, max_length=120)
    model: Literal["random_forest", "xgboost"] = "random_forest"
    split: Literal["field", "year", "district"] = "field"


class Deploy(Strict):
    model_id: str | None = None
    threshold: float = Field(default=0.8, ge=0.5, le=1)
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=5, max_length=2000)


class Predict(Strict):
    field_id: str
    season_id: str


class Ask(Strict):
    question: str = Field(min_length=3, max_length=4000)


class Extract(Predict):
    attachment_id: str
    extraction_mode: Literal["auto", "text", "vision"] = "auto"


class Review(Strict):
    decision: Literal["accepted", "rejected"]
    reason: str = Field(min_length=3, max_length=2000)
    observed_at: datetime | None = None
    value: str | None = Field(default=None, min_length=1, max_length=500)
    confirmed_against_original: bool = False


def access(user, project_id, lead=False):
    try:
        ws.authorize(user["org_id"], project_id, user["user_id"], lead)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


def field_season(user, project_id, field_id, season_id):
    if field_id not in ws.active_fields(user["org_id"], project_id) or not get_field(user["org_id"], field_id):
        raise HTTPException(404, "Active project field not found")
    row = season(user["org_id"], field_id, season_id)
    if not row:
        raise HTTPException(404, "Season not found on this field")
    return row


def submit(user, project_id, kind, payload):
    with get_db_connection() as conn:
        count = conn.execute(text("""SELECT COUNT(*) FROM background_jobs WHERE org_id=:o
            AND job_type LIKE 'workspace_%' AND status IN ('pending','running','cancel_requested')"""), {"o": user["org_id"]}).scalar()
    if count >= 10:
        raise HTTPException(429, "Ten AI jobs are already pending; wait for them to finish")
    return {"job_id": create_job(user["org_id"], "workspace_" + kind,
            {**payload, "project_id": project_id, "requested_by": user["user_id"]},
            max_attempts=1 if kind in {"answer", "document"} else 3)}


@router.get("")
def overview(project_id: str, user=Depends(get_current_user)):
    access(user, project_id)
    fields = ws.active_fields(user["org_id"], project_id)
    options = []
    attachments = []
    for fid in sorted(fields):
        current = {r["season_id"]: r for r in records("crop_seasons", user["org_id"], fid)}
        f = get_field(user["org_id"], fid)
        for sid, r in current.items():
            options.append({"field_id": fid, "field_name": (f or {}).get("name", fid), "season_id": sid,
                            "name": r["payload"]["name"], "crops": r["payload"]["crops"]})
        with get_db_connection() as conn:
            rows = conn.execute(text("SELECT attachment_id,filename,field_id,content_type FROM attachments WHERE org_id=:o AND field_id=:f"),
                                {"o": user["org_id"], "f": fid}).mappings().all()
        attachments.extend(dict(r) for r in rows)
    all_records = ws.entries(user["org_id"], project_id)
    # History stays with the project; snapshots reflect membership at creation.
    with get_db_connection() as conn:
        rows = conn.execute(text("""SELECT job_id,status,job_type,error,created_at,payload_json FROM background_jobs
            WHERE org_id=:o AND job_type LIKE 'workspace_%' ORDER BY created_at DESC LIMIT 200"""), {"o": user["org_id"]}).mappings().all()
    jobs = [{k: v for k, v in r.items() if k != "payload_json"} for r in rows
            if json.loads(r["payload_json"])["project_id"] == project_id][:30]
    from src.ai.document_ocr import vision_configured
    return {"records": all_records, "deployment": ws.deployment(user["org_id"], project_id),
            "vision_configured": vision_configured(),
            "assistant_configured": configured(), "seasons": options, "attachments": attachments, "jobs": jobs,
            "can_manage": user["role"] in {"admin", "analyst"} and (user["role"] == "admin" or
                get_project_member(user["org_id"], project_id, user["user_id"])["project_role"] == "lead")}


@router.get("/corpus")
def corpus(project_id: str, user=Depends(get_current_user)):
    access(user, project_id)
    return ws.frozen_corpus(user["org_id"], project_id)


@router.post("/train", status_code=202)
def train(project_id: str, body: Train, user=Depends(get_current_user)):
    access(user, project_id, True)
    corpus = ws.frozen_corpus(user["org_id"], project_id)
    if len(corpus["examples"]) > 2000:
        raise ValueError("This training worker supports at most 2,000 eligible field-seasons per project")
    from src.ai.crop_benchmark import make_splits
    if len(corpus["examples"]) < 4 or len({r["crop"] for r in corpus["examples"]}) < 2:
        raise ValueError("Need four eligible field-seasons across two crops, with accepted independent labels")
    make_splits(corpus["examples"], body.split)
    return submit(user, project_id, "train", {**body.model_dump(), "corpus": corpus})


@router.put("/deployment")
def deploy(project_id: str, body: Deploy, user=Depends(get_current_user)):
    access(user, project_id, True)
    return ws.set_deployment(user["org_id"], project_id, body.model_id, body.threshold,
                             body.expected_revision, user["user_id"], body.reason)


@router.post("/predict", status_code=202)
def predict(project_id: str, body: Predict, user=Depends(get_current_user)):
    access(user, project_id, True)
    s = field_season(user, project_id, body.field_id, body.season_id)
    deployment = ws.deployment(user["org_id"], project_id)
    if not deployment["model_id"]:
        raise ValueError("Activate an evaluated model first")
    runs = records("monitoring_runs", user["org_id"], body.field_id, body.season_id)
    if not runs:
        raise ValueError("Collect satellite observations for this season first")
    return submit(user, project_id, "prediction", {**body.model_dump(), "run": runs[-1], "season": s,
                  "model_id": deployment["model_id"], "threshold": deployment["threshold"], "deployment_revision": deployment["revision"]})


@router.post("/ask", status_code=202)
def ask(project_id: str, body: Ask, user=Depends(get_current_user)):
    access(user, project_id, True)
    if not configured():
        raise HTTPException(503, "Set OPENAI_API_KEY and OPENAI_MODEL on the API and worker")
    return submit(user, project_id, "answer", body.model_dump())


@router.post("/documents", status_code=202)
def extract(project_id: str, body: Extract, user=Depends(get_current_user)):
    access(user, project_id, True)
    field_season(user, project_id, body.field_id, body.season_id)
    a = get_attachment(user["org_id"], body.attachment_id)
    if not a or a["field_id"] != body.field_id:
        raise HTTPException(404, "Attachment not found on this field")
    from src.ai.document_ocr import SUPPORTED_TYPES, IMAGE_TYPES, vision_configured
    if a["content_type"] not in SUPPORTED_TYPES:
        raise ValueError("Unsupported extraction format; use PDF, DOCX, text/CSV, JPEG, PNG, or WebP")
    if body.extraction_mode == "text" and a["content_type"] in IMAGE_TYPES:
        raise ValueError("Images require automatic or visual extraction mode")
    if body.extraction_mode == "vision" and a["content_type"] not in IMAGE_TYPES | {"application/pdf"}:
        raise ValueError("Visual mode supports PDF and JPEG/PNG/WebP images")
    if (a["content_type"] in IMAGE_TYPES or body.extraction_mode == "vision") and not vision_configured():
        raise HTTPException(503, "Configure OPENAI_VISION_MODEL to enable visual extraction")
    if not configured():
        raise HTTPException(503, "Set OPENAI_API_KEY and OPENAI_MODEL on the API and worker")
    return submit(user, project_id, "document", body.model_dump())


@router.post("/documents/{document_id}/proposals/{index}/review")
def review_document(project_id: str, document_id: str, index: int, body: Review, user=Depends(get_current_user)):
    access(user, project_id, True)
    org = user["org_id"]
    doc = ws.get_entry(org, project_id, document_id, "document")["payload"]
    field_season(user, project_id, doc["field_id"], doc["season_id"])
    if index < 0 or index >= len(doc["proposals"]):
        raise HTTPException(404, "Proposal not found")
    proposal = doc["proposals"][index]
    rid = digest({"document_id": document_id, "index": index})
    observation = None
    if body.decision == "accepted":
        if proposal.get("requires_visual_confirmation") and not body.confirmed_against_original:
            raise ValueError("Confirm the OCR quote against the original page before accepting it")
        if not body.observed_at:
            raise ValueError("Confirm an observation timestamp including timezone")
        observation = ObservationCreate(observed_at=body.observed_at, kind=proposal["kind"], source="document",
            value=body.value or proposal["value"], evidence_reference=f"attachment:{doc['attachment_id']}#page={proposal['page']}",
            notes=body.reason).model_dump(mode="json")
        observation.update(created_by=user["user_id"], ai_document_id=document_id, ai_proposal_index=index)
    payload = {"document_id": document_id, "proposal_index": index, "decision": body.decision,
               "reason": body.reason, "actor": user["user_id"], "observation_id": rid if observation else None,
               "observation": observation, "confirmed_against_original": body.confirmed_against_original,
               "source_text_sha256": proposal.get("source_text_sha256")}
    with get_db_connection() as conn:
        # Claim the proposal and write its observation in the SAME transaction.
        existing = conn.execute(text("SELECT payload FROM ai_records WHERE id=:i AND org_id=:o AND project_id=:p"),
                                {"i": rid, "o": org, "p": project_id}).scalar()
        if existing:
            previous = json.loads(existing)
            if previous != payload:
                raise HTTPException(409, "This proposal has already been reviewed")
            return previous
        ws.append(org, project_id, "document_review", payload, rid, conn)
        # A concurrent reviewer may have won the unique insertion.
        stored = json.loads(conn.execute(text("SELECT payload FROM ai_records WHERE id=:i"), {"i": rid}).scalar())
        if stored != payload:
            raise HTTPException(409, "Another reviewer already decided this proposal")
        if observation:
            conn.execute(text("""INSERT INTO field_observations(id,org_id,field_id,season_id,created_at,payload)
                VALUES (:id,:org,:field,:season,:created,:payload) ON CONFLICT(id) DO NOTHING"""),
                {"id": rid, "org": org, "field": doc["field_id"], "season": doc["season_id"],
                 "created": datetime.now(timezone.utc).isoformat(), "payload": json.dumps(observation)})
        conn.commit()
    return payload


@router.get("/documents/{document_id}/source")
def document_source(project_id: str, document_id: str, user=Depends(get_current_user)):
    access(user, project_id)
    doc = ws.get_entry(user["org_id"], project_id, document_id, "document")["payload"]
    attachment = get_attachment(user["org_id"], doc["attachment_id"])
    if not attachment or attachment["field_id"] != doc["field_id"]:
        raise HTTPException(404, "Original attachment is unavailable")
    if attachment["sha256"] != doc["attachment_sha256"]:
        raise HTTPException(409, "Original attachment no longer matches this extraction")
    from src.ai.assistant import read_attachment
    return Response(read_attachment(attachment), media_type=attachment["content_type"],
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/jobs/{job_id}")
def job(project_id: str, job_id: str, user=Depends(get_current_user)):
    access(user, project_id)
    row = get_job_row(user["org_id"], job_id)
    if not row or not row["job_type"].startswith("workspace_") or row["payload"].get("project_id") != project_id:
        raise HTTPException(404, "AI job not found")
    return {k: row[k] for k in ("job_id", "status", "result", "error")}


@router.post("/jobs/{job_id}/cancel")
def cancel(project_id: str, job_id: str, user=Depends(get_current_user)):
    access(user, project_id, True)
    job(project_id, job_id, user)
    request_cancel(user["org_id"], job_id)
    return {"status": "cancellation_requested"}
