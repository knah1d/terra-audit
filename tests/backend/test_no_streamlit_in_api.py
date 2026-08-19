"""
Boundary test: the FastAPI app must not pull in Streamlit.

`src/auth.py` used to have `import streamlit as st` at module scope for
four session/form helpers, and three backend modules import from it
(security.py, deps.py, routers/registration.py). So `uvicorn
backend.main:app` loaded the entire Streamlit runtime — ~440 extra
modules — into a process that never renders a widget, and the API could
not be deployed without installing Streamlit, folium and plotly.

This is exactly the kind of coupling that reappears silently the next
time someone reaches into src/auth.py for a convenience helper, so it is
asserted rather than just documented.

Run in a subprocess because the test session itself may legitimately
have imported Streamlit for other reasons (another test module, a
plugin); only a clean interpreter answers the real question.
"""

import subprocess
import sys
import textwrap


def _probe(code: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, f"probe failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip().splitlines()[-1]


def test_importing_the_api_does_not_import_streamlit():
    assert _probe("""
        import sys
        import backend.main  # noqa: F401
        print("streamlit" in sys.modules)
    """) == "False"


def test_importing_auth_primitives_does_not_import_streamlit():
    """src/auth.py is shared by both clients, so it is the file that must
    stay clean — the split is only load-bearing if this holds."""
    assert _probe("""
        import sys
        import src.auth  # noqa: F401
        print("streamlit" in sys.modules)
    """) == "False"


def test_the_streamlit_helpers_are_still_importable():
    """The split must not have broken app.py's side of it."""
    assert _probe("""
        from src.auth_streamlit import SESSION_KEY, current_user, login_form, logout  # noqa: F401
        print(SESSION_KEY)
    """) == "auth_user"
