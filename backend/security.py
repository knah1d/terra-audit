"""
JWT auth for the FastAPI backend — .claude/plans/misty-growing-yao.md
Part A2. Wraps src.auth's existing bcrypt/DB primitives; does not fork or
duplicate them. The 4-field JWT payload (user_id/org_id/email/role) is
exactly what st.session_state["auth_user"] already carries for the
Streamlit app — same identity model, stateless transport.
"""

import datetime

import jwt

from src.auth import get_user_by_email, verify_password
from backend.config import JWT_ALGORITHM


def authenticate(email: str, password: str) -> dict | None:
    """Returns the user dict on success, None on bad credentials — mirrors
    the check inside src.auth.login_form() exactly, minus the Streamlit
    session_state write."""
    user = get_user_by_email(email.strip().lower())
    if user and verify_password(password, user["password_hash"]):
        return user
    return None


def create_access_token(user: dict, secret: str, expires_minutes: int) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "user_id": user["user_id"],
        "org_id": user["org_id"],
        "email": user["email"],
        "role": user["role"],
        "iat": now,
        "exp": now + datetime.timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict:
    """Raises jwt.PyJWTError (ExpiredSignatureError, InvalidTokenError, ...)
    on any failure — callers (backend/deps.py) turn that into a 401."""
    return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
