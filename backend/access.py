"""Shared project-authorization check — used by both backend/routers/
reviews.py (Phase 3) and backend/routers/monitoring_ops.py (Phase 4) so
"does this user have access to this project" is answered identically
everywhere rather than two slightly-different copies drifting apart.
"""
from fastapi import HTTPException, status

from src.projects import get_project_member


def project_role(org_id: str, project_id: str, user_id: str) -> str | None:
    member = get_project_member(org_id, project_id, user_id)
    return member["project_role"] if member else None


def require_project_access(org_id: str, project_id: str, user: dict) -> str | None:
    """Returns the caller's project role (None for an org admin acting
    without project membership) — raises 403 if neither applies. This is
    checked on EVERY action, not cached from an earlier request — a user
    removed from a project immediately loses access to it here."""
    if user["role"] == "admin":
        return project_role(org_id, project_id, user["user_id"])
    role = project_role(org_id, project_id, user["user_id"])
    if role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not a member of this project")
    return role


def require_project_lead(org_id: str, project_id: str, user: dict) -> None:
    if user["role"] == "admin":
        return
    if project_role(org_id, project_id, user["user_id"]) != "lead":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a project lead or org admin can do this")
