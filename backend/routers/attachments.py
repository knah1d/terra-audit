"""Document/photo attachments linked to a field, crop season, observation,
or practice event. Files are stored through src.storage's abstraction
(local filesystem today); only metadata lives in the `attachments` table.
Every request is scoped to the caller's org via the field the attachment
is linked to — a season/observation/practice_event id is additionally
checked to actually belong to that field before anything is stored, so an
attachment can never be silently linked to another tenant's record.
"""
import hashlib
import io
import json
import uuid
from sqlalchemy import text

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from backend.config import ALLOWED_ATTACHMENT_CONTENT_TYPES, MAX_ATTACHMENT_SIZE_BYTES
from backend.deps import get_current_user, require_writer
from backend.schemas.attachments import AttachmentOut
from src import monitoring
from src import projects as projects_db
from src.database import get_field, get_db_connection
from src.storage import get_storage, make_storage_key, sanitize_filename

router = APIRouter(tags=["attachments"])


def _validate_target(org_id: str, field_id: str, target_type: str, target_id: str) -> None:
    if target_type not in projects_db.ATTACHMENT_TARGET_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                             f"target_type must be one of {sorted(projects_db.ATTACHMENT_TARGET_TYPES)}")
    if get_field(org_id, field_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    if target_type == "field":
        if target_id != field_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "target_id must equal field_id for target_type 'field'")
        return
    if target_type == "season":
        if monitoring.season(org_id, field_id, target_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Crop season not found on this field")
        return
    table = "field_observations" if target_type == "observation" else "practice_events"
    if not any(r["id"] == target_id for r in monitoring.records(table, org_id, field_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{target_type.replace('_', ' ').title()} not found on this field")


@router.get("/attachments", response_model=list[AttachmentOut])
def list_attachments(target_type: str, target_id: str, user=Depends(get_current_user)):
    return [AttachmentOut(**a) for a in projects_db.list_attachments(user["org_id"], target_type, target_id)]


@router.post("/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    field_id: str = Form(...),
    target_type: str = Form(...),
    target_id: str = Form(...),
    file: UploadFile = None,
    user=Depends(require_writer),
):
    if file is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A file is required")
    _validate_target(user["org_id"], field_id, target_type, target_id)
    if file.content_type not in ALLOWED_ATTACHMENT_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unsupported file type '{file.content_type}'. Allowed: {sorted(ALLOWED_ATTACHMENT_CONTENT_TYPES)}",
        )
    content = await file.read(MAX_ATTACHMENT_SIZE_BYTES + 1)
    if len(content) > MAX_ATTACHMENT_SIZE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds the {MAX_ATTACHMENT_SIZE_BYTES // (1024 * 1024)} MB upload limit",
        )
    filename = sanitize_filename(file.filename or "upload")
    attachment_id = uuid.uuid4().hex
    storage_key = make_storage_key(user["org_id"], attachment_id, filename)
    get_storage().save(storage_key, io.BytesIO(content))
    projects_db.create_attachment(
        user["org_id"], target_type, target_id, field_id, filename, file.content_type,
        len(content), storage_key, sha256=hashlib.sha256(content).hexdigest(),
        uploaded_by=user["user_id"], attachment_id=attachment_id,
    )
    return AttachmentOut(**projects_db.get_attachment(user["org_id"], attachment_id))


@router.get("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: str, user=Depends(get_current_user)):
    attachment = projects_db.get_attachment(user["org_id"], attachment_id)
    if attachment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    with get_storage().open(attachment["storage_key"]) as f:
        content = f.read()
    return Response(content=content, media_type=attachment["content_type"], headers={
        "Content-Disposition": f'attachment; filename="{attachment["filename"]}"',
    })


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: str, user=Depends(require_writer)):
    attachment = projects_db.get_attachment(user["org_id"], attachment_id)
    if attachment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    from src.calculations import referenced_attachment_ids
    with get_db_connection() as conn:
        rows = conn.execute(text("SELECT payload FROM ai_records WHERE org_id=:o AND kind='document'"),
                            {"o": user["org_id"]}).scalars().all()
    if any(json.loads(r).get("attachment_id") == attachment_id for r in rows):
        raise HTTPException(409, "This attachment is retained as evidence for an AI document review.")
    if attachment_id in referenced_attachment_ids(user["org_id"]):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This attachment is referenced by a committed calculation's evidence snapshot and cannot be deleted.",
        )
    get_storage().delete(attachment["storage_key"])
    projects_db.delete_attachment_record(user["org_id"], attachment_id)
    return None
