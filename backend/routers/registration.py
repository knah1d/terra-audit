"""
Self-serve org signup with email OTP verification
(.claude/plans/misty-growing-yao.md).

Two endpoints: request-otp (org name + email + password -> emails a
6-digit code) and verify-otp (email + code -> creates the org + its
first admin user, returns a JWT so the user is logged in immediately —
they've already proven both password and email control by this point,
so a separate login step is pure friction).

Deliberate trade-off: request-otp returns a specific 409 when the email
already belongs to a real user, rather than a generic response designed
to resist email enumeration. This matches src.auth.create_org_user's
existing behavior for the admin-invite flow (a specific ValueError on
duplicate email) — consistency with that precedent outweighs an
enumeration concern this B2B app doesn't otherwise defend against
(the login endpoint's 401 already doesn't distinguish wrong-password
from no-such-user, but leaking valid credentials is a different, much
higher-severity threat than leaking "an account with this email exists").
"""

import hashlib
import hmac
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status

from backend.config import (
    JWT_EXPIRE_MINUTES,
    JWT_SECRET,
    OTP_EXPIRE_MINUTES,
    OTP_MAX_ATTEMPTS,
    OTP_RESEND_COOLDOWN_SECONDS,
)
from backend.email_util import EmailSendError, send_otp_email
from backend.schemas.auth import TokenResponse
from backend.schemas.registration import RegisterOtpSentResponse, RegisterRequest, VerifyOtpRequest
from backend.security import create_access_token
from src.auth import get_user_by_email, hash_password
from src.database import (
    get_pending_registration,
    record_otp_attempt_failure,
    upsert_pending_registration,
    verify_and_create_org,
)

router = APIRouter(tags=["registration"])

# Per-IP rate limiting on request-otp: a module-level in-process sliding
# window, the same "acceptable single-process state" posture this
# codebase already takes for src.database's _ENGINE/_DB_INITIALIZED
# globals and backend.main's app.state.spatial_engine. A multi-worker or
# multi-instance deployment would need this moved to the DB or a shared
# cache — flagged here, not solved, since this app runs a single uvicorn
# process today.
_ip_request_log: dict[str, list[float]] = {}
_IP_WINDOW_SECONDS = 3600
_IP_MAX_REQUESTS = 10


def _check_ip_rate_limit(ip: str):
    now = time.monotonic()
    recent = [t for t in _ip_request_log.get(ip, []) if now - t < _IP_WINDOW_SECONDS]
    if len(recent) >= _IP_MAX_REQUESTS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many registration attempts from this network — try again later",
        )
    recent.append(now)
    _ip_request_log[ip] = recent


def _hash_otp(otp: str, registration_id: str) -> str:
    # sha256, not bcrypt: a 6-digit code has only 10^6 values, so bcrypt's
    # cost factor buys nothing against brute force here — attempt_count/
    # max_attempts is the actual defense. sha256 salted with
    # registration_id (unique, unpredictable) just keeps a raw DB read
    # from handing over the live code, at negligible cost.
    return hashlib.sha256(f"{otp}:{registration_id}".encode()).hexdigest()


@router.post("/auth/register/request-otp", response_model=RegisterOtpSentResponse)
def request_otp(body: RegisterRequest, request: Request):
    email = body.email.strip().lower()
    org_name = body.org_name.strip()
    if not org_name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Organization name is required")
    if len(body.password) < 8:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Password must be at least 8 characters")

    if get_user_by_email(email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    client_ip = request.client.host if request.client else "unknown"
    _check_ip_rate_limit(client_ip)

    otp = f"{secrets.randbelow(1_000_000):06d}"
    registration_id = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)

    try:
        upsert_pending_registration(
            registration_id=registration_id,
            email=email,
            org_name=org_name,
            password_hash=hash_password(body.password),
            otp_hash=_hash_otp(otp, registration_id),
            expires_at=expires_at.isoformat(),
            resend_cooldown_seconds=OTP_RESEND_COOLDOWN_SECONDS,
            max_attempts=OTP_MAX_ATTEMPTS,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc

    try:
        send_otp_email(email, otp)
    except EmailSendError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return RegisterOtpSentResponse(email=email, expires_in_seconds=OTP_EXPIRE_MINUTES * 60)


@router.post("/auth/register/verify-otp", response_model=TokenResponse)
def verify_otp(body: VerifyOtpRequest):
    email = body.email.strip().lower()
    row = get_pending_registration(email)
    if row is None:
        # Distinguish "already completed" (e.g. the losing side of a
        # concurrent double-verify, or a stale retry after success) from
        # "never requested a code" — the former is a 409, not a 400.
        if get_user_by_email(email) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "This registration was already completed")
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No pending registration for this email")

    expires_at = _parse_timestamp(row["expires_at"])
    if expires_at is not None and datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status.HTTP_410_GONE, "This code has expired — request a new one")

    if row["attempt_count"] >= row["max_attempts"]:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many incorrect attempts — request a new code",
        )

    expected_hash = _hash_otp(body.otp.strip(), row["registration_id"])
    if not hmac.compare_digest(expected_hash, row["otp_hash"]):
        record_otp_attempt_failure(row["registration_id"])
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid code")

    org_id = uuid.uuid4().hex
    user_id = uuid.uuid4().hex
    user = verify_and_create_org(row["registration_id"], org_id, user_id)
    if user is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This registration was already completed or the email is no longer available",
        )

    token = create_access_token(user, JWT_SECRET, JWT_EXPIRE_MINUTES)
    return TokenResponse(access_token=token)


def _parse_timestamp(value) -> datetime | None:
    """expires_at comes back from SQLAlchemy as either a datetime
    (Postgres) or an ISO string (SQLite stores what we wrote via
    .isoformat()) — normalize both to an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value)
