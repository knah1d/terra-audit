"""
Backend settings — .claude/plans/misty-growing-yao.md Part A1/A2.

Plain os.environ reads, not pydantic-settings: this app already has a
single .env-loading convention (python-dotenv, used by src/data_engine.py
for EE_PROJECT and src/database.py for DATABASE_URL) — adding a second
settings framework for 3 values isn't justified. JWT_SECRET has no safe
default in a real deployment; it falls back to a fixed dev-only string
ONLY so `uvicorn backend.main:app` works out of the box for local
development, with a loud warning so nobody ships that fallback by accident.
"""

import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

_DEV_ONLY_JWT_SECRET = "dev-only-insecure-secret-change-me"

JWT_SECRET = os.environ.get("JWT_SECRET")
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
ALLOWED_ORIGIN_REGEX = os.environ.get("ALLOWED_ORIGIN_REGEX", r"http://localhost:3000")

# Self-serve org signup (OTP email verification) — see
# .claude/plans/misty-growing-yao.md. SMTP_* has no safe default (there's
# no dev-only fallback server the way JWT_SECRET has a fallback string);
# instead backend/email_util.py falls back to logging the OTP when SMTP
# isn't fully configured, so local dev works without a real mail server.
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@terra-audit.local")

SMTP_CONFIGURED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)
if not SMTP_CONFIGURED:
    warnings.warn(
        "SMTP_* not fully configured — registration OTPs will be logged to "
        "stdout instead of emailed. Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD in "
        ".env before deploying this anywhere real.",
        stacklevel=2,
    )

OTP_EXPIRE_MINUTES = int(os.environ.get("OTP_EXPIRE_MINUTES", "10"))
OTP_MAX_ATTEMPTS = int(os.environ.get("OTP_MAX_ATTEMPTS", "5"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.environ.get("OTP_RESEND_COOLDOWN_SECONDS", "60"))
