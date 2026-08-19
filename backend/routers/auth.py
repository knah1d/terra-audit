from fastapi import APIRouter, Depends, HTTPException, status

from backend.config import JWT_EXPIRE_MINUTES, JWT_SECRET
from backend.deps import get_current_user
from backend.schemas.auth import LoginRequest, TokenResponse, UserOut
from backend.security import authenticate, create_access_token
from src.auth import touch_last_login

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    # src.auth.touch_last_login is now public (it was private, so this
    # router kept its own inline copy of the same UPDATE). Both clients'
    # login paths share the one implementation.
    touch_last_login(user["user_id"])
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
