"""
FastAPI application entrypoint — .claude/plans/misty-growing-yao.md Part A1.

Run with: uvicorn backend.main:app --reload
Swagger UI at /docs.

Coexists with the Streamlit app (app.py) against the same database
throughout the transition — see the plan's "migration/coexistence
strategy" section. Nothing here forks src/ logic; every router imports
and calls src.* directly.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import triggers src.field_types.rice_awd/alm_vm0042's registration
# side-effects (see src/field_types/__init__.py) — without this,
# registry.FIELD_TYPES stays empty and build_methodology()/build_detector()
# raise KeyError for every request.
import src.field_types  # noqa: F401
from src.database import initialize_database

from backend.routers import ai, alm, auth, carbon, export, fields, portfolio, registration, signal


@asynccontextmanager
async def lifespan(app: FastAPI):
    # initialize_database() already ran at src.database import time and is
    # idempotent (_DB_INITIALIZED guard) — calling it again here is a
    # documented no-op, not redundant defensive code.
    initialize_database()

    from src.data_engine import SpatialDataEngine
    try:
        app.state.spatial_engine = SpatialDataEngine()
    except RuntimeError as exc:
        # Earth Engine auth/config missing — signal-run endpoints will
        # 503 via deps.get_spatial_engine rather than crashing the whole
        # API, since every other endpoint (fields, carbon-credits, ALM,
        # portfolio) works fine without GEE.
        app.state.spatial_engine = None
        app.state.spatial_engine_error = str(exc)
    yield


app = FastAPI(title="Terra Audit API", lifespan=lifespan)

# Permissive for local dev (Next.js on :3000) — tighten allow_origins to
# the real frontend origin(s) before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (auth.router, registration.router, fields.router, alm.router, carbon.router,
               signal.router, ai.router, portfolio.router, export.router):
    app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
