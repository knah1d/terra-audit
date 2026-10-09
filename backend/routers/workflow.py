"""Guided-workflow reads: per-field step status, per-project field statuses,
and the dashboard's activity/warnings. Read-only; derived from saved records
(src.projects.workflow)."""
from fastapi import APIRouter, Depends, HTTPException, status

from backend.access import require_project_access
from backend.deps import get_current_user, get_owned_field
from src.persistence.database import get_field
from src.projects import repository as projects_db
from src.projects.workflow import current_projects, field_workflow_status, recent_activity

router = APIRouter(tags=["workflow"])


@router.get("/fields/{field_id}/workflow-status")
def get_field_workflow_status(field_id: str, user=Depends(get_current_user), field=Depends(get_owned_field())):
    return field_workflow_status(user["org_id"], field, current_projects(user["org_id"]).get(field_id))


@router.get("/projects/{project_id}/workflow-status")
def get_project_workflow_status(project_id: str, user=Depends(get_current_user)):
    require_project_access(user["org_id"], project_id, user)
    if projects_db.get_project(user["org_id"], project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    project_by_field = current_projects(user["org_id"])
    rows = []
    for membership in projects_db.list_project_fields(user["org_id"], project_id):
        if membership["effective_end_date"] is not None:
            continue
        field = get_field(user["org_id"], membership["field_id"])
        if field is None:
            continue
        rows.append({"name": field["name"], "field_type": field["field_type"], "district": field["district"],
                     **field_workflow_status(user["org_id"], field, project_by_field.get(field["field_id"]))})
    return rows


@router.get("/dashboard/summary")
def dashboard_summary(user=Depends(get_current_user)):
    """"Continue where you left off" (latest saved work per field) and the
    next step / readiness warning for each of those fields."""
    org_id = user["org_id"]
    project_by_field = current_projects(org_id)
    items = []
    for event in recent_activity(org_id):
        field = get_field(org_id, event["field_id"])
        if field is None:
            continue
        workflow = field_workflow_status(org_id, field, project_by_field.get(field["field_id"]))
        items.append({"field_id": field["field_id"], "name": field["name"], "last_activity": event,
                      "project": workflow["project"], "next_step": workflow["next_step"],
                      "needs_attention": [{"step": k, **v} for k, v in workflow["steps"].items()
                                          if v["status"] == "needs_attention"]})
    return {"recent": items}
