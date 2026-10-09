"""Field workflow status, current project and recent activity — derived only
from persisted records (seasons, observations/reviews, signal runs,
calculations, submissions, ALM data). Visiting a page never changes a status,
and readiness is never recomputed here: calculation status reuses the
readiness frozen into the latest calculation.

Statuses: not_started, in_progress, needs_attention, ready, completed,
not_applicable.
"""
from sqlalchemy import text

from src.evidence import monitoring
from src.persistence.database import get_db_connection

RICE_ORDER = ["crop-seasons", "enrollment", "signal-analytics", "calculations", "review"]
ALM_ORDER = ["crop-seasons", "enrollment", "practice-data", "soil-evidence", "production-records",
             "calculations", "review"]
OPEN = ("not_started", "in_progress", "needs_attention")


def _step(status: str, detail: str) -> dict:
    return {"status": status, "detail": detail}


def current_projects(org_id: str) -> dict:
    """field_id -> its current (open-ended) project membership. One project
    per field at a time is enforced on assignment; for older overlapping rows
    the most recent start wins here and the admin conflict report lists them."""
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT pf.field_id, pf.project_id, pf.membership_id, pf.effective_start_date, p.name
            FROM project_fields pf
            LEFT JOIN projects p ON p.org_id = pf.org_id AND p.project_id = pf.project_id
            WHERE pf.org_id = :org_id AND pf.effective_end_date IS NULL
            ORDER BY pf.effective_start_date
        """), {"org_id": org_id}).mappings().fetchall()
    return {r["field_id"]: {"project_id": r["project_id"], "name": r["name"] or r["project_id"],
                            "membership_id": r["membership_id"],
                            "effective_start_date": r["effective_start_date"]} for r in rows}


def _crop_seasons(org_id: str, field_id: str, seasons: list) -> dict:
    if not seasons:
        return _step("not_started", "No crop season yet")
    latest_review = {}
    for review in monitoring.records("observation_reviews", org_id, field_id):
        latest_review[review["payload"]["observation_id"]] = review["payload"]["decision"]
    observations = monitoring.records("field_observations", org_id, field_id)
    rejected = sum(1 for o in observations if latest_review.get(o["id"]) == "rejected")
    pending = sum(1 for o in observations if o["id"] not in latest_review)
    if rejected:
        return _step("needs_attention", f"{rejected} observation(s) rejected")
    if pending:
        return _step("in_progress", f"{pending} observation(s) awaiting review")
    return _step("completed", f"{len(seasons)} season(s)")


def _enrollment(org_id: str, field: dict, seasons: list, project_id: str | None) -> dict:
    if not seasons:
        return _step("not_started", "Add a crop season first")
    from src.methodology.readiness import guided_enrollment
    enrollment = guided_enrollment(org_id, field, project_id)
    unrecognized = [c for c in enrollment["declared_crops"] if not c.get("recognized", True)]
    if enrollment["missing_evidence"]:
        return _step("needs_attention", enrollment["missing_evidence"][0])
    if unrecognized:
        return _step("needs_attention", "A declared crop needs reviewer confirmation")
    return _step("ready", "No evidence gaps flagged")


def _signal(org_id: str, field_id: str) -> dict:
    from src.carbon.signal_evidence import candidates
    runs = candidates(org_id, field_id)
    if not runs:
        return _step("not_started", "No satellite analysis yet")
    return _step("completed", f"Latest: {runs[0]['window_start']} – {runs[0]['window_end']}")


def _practice(org_id: str, field_id: str) -> dict:
    from src.persistence.database import get_alm_practice_schedule, get_soc_measurements
    schedule = get_alm_practice_schedule(org_id, field_id)
    soc = get_soc_measurements(org_id, field_id)
    have = [bool(schedule.get("baseline")), bool(schedule.get("project")), len(soc) >= 4]
    if all(have):
        return _step("completed", "Practices and SOC samples recorded")
    if any(have) or soc:
        return _step("in_progress", "Practice schedules or SOC samples incomplete")
    return _step("not_started", "No practice data yet")


def _soil(org_id: str, field_id: str) -> dict:
    from src.evidence.soil import list_plans, resolved_soc_measurements
    adopted = sum(1 for cell in resolved_soc_measurements(org_id, field_id).values()
                  if isinstance(cell, dict) and cell.get("source") == "reviewed_evidence")
    if adopted >= 4:
        return _step("completed", "All SOC cells use reviewed samples")
    if adopted or list_plans(org_id, field_id):
        return _step("in_progress", f"{adopted} of 4 SOC cells adopted")
    return _step("not_started", "No sampling plan yet")


def _production(org_id: str, field_id: str) -> dict:
    from src.evidence.production import list_leakage_assessments, list_production_records
    records = list_production_records(org_id, field_id)
    if not records:
        return _step("not_started", "No production records yet")
    if not list_leakage_assessments(org_id, field_id):
        return _step("in_progress", "No leakage assessment saved")
    return _step("completed", f"{len(records)} record(s) and a leakage assessment")


def _calculations(org_id: str, field_id: str) -> tuple[dict, dict | None]:
    from src.carbon.calculations import list_calculations
    calcs = list_calculations(org_id, field_id=field_id, latest_only=True)
    if not calcs:
        return _step("not_started", "No calculation yet"), None
    latest = calcs[0]
    period = f"{latest['monitoring_period_start']} – {latest['monitoring_period_end']}"
    if latest["status"] == "ready_for_review":
        return _step("ready", f"Ready for review ({period})"), latest
    return _step("needs_attention", f"Draft — readiness items still blocking ({period})"), latest


def _review(org_id: str, field_id: str, project: dict | None, latest_calc: dict | None) -> dict:
    if project is None:
        return _step("not_applicable", "Requires a project")
    with get_db_connection() as conn:
        row = conn.execute(text("""
            SELECT status FROM review_submissions WHERE org_id = :org_id AND field_id = :field_id
            ORDER BY submitted_at DESC LIMIT 1
        """), {"org_id": org_id, "field_id": field_id}).mappings().fetchone()
    status = row["status"] if row else None
    if status in ("submitted", "in_review"):
        return _step("in_progress", "Under internal review")
    if status in ("changes_requested", "rejected"):
        return _step("needs_attention", "Reviewer requested changes" if status == "changes_requested" else "Rejected")
    if status == "internally_approved":
        return _step("completed", "Internally approved")
    if latest_calc and latest_calc["status"] == "ready_for_review":
        return _step("ready", "Ready to submit for review")
    return _step("not_started", "Needs a ready calculation first")


def field_workflow_status(org_id: str, field: dict, project: dict | None = None) -> dict:
    field_id = field["field_id"]
    seasons = monitoring.current_seasons(org_id, field_id)
    calc_step, latest_calc = _calculations(org_id, field_id)
    steps = {
        "crop-seasons": _crop_seasons(org_id, field_id, seasons),
        "enrollment": _enrollment(org_id, field, seasons, project["project_id"] if project else None),
        "calculations": calc_step,
        "review": _review(org_id, field_id, project, latest_calc),
    }
    if field["field_type"] == "rice_awd":
        steps["signal-analytics"] = _signal(org_id, field_id)
        order = RICE_ORDER
    else:
        steps.update({"practice-data": _practice(org_id, field_id), "soil-evidence": _soil(org_id, field_id),
                      "production-records": _production(org_id, field_id)})
        order = ALM_ORDER
    next_step = next(({"step": s, **steps[s]} for s in order if steps[s]["status"] in OPEN or
                      (s == "review" and steps[s]["status"] == "ready")), None)
    return {"field_id": field_id, "project": project, "order": order, "steps": steps, "next_step": next_step}


def recent_activity(org_id: str, limit: int = 5) -> list[dict]:
    """Latest saved work per field (calculation, satellite analysis or crop
    season) — the basis for "Continue where you left off"."""
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT field_id, 'calculation' AS kind, created_at AS at FROM calculations WHERE org_id = :o
            UNION ALL
            SELECT field_id, 'crop_season' AS kind, created_at AS at FROM crop_seasons WHERE org_id = :o
        """), {"o": org_id}).mappings().fetchall()
        jobs = conn.execute(text("""
            SELECT payload_json, finished_at AS at FROM background_jobs
            WHERE org_id = :o AND job_type = 'signal_run' AND status = 'done'
        """), {"o": org_id}).mappings().fetchall()
    import json
    events = [dict(r) for r in rows]
    events += [{"field_id": json.loads(j["payload_json"] or "{}").get("field_id"), "kind": "signal_run", "at": j["at"]}
               for j in jobs]
    latest = {}
    for e in sorted((e for e in events if e["field_id"] and e["at"]), key=lambda e: str(e["at"]), reverse=True):
        latest.setdefault(e["field_id"], {**e, "at": str(e["at"])})
    return list(latest.values())[:limit]
