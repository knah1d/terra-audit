from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from backend.config import JWT_EXPIRE_MINUTES, JWT_SECRET
from backend.deps import get_current_user
from backend.schemas.auth import LoginRequest, TokenResponse, UserOut
from backend.security import authenticate, create_access_token
from src.database import get_db_connection

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    # Inlined rather than promoting src.auth's private _touch_last_login to
    # public — a two-line UPDATE isn't worth even a cosmetic diff to that
    # file, per the plan's "don't touch src/auth.py" default.
    with get_db_connection() as conn:
        conn.execute(
            text("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE user_id = :uid"),
            {"uid": user["user_id"]},
        )
        conn.commit()
    token = create_access_token(user, JWT_SECRET, JWT_EXPIRE_MINUTES)
    return TokenResponse(access_token=token)


@router.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(**user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout():
    """Stateless JWT — logout is a client-side token discard. This
    endpoint exists only so the frontend has one consistent call to make
    rather than special-casing 'no logout request for JWT.'"""
    return None
