"""
Import-hygiene boundary tests: importing this codebase's modules must not
drag in a UI framework, and must not touch the filesystem or database.

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


# --- import-time side effects -------------------------------------------

def test_importing_src_database_does_not_build_an_engine_or_run_ddl():
    """src/database.py used to call initialize_database() at module scope,
    so merely importing it created the data/ directory, opened a
    connection, and ran the full DDL + ALTER TABLE migration replay — and
    latched DATABASE_URL at first import, which is why the test fixtures
    had to reset two private globals by hand to redirect at a temp file.
    Any test that forgot the fixture wrote DDL to the developer's real
    project_store.db."""
    assert _probe("""
        import src.database as db
        print(db._ENGINE is None and db._DB_INITIALIZED is False)
    """) == "True"


def test_importing_the_api_does_not_run_ddl_before_lifespan():
    """The schema is created in backend/main.py's lifespan, not at import.
    Importing the module to inspect routes (or for `openapi.json`
    generation) must not require a writable database."""
    assert _probe("""
        import backend.main  # noqa: F401
        import src.database as db
        print(db._DB_INITIALIZED is False)
    """) == "True"
