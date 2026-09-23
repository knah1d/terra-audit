"""Configuration and onboarding visibility without secret values."""
import importlib.util
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from backend.deps import require_admin
from backend.config import JWT_SECRET, _DEV_ONLY_JWT_SECRET, EMAIL_CONFIGURED
from src.database import get_db_connection, is_sqlite
from src.ai.assistant import configured

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
        {"name": "AI assistant configuration", "ready": configured(), "detail": "Requires OPENAI_API_KEY and OPENAI_MODEL on API and worker. Configuration presence only; no provider call performed."},
        {"name": "Recovery email", "ready": EMAIL_CONFIGURED, "detail": "Brevo key and verified sender are required. Delivery is not probed."},
        {"name": "Public account links", "ready": os.environ.get("FRONTEND_PUBLIC_URL", "").startswith("https://"), "detail": "Set FRONTEND_PUBLIC_URL to the HTTPS frontend address."},
        {"name": "Shared file storage", "ready": storage == "s3" and bool(os.environ.get("S3_BUCKET")), "detail": "S3 configuration is present." if storage == "s3" else "Local storage: API and worker must mount the same persistent directory."},
        {"name": "PDF extraction dependency", "ready": importlib.util.find_spec("pypdf") is not None, "detail": "Install the updated backend requirements."},
    ]
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "checks": checks, "counts": {**counts, "models": models},
            "queued_jobs": queued, "notice": "Configuration checks do not establish production readiness. Confirm delivery, storage access and backup restoration in your environment."}
