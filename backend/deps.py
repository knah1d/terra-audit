"""
FastAPI dependencies — .claude/plans/misty-growing-yao.md Part A2.
"""

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from backend.config import JWT_SECRET
from backend.security import decode_access_token
from src.auth import require_role as _require_role

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
