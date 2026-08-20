"""
Team management — admin-only roster + invite, wrapping src.auth's existing
create_org_user/list_org_users (previously called only from app.py,
bypassing the API entirely). See app.py's admin-only Team UI (the
if auth_user["role"] == "admin": block) for the Streamlit precedent this
mirrors.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.deps import require_admin
from backend.schemas.team import CreateUserIn, TeamUserOut
from src.auth import VALID_ROLES, create_org_user, list_org_users

router = APIRouter(tags=["team"])


def _to_out(row: dict) -> TeamUserOut:
    return TeamUserOut(
        user_id=row["user_id"],
        email=row["email"],
        role=row["role"],
        is_active=bool(row["is_active"]),
        created_at=str(row["created_at"]) if row["created_at"] is not None else None,
        last_login_at=str(row["last_login_at"]) if row["last_login_at"] is not None else None,
    )


@router.get("/team/users", response_model=list[TeamUserOut])
def get_team_users(user: dict = Depends(require_admin)):
    return [_to_out(row) for row in list_org_users(user["org_id"])]


@router.post("/team/users", response_model=TeamUserOut, status_code=status.HTTP_201_CREATED)
def invite_team_user(body: CreateUserIn, user: dict = Depends(require_admin)):
    if body.role not in VALID_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"role must be one of {sorted(VALID_ROLES)}")
    try:
        create_org_user(user["org_id"], body.email, body.password, body.role)
    except ValueError as exc:
        # create_org_user raises ValueError for both "role invalid" (already
        # checked above, kept as a defensive backstop) and "email taken" —
        # the latter is the one actually reachable here, hence 409.
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    for row in list_org_users(user["org_id"]):
        if row["email"] == body.email.strip().lower():
            return _to_out(row)
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "User created but could not be re-read")
