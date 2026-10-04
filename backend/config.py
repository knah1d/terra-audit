"""Central backend configuration; production rejects unsafe development defaults."""

import os
import re
import warnings
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# Render's managed runtime is production even if APP_ENV was omitted.
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
if APP_ENV not in {"development", "test", "production"}:
    raise RuntimeError("APP_ENV must be development, test, or production")
IS_PRODUCTION = APP_ENV == "production" or os.environ.get("RENDER", "").lower() == "true"


def _frontend_url():
    from urllib.parse import urlsplit
    from ipaddress import ip_address
    value = os.environ.get("FRONTEND_PUBLIC_URL", "").strip().rstrip("/")
    if not value:
        if IS_PRODUCTION:
            raise RuntimeError("FRONTEND_PUBLIC_URL is required in production; set the public HTTPS frontend origin")
        value = "http://localhost:3000"
    try:
        parts = urlsplit(value)
        _ = parts.port  # Validate malformed ports.
        host = parts.hostname or ""
        invalid = (parts.scheme not in {"http", "https"} or not host or
                   parts.username is not None or parts.password is not None or
                   parts.query or parts.fragment or parts.path not in {"", "/"})
        local = host.lower() == "localhost" or host.lower().endswith(".localhost") or host.lower().endswith(".local")
        try:
            address = ip_address(host)
            local = local or address.is_loopback or address.is_unspecified
        except ValueError:
            pass
        if invalid or (IS_PRODUCTION and (parts.scheme != "https" or local)):
            raise ValueError()
    except ValueError:
        raise RuntimeError("FRONTEND_PUBLIC_URL must be a frontend origin without a path, credentials, query, or fragment; production requires HTTPS and a non-local host") from None
    return value


FRONTEND_PUBLIC_URL = _frontend_url()

_DEV_ONLY_JWT_SECRET = "dev-only-insecure-secret-change-me"

JWT_SECRET = os.environ.get("JWT_SECRET", "").strip()
if IS_PRODUCTION and (len(JWT_SECRET) < 32 or JWT_SECRET == _DEV_ONLY_JWT_SECRET):
    raise RuntimeError("JWT_SECRET must be a private secret of at least 32 characters in production")
if not JWT_SECRET:
    JWT_SECRET = _DEV_ONLY_JWT_SECRET
    warnings.warn(
        "JWT_SECRET not set — using an insecure development-only default. "
        "Set JWT_SECRET in .env before deploying this anywhere real.",
        stacklevel=2,
    )

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "720"))  # 12h default

# CORS — regex (not a fixed origin list) because a Vercel-hosted frontend
# gets a new preview subdomain per branch/PR that can't be enumerated in
# advance (e.g. https://terra-audit-git-foo-<team>.vercel.app). Defaults to
# local dev only; set this in the deployment env to your real frontend
# domain(s), e.g. "https://terra-audit\.vercel\.app|https://.*-<team>\.vercel\.app".
ALLOWED_ORIGIN_REGEX = os.environ.get("ALLOWED_ORIGIN_REGEX", r"http://localhost:3000" if not IS_PRODUCTION else re.escape(FRONTEND_PUBLIC_URL))
try:
    re.compile(ALLOWED_ORIGIN_REGEX)
except re.error:
    raise RuntimeError("ALLOWED_ORIGIN_REGEX must be a valid regular expression") from None

# Self-serve org signup (OTP email verification) — see
# .claude/plans/misty-growing-yao.md. Sent via Brevo's HTTPS API, not
# SMTP: several PaaS hosts (Railway confirmed, by direct testing) silently
# drop outbound traffic on SMTP ports 587/465 for anti-abuse reasons —
# connections hang until timeout rather than being refused. HTTPS (443)
# doesn't have this problem. (SendGrid was tried first — its new-account
# fraud review locked the account out entirely before it could even be
# used; Brevo's signup/verification flow doesn't have that problem.)
# BREVO_API_KEY has no safe default (there's no dev-only fallback the way
# JWT_SECRET has a fallback string); instead backend/email_util.py falls
# back to logging the OTP when it's unset, so local dev works without a
# real Brevo account. EMAIL_FROM must exactly match a sender verified in
# Brevo (single-sender verification — doesn't require owning a domain).
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "no-reply@terra-audit.local")

EMAIL_CONFIGURED = bool(BREVO_API_KEY)
if not EMAIL_CONFIGURED:
    warnings.warn(
        "BREVO_API_KEY not set — registration OTPs will be logged to "
        "stdout instead of emailed. Set BREVO_API_KEY (and EMAIL_FROM, "
        "verified in your Brevo account) in .env before deploying this "
        "anywhere real.",
        stacklevel=2,
    )

WORKER_POLL_INTERVAL_SECONDS = float(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", "2"))
WORKER_HEARTBEAT_INTERVAL_SECONDS = float(os.environ.get("WORKER_HEARTBEAT_INTERVAL_SECONDS", "15"))
MAX_CONCURRENT_JOBS_PER_ORG = int(os.environ.get("MAX_CONCURRENT_JOBS_PER_ORG", "3"))
MAX_BULK_MONITORING_ITEMS = int(os.environ.get("MAX_BULK_MONITORING_ITEMS", "100"))

OTP_EXPIRE_MINUTES = int(os.environ.get("OTP_EXPIRE_MINUTES", "10"))
OTP_MAX_ATTEMPTS = int(os.environ.get("OTP_MAX_ATTEMPTS", "5"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.environ.get("OTP_RESEND_COOLDOWN_SECONDS", "60"))

# Document/photo attachments (Phase 1 — see docs/MULTICROP.md). Files
# themselves live under ATTACHMENTS_DIR (see src/persistence/storage.py), not in the
# database; only metadata is stored in the `attachments` table.
MAX_ATTACHMENT_SIZE_BYTES = int(os.environ.get("MAX_ATTACHMENT_SIZE_BYTES", str(15 * 1024 * 1024)))
ALLOWED_ATTACHMENT_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/heic",
    "application/pdf", "text/csv", "text/plain", "application/json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
