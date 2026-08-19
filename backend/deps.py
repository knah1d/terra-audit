"""
FastAPI dependencies — .claude/plans/misty-growing-yao.md Part A2.
"""

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from backend.config import JWT_SECRET
from backend.security import decode_access_token
from src.auth import require_role as _require_role
from src.database import get_field
from src.field_types.registry import field_uses_sar

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Decodes the bearer token into the same 4-field shape src.auth's
    functions expect ({"user_id","org_id","email","role"}) — every router
    downstream calls src.database.*(org_id, ...) with claims["org_id"],
    never a client-supplied org_id."""
    try:
        claims = decode_access_token(token, JWT_SECRET)
    except pyjwt.PyJWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "user_id": claims["user_id"],
        "org_id": claims["org_id"],
        "email": claims["email"],
        "role": claims["role"],
    }


def require_roles(*allowed: str):
    """FastAPI-dependency adapter around src.auth.require_role — reuses
    that function's PermissionError contract verbatim, translating it to
    a 403 rather than reimplementing role-checking logic here."""
    allowed_set = set(allowed)

    def _dependency(user: dict = Depends(get_current_user)) -> dict:
        try:
            _require_role(user, allowed_set)
        except PermissionError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
        return user

    return _dependency


require_writer = require_roles("admin", "analyst")
require_admin = require_roles("admin")


def get_owned_field(expect_type: str | None = None, require_sar: bool = False):
    """Loads the path's {field_id} scoped to the caller's org, 404ing if it
    doesn't exist or belongs to another tenant.

    Replaces a `_require_field` helper that was defined identically in
    three routers and inlined in two more (16 call sites), so the
    load-or-404 preamble now exists once.

    `expect_type` / `require_sar` close two real holes the per-router
    copies left open, because they only ever checked existence and
    ownership — never that the field was the *kind* of field the endpoint
    is for:
      - the ALM practice/livestock/SOC endpoints would happily write ALM
        rows onto a rice field
      - POST /fields/{id}/signal-runs ran the rice SAR detector against
        cropland_alm_vm0042 fields, which have no timeseries at all
        (app.py has always guarded this via field_uses_sar; the API
        dropped the guard)
    Mismatches are 422, not 404: the field genuinely exists and the
    caller may read it, the *request* is what's wrong.
    """
    def _dependency(field_id: str, user: dict = Depends(get_current_user)) -> dict:
        field = get_field(user["org_id"], field_id)
        if field is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")

        field_type = field["field_type"]
        if expect_type is not None and field_type != expect_type:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Field '{field_id}' is of type '{field_type}'; this endpoint "
                f"requires '{expect_type}'.",
            )
        if require_sar:
            try:
                uses_sar = field_uses_sar(field_type)
            except KeyError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
            if not uses_sar:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Field type '{field_type}' is not satellite-driven — it has "
                    "no Sentinel-1 timeseries to analyze. Enter its practice and "
                    "soil data instead.",
                )
        return field

    return _dependency


def get_spatial_engine(request: Request):
    """Returns the process-lifetime SpatialDataEngine singleton created in
    backend/main.py's lifespan — never constructs a new one per request
    (ee.Initialize() is a one-time cost, exactly as app.py's own
    @st.cache_resource-wrapped init_modules() already treats it)."""
    engine = getattr(request.app.state, "spatial_engine", None)
    if engine is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Earth Engine is not initialized on this server",
        )
    return engine
