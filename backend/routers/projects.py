"""Projects: operational grouping of fields for monitoring/reporting —
deliberately separate from carbon-claim allocation (src.issuance/
credit_history). A field can belong to more than one project at once;
this router surfaces that overlap rather than hiding it, and never
infers or changes a field's accounting methodology (field_type) from
project membership.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from backend.deps import get_current_user, require_writer
from backend.access import require_project_access, require_project_lead
from backend.schemas.projects import (
    FieldMembershipAssign, FieldMembershipEnd, FieldMembershipOut,
    ProjectCreate, ProjectMemberCreate, ProjectMemberOut, ProjectOut, ProjectUpdate,
)
from src.auth import list_org_users
from src.database import get_field
from src import projects as projects_db

router = APIRouter(tags=["projects"])


def _owned_project(org_id: str, project_id: str) -> dict:
    project = projects_db.get_project(org_id, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(user=Depends(get_current_user)):
    return [ProjectOut(**p) for p in projects_db.list_projects(user["org_id"])
            if user["role"] == "admin" or projects_db.get_project_member(user["org_id"], p["project_id"], user["user_id"])]


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, user=Depends(require_writer)):
    project_id = projects_db.create_project(
        user["org_id"], body.name, body.description, body.geography,
        body.monitoring_start_date.isoformat() if body.monitoring_start_date else None,
        body.monitoring_end_date.isoformat() if body.monitoring_end_date else None,
        body.status, user["user_id"],
    )
    projects_db.add_project_member(user["org_id"], project_id, user["user_id"], "lead",
                                    actor=user["user_id"], reason="Project creator")
    return ProjectOut(**projects_db.get_project(user["org_id"], project_id))


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, user=Depends(get_current_user)):
    require_project_access(user["org_id"], project_id, user)
    return ProjectOut(**_owned_project(user["org_id"], project_id))


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate, user=Depends(require_writer)):
    require_project_lead(user["org_id"], project_id, user)
    _owned_project(user["org_id"], project_id)
    projects_db.update_project(
        user["org_id"], project_id, body.name, body.description, body.geography,
        body.monitoring_start_date.isoformat() if body.monitoring_start_date else None,
        body.monitoring_end_date.isoformat() if body.monitoring_end_date else None,
        body.status,
    )
    return ProjectOut(**projects_db.get_project(user["org_id"], project_id))


@router.get("/projects/{project_id}/members", response_model=list[ProjectMemberOut])
def get_project_members(project_id: str, user=Depends(get_current_user)):
    require_project_access(user["org_id"], project_id, user)
    _owned_project(user["org_id"], project_id)
    return [ProjectMemberOut(**m) for m in projects_db.list_project_members(user["org_id"], project_id)]


@router.post("/projects/{project_id}/members", response_model=list[ProjectMemberOut], status_code=status.HTTP_201_CREATED)
def add_project_member(project_id: str, body: ProjectMemberCreate, user=Depends(require_writer)):
    require_project_lead(user["org_id"], project_id, user)
    _owned_project(user["org_id"], project_id)
    if not any(u["user_id"] == body.user_id for u in list_org_users(user["org_id"])):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "User does not belong to this organization")
    projects_db.add_project_member(user["org_id"], project_id, body.user_id, body.project_role,
                                    actor=user["user_id"], reason=body.reason)
    return [ProjectMemberOut(**m) for m in projects_db.list_project_members(user["org_id"], project_id)]


@router.delete("/projects/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(project_id: str, user_id: str, reason: str | None = None, user=Depends(require_writer)):
    require_project_lead(user["org_id"], project_id, user)
    _owned_project(user["org_id"], project_id)
    projects_db.remove_project_member(user["org_id"], project_id, user_id, actor=user["user_id"], reason=reason)
    return None


@router.get("/projects/{project_id}/membership-events")
def get_membership_events(project_id: str, user=Depends(get_current_user)):
    require_project_access(user["org_id"], project_id, user)
    _owned_project(user["org_id"], project_id)
    return projects_db.membership_events(user["org_id"], project_id)


@router.get("/projects/{project_id}/fields", response_model=list[FieldMembershipOut])
def get_project_fields(project_id: str, user=Depends(get_current_user)):
    require_project_access(user["org_id"], project_id, user)
    _owned_project(user["org_id"], project_id)
    return [FieldMembershipOut(**m) for m in projects_db.list_project_fields(user["org_id"], project_id)]


@router.post("/projects/{project_id}/fields", response_model=FieldMembershipOut, status_code=status.HTTP_201_CREATED)
def assign_field(project_id: str, body: FieldMembershipAssign, user=Depends(require_writer)):
    """Explicit assignment workflow: attaches an EXISTING field (its full
    history untouched) to this project as of effective_start_date. Never
    triggered automatically by field registration or a crop declaration."""
    require_project_lead(user["org_id"], project_id, user)
    _owned_project(user["org_id"], project_id)
    if get_field(user["org_id"], body.field_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    membership_id = projects_db.assign_field_to_project(
        user["org_id"], project_id, body.field_id, body.effective_start_date.isoformat(), user["user_id"],
    )
    matches = [m for m in projects_db.list_project_fields(user["org_id"], project_id) if m["membership_id"] == membership_id]
    return FieldMembershipOut(**matches[0])


@router.post("/projects/{project_id}/fields/{membership_id}/end", response_model=FieldMembershipOut)
def end_field_membership(project_id: str, membership_id: str, body: FieldMembershipEnd, user=Depends(require_writer)):
    require_project_lead(user["org_id"], project_id, user)
    _owned_project(user["org_id"], project_id)
    if not any(m["membership_id"] == membership_id for m in projects_db.list_project_fields(user["org_id"], project_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found in this project")
    ok = projects_db.end_project_field_membership(
        user["org_id"], membership_id, body.effective_end_date.isoformat(), body.reason,
    )
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active field membership not found")
    matches = [m for m in projects_db.list_project_fields(user["org_id"], project_id) if m["membership_id"] == membership_id]
    return FieldMembershipOut(**matches[0])


@router.get("/projects/{project_id}/dashboard")
def get_project_dashboard(project_id: str, user=Depends(get_current_user)):
    require_project_access(user["org_id"], project_id, user)
    _owned_project(user["org_id"], project_id)
    return projects_db.project_dashboard(user["org_id"], project_id)


@router.get("/fields/{field_id}/projects", response_model=list[FieldMembershipOut])
def get_projects_for_field(field_id: str, user=Depends(get_current_user)):
    """Every project this field belongs to (open and ended) — surfaces
    overlap explicitly rather than assuming one field means one project."""
    if get_field(user["org_id"], field_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    return [FieldMembershipOut(**m) for m in projects_db.list_projects_for_field(user["org_id"], field_id)
            if user["role"] == "admin" or projects_db.get_project_member(user["org_id"], m["project_id"], user["user_id"])]
