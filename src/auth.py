"""
Authentication layer — Phase 1 of the multi-tenant plan
(.claude/plans/misty-growing-yao.md).

Deliberately custom (bcrypt-hashed `users` table + a plain st.form +
st.session_state), not `streamlit-authenticator` or an external IdP:

- `streamlit-authenticator`'s flat YAML/dict credential model fights the
  relational org/role schema this app already needs (see
  src/database.py's `users` table, org_id + role columns) — it would mean
  maintaining a second, parallel identity store.
- An external IdP (Auth0/Clerk/Cognito via OIDC) is the correct long-term
  answer once an enterprise customer contractually requires SSO, but real
  integration cost for zero real users today, and duplicate identity
  storage until that day comes. Revisit then, not now.

`st.session_state["auth_user"]` holds the authenticated identity for the
lifetime of the browser session (Streamlit's own per-session state) — it
does NOT survive a hard refresh/new tab, unlike a cookie-based session.
That's an accepted trade-off for Phase 1's simplicity, not an oversight.
"""

import bcrypt
import streamlit as st

from src.database import get_db_connection

SESSION_KEY = "auth_user"


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
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (email,),
        ).fetchone()
    return dict(row) if row else None


def _touch_last_login(user_id: str):
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()


def current_user() -> dict | None:
    """Returns the authenticated user dict from this browser session, or
    None if no one is logged in yet. Never touches the DB."""
    return st.session_state.get(SESSION_KEY)


def login_form() -> dict | None:
    """Renders a login form until `st.session_state['auth_user']` is set,
    then returns that user dict on every subsequent rerun without
    re-rendering the form. Call this at the very top of app.py, before
    init_modules()/any DB read, so no GEE/DB work happens pre-auth.
    """
    existing = current_user()
    if existing is not None:
        return existing

    st.title("🌍 Terra Audit — Sign In")
    st.caption("Sign in with your organization's credentials to continue.")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

    if submitted:
        user = get_user_by_email(email.strip().lower())
        if user and verify_password(password, user["password_hash"]):
            st.session_state[SESSION_KEY] = {
                "user_id": user["user_id"],
                "org_id": user["org_id"],
                "email": user["email"],
                "role": user["role"],
            }
            _touch_last_login(user["user_id"])
            st.rerun()
        else:
            st.error("Invalid email or password.")
    return None


def logout():
    """Clears the authenticated session. Field-derived session_state keys
    (carbon_*, signal_*, export_*, alm_*, ...) are cleared separately by
    app.py's SESSION_KEYS_TO_CLEAR_ON_FIELD_CHANGE sweep (Phase 3) so a
    different user logging into the same browser tab never sees stale
    per-field results left over from the previous session."""
    st.session_state.pop(SESSION_KEY, None)


# NOTE: role enforcement (require_role) is deliberately deferred to Phase 4
# of the multi-tenant plan, once org self-serve invites exist and there's
# more than one role in practice to enforce against. Keeping Phase 1
# scoped to "does a login work at all" avoids shipping an unused/untested
# guard function.
