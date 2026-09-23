from datetime import datetime

from pydantic import BaseModel


class AttachmentOut(BaseModel):
    attachment_id: str
    target_type: str
    target_id: str
    field_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    uploaded_by: str | None
    uploaded_at: datetime | None
