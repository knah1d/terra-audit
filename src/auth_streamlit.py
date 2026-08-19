"""
Streamlit-only session/login helpers, split out of src/auth.py.

These four things (SESSION_KEY + current_user/login_form/logout) were the
only users of `st.*` in the auth layer, but because they lived alongside
the pure bcrypt/SQL primitives, `import streamlit` sat at src/auth.py's
module scope. Every importer inherited it — including
backend/security.py, backend/deps.py and backend/routers/registration.py,
so starting the FastAPI server loaded the whole Streamlit runtime into a
process that never renders a widget.

Nothing under backend/ may import this module.
`st.session_state["auth_user"]` holds the authenticated identity for the
lifetime of the browser session (Streamlit's own per-session state) — it
does NOT survive a hard refresh/new tab, unlike a cookie-based session.
That's an accepted trade-off for Phase 1's simplicity, not an oversight.
"""

import streamlit as st

from src.auth import get_user_by_email, touch_last_login, verify_password

SESSION_KEY = "auth_user"


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
