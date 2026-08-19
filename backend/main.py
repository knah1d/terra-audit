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

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

# Import triggers src.field_types.rice_awd/alm_vm0042's registration
# side-effects (see src/field_types/__init__.py) — without this,
# registry.FIELD_TYPES stays empty and build_methodology()/build_detector()
# raise KeyError for every request.
import src.field_types  # noqa: F401
from src.database import initialize_database
from src.issuance import NonIssuableResultError

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


@app.exception_handler(PydanticValidationError)
async def _pydantic_validation_handler(request: Request, exc: PydanticValidationError):
    """The carbon-credits endpoints take an untyped `body: dict` and build
    CarbonCalcRequestRice/Alm inside the handler, because which shape is
    correct depends on the field's *stored* field_type — something FastAPI
    can't see from the signature. A pydantic.ValidationError raised in a
    handler body is not FastAPI's RequestValidationError and has no
    default handler, so a malformed body used to surface as a 500. This
    turns it into the 422 it always should have been, using Pydantic's own
    error list so the response shape matches FastAPI's native one.
    """
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})


@app.exception_handler(NonIssuableResultError)
async def _non_issuable_handler(request: Request, exc: NonIssuableResultError):
    """Backstop for the issuance gate (src/issuance.py). Routers check
    result_is_issuable() first to return the methodology's own reason, so
    reaching here means a caller tried to persist a blocked result without
    checking — a 422, never a 500."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok"}
