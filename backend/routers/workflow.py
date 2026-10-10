"""Guided-workflow reads: per-field step status, per-project field statuses,
and the dashboard's activity/warnings. Read-only; derived from saved records
(src.projects.workflow)."""
from fastapi import APIRouter, Depends, HTTPException, status

from backend.access import require_project_access
from backend.deps import get_current_user, get_owned_field
from src.persistence.database import read_connection_scope
from src.projects import repository as projects_db
from src.projects.workflow import Prefetch, current_projects, field_workflow_status, recent_activity

router = APIRouter(tags=["workflow"])


@router.get("/fields/{field_id}/workflow-status")
def get_field_workflow_status(field_id: str, user=Depends(get_current_user), field=Depends(get_owned_field())):
    # Many small reads: one shared read-only connection instead of a pooled
    # checkout (plus liveness ping) per query — each is a Neon round trip.
    with read_connection_scope():
        return field_workflow_status(user["org_id"], field, current_projects(user["org_id"]).get(field_id))


@router.get("/projects/{project_id}/workflow-status")
def get_project_workflow_status(project_id: str, user=Depends(get_current_user)):
    require_project_access(user["org_id"], project_id, user)
    with read_connection_scope():
        return _project_workflow(user, project_id)


def _project_workflow(user: dict, project_id: str) -> list[dict]:
    if projects_db.get_project(user["org_id"], project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    project_by_field = current_projects(user["org_id"])
    field_ids = [m["field_id"] for m in projects_db.list_project_fields(user["org_id"], project_id)
                 if m["effective_end_date"] is None]
    fields = _light_fields(user["org_id"], field_ids)
    pre = Prefetch(user["org_id"], list(fields))
    rows = []
    for field_id in field_ids:
        field = fields.get(field_id)
        if field is None:
            continue
        rows.append({"name": field["name"], "field_type": field["field_type"], "district": field["district"],
                     **field_workflow_status(user["org_id"], field, project_by_field.get(field_id), pre)})
    return rows


@router.get("/dashboard/summary")
def dashboard_summary(user=Depends(get_current_user)):
    """"Continue where you left off" (latest saved work per field) and the
    next step / readiness warning for each of those fields."""
    with read_connection_scope():
        return _dashboard_summary(user["org_id"])


def _light_fields(org_id: str, field_ids: list[str]) -> dict[str, dict]:
    """The few field columns the workflow needs, for many fields in one query
    (get_field also loads the boundary geometry)."""
    if not field_ids:
        return {}
    from sqlalchemy import bindparam, text
    from src.persistence.database import get_db_connection
    with get_db_connection() as conn:
        rows = conn.execute(text(
            "SELECT field_id, name, district, field_type, area_ha FROM fields "
            "WHERE org_id = :org_id AND field_id IN :ids").bindparams(bindparam("ids", expanding=True)),
            {"org_id": org_id, "ids": list(field_ids)}).mappings().fetchall()
    return {r["field_id"]: dict(r) for r in rows}


def _dashboard_summary(org_id: str) -> dict:
    project_by_field = current_projects(org_id)
    events = recent_activity(org_id)
    fields = _light_fields(org_id, [e["field_id"] for e in events])
    pre = Prefetch(org_id, list(fields))
    items = []
    for event in events:
        field = fields.get(event["field_id"])
        if field is None:
            continue
        workflow = field_workflow_status(org_id, field, project_by_field.get(field["field_id"]), pre)
        items.append({"field_id": field["field_id"], "name": field["name"], "last_activity": event,
                      "project": workflow["project"], "next_step": workflow["next_step"],
                      "needs_attention": [{"step": k, **v} for k, v in workflow["steps"].items()
                                          if v["status"] == "needs_attention"]})
    return {"recent": items}
