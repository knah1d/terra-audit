"""Quantification units and grouped-project eligibility areas — Phase 2
(docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md: "Represent
quantification units and grouped-project eligibility areas where
required.").

A quantification unit is a named subdivision of a field's registered
area for accounting purposes — e.g. part of a field excluded from a
methodology's scope (a wetland strip within an otherwise-eligible
field), or a distinct eligibility determination area within a larger
boundary. Field area itself (src.database.fields.area_ha) is unchanged
and remains the geometry-derived source of truth; a quantification unit
never resizes it, it only records how much of it is currently
considered eligible and why.

Grouped-project eligible area is a simple aggregation across a
project's currently-assigned fields' eligible quantification units —
not a full VCS grouped-project instance/monitoring-report workflow
(out of scope for this phase), but enough to answer "how much of this
project's enrolled area is actually eligible right now," which several
methodology conditions (and a reviewer sanity check) need.
"""
import uuid

from sqlalchemy import text

from src.database import get_db_connection

ELIGIBILITY_STATUSES = {"eligible", "excluded", "needs_review"}


def initialize_tables(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS quantification_units (
            org_id             TEXT NOT NULL,
            unit_id            TEXT NOT NULL,
            field_id           TEXT NOT NULL,
            name               TEXT NOT NULL,
            area_ha            REAL NOT NULL,
            eligibility_status TEXT NOT NULL DEFAULT 'needs_review'
                               CHECK (eligibility_status IN ('eligible', 'excluded', 'needs_review')),
            exclusion_reason   TEXT,
            geojson_geometry   TEXT,
            created_by         TEXT NOT NULL,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, unit_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quantification_units_field ON quantification_units(org_id, field_id)"))


def create_unit(org_id: str, field_id: str, name: str, area_ha: float, eligibility_status: str,
                exclusion_reason: str | None, created_by: str, geojson_geometry: dict | None = None) -> str:
    import json
    if eligibility_status not in ELIGIBILITY_STATUSES:
        raise ValueError(f"eligibility_status must be one of {sorted(ELIGIBILITY_STATUSES)}")
    if eligibility_status == "excluded" and not exclusion_reason:
        raise ValueError("exclusion_reason is required when eligibility_status is 'excluded'")
    unit_id = uuid.uuid4().hex
    with get_db_connection() as conn:
        field_area = conn.execute(text(
            "SELECT area_ha FROM fields WHERE org_id = :org_id AND field_id = :field_id"
        ), {"org_id": org_id, "field_id": field_id}).scalar()
        if field_area is None:
            raise ValueError(f"Field {field_id!r} not found")
        existing_total = conn.execute(text(
            "SELECT COALESCE(SUM(area_ha), 0) FROM quantification_units WHERE org_id = :org_id AND field_id = :field_id"
        ), {"org_id": org_id, "field_id": field_id}).scalar()
        if field_area and existing_total + area_ha > field_area + 1e-6:
            raise ValueError(
                f"Quantification units would total {existing_total + area_ha:.4f} ha, exceeding the "
                f"field's registered area of {field_area:.4f} ha."
            )
        conn.execute(text("""
            INSERT INTO quantification_units (org_id, unit_id, field_id, name, area_ha, eligibility_status,
                                                exclusion_reason, geojson_geometry, created_by)
            VALUES (:org_id, :unit_id, :field_id, :name, :area_ha, :eligibility_status, :exclusion_reason,
                    :geojson_geometry, :created_by)
        """), {"org_id": org_id, "unit_id": unit_id, "field_id": field_id, "name": name, "area_ha": area_ha,
               "eligibility_status": eligibility_status, "exclusion_reason": exclusion_reason,
               "geojson_geometry": json.dumps(geojson_geometry) if geojson_geometry else None,
               "created_by": created_by})
        conn.commit()
    return unit_id


def list_units(org_id: str, field_id: str) -> list[dict]:
    import json
    with get_db_connection() as conn:
        rows = conn.execute(text(
            "SELECT * FROM quantification_units WHERE org_id = :org_id AND field_id = :field_id ORDER BY created_at"
        ), {"org_id": org_id, "field_id": field_id}).mappings().fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["geojson_geometry"] = json.loads(d["geojson_geometry"]) if d["geojson_geometry"] else None
        out.append(d)
    return out


def project_eligible_area(org_id: str, project_id: str) -> dict:
    """Aggregates eligible/excluded/needs_review area across every field
    currently (openly) assigned to this project — a lightweight
    grouped-project eligibility summary, not a full VCS grouped-project
    workflow."""
    from src import projects as projects_db
    field_ids = [m["field_id"] for m in projects_db.list_project_fields(org_id, project_id) if m["removed_at"] is None]
    totals = {"eligible": 0.0, "excluded": 0.0, "needs_review": 0.0}
    unallocated_fields = []
    with get_db_connection() as conn:
        for field_id in field_ids:
            units = list_units(org_id, field_id)
            if not units:
                area = conn.execute(text(
                    "SELECT area_ha FROM fields WHERE org_id = :org_id AND field_id = :field_id"
                ), {"org_id": org_id, "field_id": field_id}).scalar()
                unallocated_fields.append(field_id)
                if area:
                    totals["needs_review"] += area
                continue
            for u in units:
                totals[u["eligibility_status"]] += u["area_ha"]
    return {
        "field_count": len(field_ids), "totals_ha": totals,
        "fields_without_quantification_units": unallocated_fields,
        "note": "Fields without any recorded quantification unit are counted in full under "
                "'needs_review' — no field is assumed eligible by default.",
    }
