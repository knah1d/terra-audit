"""
Authentication primitives — pure bcrypt + SQL, no UI framework.

This module is imported by BOTH clients (the Streamlit app and the
FastAPI backend), so it must stay free of Streamlit. The
Streamlit-specific session/form helpers that used to live here
(current_user/login_form/logout and the SESSION_KEY they share) are in
src/auth_streamlit.py — they were the only four things in this file that
touched `st.*`, and their presence meant `import streamlit` sat at module
scope, so `uvicorn backend.main:app` pulled the entire Streamlit runtime
(~2,800 modules) into an API process that never renders a widget.
tests/backend/test_no_streamlit_in_api.py locks that boundary in.

Deliberately a custom bcrypt-hashed `users` table, not
`streamlit-authenticator` or an external IdP:

- `streamlit-authenticator`'s flat YAML/dict credential model fights the
  relational org/role schema this app already needs (see
  src/database.py's `users` table, org_id + role columns) — it would mean
  maintaining a second, parallel identity store.
- An external IdP (Auth0/Clerk/Cognito via OIDC) is the correct long-term
  answer once an enterprise customer contractually requires SSO, but real
  integration cost for zero real users today, and duplicate identity
  storage until that day comes. Revisit then, not now.
"""

import uuid

import bcrypt
from sqlalchemy import text

from src.database import get_db_connection

VALID_ROLES = {"admin", "analyst", "viewer"}


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        # Malformed/legacy hash — never let this raise all the way up
        # through a login attempt.
        return False


def get_user_by_email(email: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(
            text("SELECT * FROM users WHERE email = :email AND is_active = 1"),
            {"email": email},
        ).mappings().fetchone()
    return dict(row) if row else None


def touch_last_login(user_id: str):
    with get_db_connection() as conn:
        conn.execute(
            text("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        conn.commit()


def require_role(user: dict, allowed_roles: set[str]):
    """Guard for mutating UI actions (field registration, every save_*/
    delete_field call site, team invites) — call at the top of the
    handler, before any DB write. Raises PermissionError rather than
    silently no-op'ing, so a caller that forgets the check fails loudly
    in testing rather than quietly letting a viewer write data.

    Kept in src/auth.py, not src/database.py — database.py stays a pure
    data layer with no notion of "who is calling," and role enforcement
    belongs in the app layer that already has `auth_user` in scope.
    """
    if user.get("role") not in allowed_roles:
        raise PermissionError(
            f"Role '{user.get('role')}' is not permitted to perform this action "
            f"(requires one of {sorted(allowed_roles)})."
        )


def create_org_user(org_id: str, email: str, password: str, role: str) -> str:
    """Creates a new user within an existing org — used by the admin-only
    Team UI (app.py) so onboarding teammates doesn't require CLI/operator
    involvement beyond the very first admin per org (scripts/create_user.py).
    Raises ValueError if the email is already taken (any org) or the role
    is invalid."""
    email = email.strip().lower()
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {sorted(VALID_ROLES)}, got {role!r}")
    if get_user_by_email(email) is not None:
        raise ValueError(f"a user with email {email!r} already exists")

    user_id = uuid.uuid4().hex
    with get_db_connection() as conn:
        conn.execute(
            text("INSERT INTO users (user_id, org_id, email, password_hash, role) "
                 "VALUES (:user_id, :org_id, :email, :password_hash, :role)"),
            {"user_id": user_id, "org_id": org_id, "email": email,
             "password_hash": hash_password(password), "role": role},
        )
        conn.commit()
    return user_id


def list_org_users(org_id: str) -> list[dict]:
    """Returns every user in this org (for the admin Team UI's roster),
    ordered by creation time."""
    with get_db_connection() as conn:
        rows = conn.execute(
            text("SELECT user_id, email, role, is_active, created_at, last_login_at "
                 "FROM users WHERE org_id = :org_id ORDER BY created_at ASC"),
            {"org_id": org_id},
        ).mappings().fetchall()
    return [dict(r) for r in rows]
