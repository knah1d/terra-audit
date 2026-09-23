import json
import os
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.config import BREVO_API_KEY, EMAIL_FROM
from backend.deps import require_admin
from src import account_access as accounts
from src.auth import get_user_by_email
from typing import Literal

router = APIRouter(tags=["account access"])


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def email_address(cls, value):
        value = value.strip().lower()
        if value.count("@") != 1 or any(c.isspace() for c in value):
            raise ValueError("Enter a valid email address")
        return value


class Invitation(EmailRequest):
    role: Literal["admin", "analyst", "viewer"] = "analyst"


class Consume(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=12, max_length=72)


def link_url(token):
    base = os.environ.get("FRONTEND_PUBLIC_URL", "http://localhost:3000").rstrip("/")
    parts = urlsplit(base)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.query or parts.fragment or parts.username:
        raise ValueError("FRONTEND_PUBLIC_URL must be an absolute frontend URL")
    return f"{base}/account-access#token={token}"


@router.post("/team/invitations", status_code=201)
def invite(body: Invitation, user=Depends(require_admin)):
    if get_user_by_email(body.email):
        raise HTTPException(409, "An account already exists for this email")
    if not accounts.throttle("invite:" + user["org_id"], 30, 3600):
        raise HTTPException(429, "Invitation limit reached; try again later")
    link_url("validate")
    token = accounts.create_link(user["org_id"], body.email, "invite", body.role, user["user_id"])
    return {"invitation_url": link_url(token), "expires_in_hours": 48,
            "delivery": "Share this one-time link with the intended teammate. It is not emailed automatically."}


@router.post("/auth/recovery/request")
def request_recovery(body: EmailRequest, request: Request):
    if not BREVO_API_KEY:
        raise HTTPException(503, "Password recovery email is not configured; contact your administrator")
    # Trust the connected peer, not arbitrary forwarded headers. Configure a
    # trusted proxy / edge rate limiter separately for production.
    peer = request.client.host if request.client else "unknown"
    if not accounts.throttle("recovery-peer:" + peer, 30, 3600):
        raise HTTPException(429, "Too many recovery requests; try again later")
    result = {"message": "If an active account exists, a recovery link will be emailed."}
    if not accounts.throttle("recovery-email:" + body.email, 1, 120):
        return result
    user = get_user_by_email(body.email)
    if not user:
        return result
    link_url("validate")
    token = accounts.create_link(user["org_id"], body.email, "recovery", user["role"])
    try:
        response = httpx.post("https://api.brevo.com/v3/smtp/email", headers={"api-key": BREVO_API_KEY}, json={
            "sender": {"email": EMAIL_FROM}, "to": [{"email": body.email}],
            "subject": "Reset your Terra-Audit password",
            "textContent": f"Set a new password: {link_url(token)}\n\nThis link expires in one hour and can be used once. If you did not request it, ignore this email."}, timeout=15)
        if response.status_code >= 400:
            # Generic result avoids exposing whether the address exists.
            import logging
            logging.getLogger(__name__).error("Recovery delivery failed (HTTP %s)", response.status_code)
    except httpx.HTTPError:
        import logging
        logging.getLogger(__name__).error("Recovery delivery unavailable")
    return result


@router.post("/auth/recovery/consume")
def consume(body: Consume, request: Request):
    peer = request.client.host if request.client else "unknown"
    if not accounts.throttle("consume-peer:" + peer, 30, 3600):
        raise HTTPException(429, "Too many attempts; try again later")
    accounts.consume_link(body.token, body.password)
    return {"message": "Password saved. Sign in with your email and new password."}
