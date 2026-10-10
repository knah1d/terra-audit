"""Configuration and onboarding visibility without secret values."""
import importlib.util
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from backend.deps import require_admin
from backend.config import JWT_SECRET, _DEV_ONLY_JWT_SECRET, EMAIL_CONFIGURED
from src.persistence.database import get_db_connection, is_sqlite
from src.ai.assistant import configured
from src.ai.providers import provider_status

router = APIRouter(tags=["product operations"])


@router.get("/admin/product-readiness")
def readiness(user=Depends(require_admin)):
    org = user["org_id"]
    with get_db_connection() as conn:
        conn.execute(text("SELECT 1"))
        counts = {table: conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE org_id=:o"), {"o": org}).scalar()
                  for table in ("fields", "projects", "crop_seasons", "field_observations", "attachments")}
        models = conn.execute(text("SELECT COUNT(*) FROM ai_records WHERE org_id=:o AND kind='model'"), {"o": org}).scalar()
        queued = conn.execute(text("SELECT COUNT(*) FROM background_jobs WHERE org_id=:o AND status IN ('pending','running','cancel_requested')"), {"o": org}).scalar()
    storage = os.environ.get("STORAGE_BACKEND", "local")
    checks = [
        {"name": "Database", "ready": True, "detail": "SQLite" if is_sqlite() else "PostgreSQL"},
        {"name": "Session signing", "ready": JWT_SECRET != _DEV_ONLY_JWT_SECRET and len(JWT_SECRET) >= 32, "detail": "Use a private secret of at least 32 characters."},
        {"name": "AI assistant configuration", "ready": configured(for_generation=False), "detail": provider_status()["configuration_hint"] + " Configuration presence only; worker credentials and provider connectivity are not verified."},
        {"name": "Recovery email", "ready": EMAIL_CONFIGURED, "detail": "Brevo key and verified sender are required. Delivery is not probed."},
        {"name": "Public account links", "ready": os.environ.get("FRONTEND_PUBLIC_URL", "").startswith("https://"), "detail": "Set FRONTEND_PUBLIC_URL to the HTTPS frontend address."},
        {"name": "Shared file storage", "ready": storage == "s3" and bool(os.environ.get("S3_BUCKET")), "detail": "S3 configuration is present." if storage == "s3" else "Local storage: API and worker must mount the same persistent directory."},
        {"name": "PDF extraction dependency", "ready": importlib.util.find_spec("pypdf") is not None, "detail": "Install the updated backend requirements."},
    ]
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "checks": checks, "counts": {**counts, "models": models},
            "queued_jobs": queued, "notice": "Configuration checks do not establish production readiness. Confirm delivery, storage access and backup restoration in your environment."}


@router.get("/admin/accounting-conflicts")
def accounting_conflicts(user=Depends(require_admin)):
    """Existing double counting (reviewable project calculations overlapping
    for the same field and pathway) and fields in more than one project at the
    same time — both created before the guards existed. Listed for admins to
    resolve; never rewritten automatically."""
    from src.carbon.calculations import accounting_conflicts as find_conflicts
    from src.projects.repository import overlapping_project_memberships
    return {"conflicts": find_conflicts(user["org_id"]),
            "overlapping_memberships": overlapping_project_memberships(user["org_id"])}


@router.get("/admin/ai-provider-permission")
def get_ai_provider_permission(user=Depends(require_admin)):
    """Whether this organization lets project evidence go to the configured
    external AI provider (Groq or OpenAI) for explanations."""
    from src.ai import workspace as ws
    from src.ai.providers import provider_name
    name = provider_name()
    external = name in {"groq", "openai"}
    return {"provider": name, "external": external,
            "allowed": ws.provider_allowed(user["org_id"], name) if external else True}


class ProviderPermissionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed: bool


@router.put("/admin/ai-provider-permission")
def set_ai_provider_permission(body: ProviderPermissionUpdate, user=Depends(require_admin)):
    from fastapi import HTTPException
    from src.ai import workspace as ws
    from src.ai.providers import provider_name
    name = provider_name()
    if name not in {"groq", "openai"}:
        raise HTTPException(422, "Only an external AI provider (groq or openai) needs this permission.")
    return ws.set_provider_allowed(user["org_id"], name, body.allowed, user["user_id"])
