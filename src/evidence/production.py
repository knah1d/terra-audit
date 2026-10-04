"""Commodity-level, multi-year production records — Phase 3 follow-up
("Implement commodity and historical production records").

VMD0054 v1.1's Step 1 (§5.1, Eqs. 1-3) quantifies production change
COMMODITY BY COMMODITY, comparing actual production in a "historical
reference period" (the longer of 3 years or one complete crop
rotation, immediately preceding the project) against actual production
in the project period being claimed. The codebase's prior
`crop_yield_t_ha` scalar (still on `alm_practice_schedule`, kept
unchanged as a LEGACY input — see src.persistence.database.ALM_PRACTICE_COLUMNS and
src.carbon.alm._production_decline_leakage's docstring) is a
single before/after number under VM0042's baseline/project framework
and cannot represent multi-year, multi-commodity history. This module
adds the real data model instead: dated harvest records per commodity,
tagged either `historical_year` (a year within the reference period) or
`project_period` (the verification period being claimed) —
deliberately just this ONE dimension (not also a baseline/project
scenario axis), because that is exactly what VMD0054 Step 1 itself
compares.

Area/production double-counting: two distinct sharing patterns exist
on a field and must not be conflated:
  - ROTATION — sequential crops on the same land within one period
    (e.g. wheat then maize in the same year). Each `crop_cycle_index`
    is a distinct sequential slot; a cycle's `harvested_area_ha` can
    independently use the full field area since cycles don't overlap
    in time.
  - INTERCROPPING — simultaneous crops sharing the same physical land
    within ONE cycle (e.g. maize + beans intercropped). Each entry in
    that cycle must give an `area_share_pct` of the cycle's harvested
    area, and the module enforces that shares within one
    (field, period_label, crop_cycle_index) group never sum past 100%
    — see _validate_area_share.

`production_status` distinguishes three states a bare quantity number
cannot: 'produced' (a real quantity was harvested), 'zero_production'
(harvested area existed but yielded nothing — a real, informative
zero, e.g. total crop failure), 'missing' (this period's production
for this commodity is simply not recorded yet — never silently treated
as zero), and 'not_applicable' (this commodity was not grown in this
period at all — distinct from "grown but data missing").
"""
import uuid
import json

from sqlalchemy import text

from src.persistence.database import get_db_connection

PERIOD_TYPES = {"historical_year", "project_period"}
PRODUCTION_STATUSES = {"produced", "zero_production", "missing", "not_applicable"}


def initialize_tables(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS leakage_assessments (
            assessment_id TEXT PRIMARY KEY, org_id TEXT NOT NULL,
            field_id TEXT NOT NULL, project_id TEXT NOT NULL, bundle_id TEXT NOT NULL,
            period_start TEXT NOT NULL, period_end TEXT NOT NULL,
            payload_json TEXT NOT NULL, created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS production_records (
            org_id             TEXT NOT NULL,
            record_id          TEXT NOT NULL,
            field_id           TEXT NOT NULL,
            commodity          TEXT NOT NULL,
            period_type        TEXT NOT NULL CHECK (period_type IN ('historical_year', 'project_period')),
            period_label       TEXT NOT NULL,
            crop_cycle_index   INTEGER NOT NULL DEFAULT 0,
            harvest_start_date TEXT,
            harvest_end_date   TEXT,
            harvested_area_ha  REAL,
            area_share_pct     REAL NOT NULL DEFAULT 100.0,
            production_status  TEXT NOT NULL CHECK (production_status IN
                               ('produced', 'zero_production', 'missing', 'not_applicable')),
            production_quantity REAL,
            unit               TEXT NOT NULL DEFAULT '',
            evidence_ref       TEXT NOT NULL DEFAULT '',
            notes              TEXT NOT NULL DEFAULT '',
            created_by         TEXT NOT NULL,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, record_id)
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_production_records_scope "
        "ON production_records(org_id, field_id, period_type)"
    ))


def _uid():
    return uuid.uuid4().hex


def _validate_area_share(org_id: str, field_id: str, period_label: str, crop_cycle_index: int,
                          area_share_pct: float, exclude_record_id: str | None = None) -> None:
    """Enforces that intercropped commodities sharing one cycle never
    claim more than 100% of that cycle's land, in aggregate — the
    mechanism that keeps intercropping from double-counting area.
    Sequential rotation cycles (different crop_cycle_index values) are
    NOT summed against each other here — each is its own slot."""
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT record_id, area_share_pct FROM production_records
            WHERE org_id = :org_id AND field_id = :field_id
              AND period_label = :period_label AND crop_cycle_index = :crop_cycle_index
        """), {"org_id": org_id, "field_id": field_id,
               "period_label": period_label, "crop_cycle_index": crop_cycle_index}).mappings().fetchall()
    existing_total = sum(r["area_share_pct"] for r in rows if r["record_id"] != exclude_record_id)
    if existing_total + area_share_pct > 100.0001:
        raise ValueError(
            f"area_share_pct total for field {field_id!r} period {period_label!r} cycle "
            f"{crop_cycle_index} would be {existing_total + area_share_pct:.2f}% (>100%) — intercropped "
            "commodities sharing one cycle must not claim more than the physical land area."
        )


def create_production_record(
    org_id: str, field_id: str, commodity: str, period_type: str, period_label: str,
    crop_cycle_index: int, harvest_start_date: str | None, harvest_end_date: str | None,
    harvested_area_ha: float | None, area_share_pct: float, production_status: str,
    production_quantity: float | None, unit: str, evidence_ref: str, notes: str, created_by: str,
) -> str:
    if period_type not in PERIOD_TYPES:
        raise ValueError(f"period_type must be one of {sorted(PERIOD_TYPES)}")
    if production_status not in PRODUCTION_STATUSES:
        raise ValueError(f"production_status must be one of {sorted(PRODUCTION_STATUSES)}")
    if production_status == "produced" and production_quantity is None:
        raise ValueError("production_quantity is required when production_status is 'produced'")
    if production_status != "produced" and production_quantity is not None:
        raise ValueError(
            f"production_quantity must not be set when production_status is {production_status!r} — "
            "a zero/missing/not-applicable period must not carry a fabricated number."
        )
    if production_status == "produced" and not unit.strip():
        raise ValueError("unit is required when production_status is 'produced'")
    _validate_area_share(org_id, field_id, period_label, crop_cycle_index, area_share_pct)

    record_id = _uid()
    with get_db_connection() as conn:
        field_exists = conn.execute(text(
            "SELECT 1 FROM fields WHERE org_id = :org_id AND field_id = :field_id"
        ), {"org_id": org_id, "field_id": field_id}).first()
        if not field_exists:
            raise ValueError(f"Field {field_id!r} not found")
        conn.execute(text("""
            INSERT INTO production_records (
                org_id, record_id, field_id, commodity, period_type, period_label,
                crop_cycle_index, harvest_start_date, harvest_end_date, harvested_area_ha, area_share_pct,
                production_status, production_quantity, unit, evidence_ref, notes, created_by
            ) VALUES (
                :org_id, :record_id, :field_id, :commodity, :period_type, :period_label,
                :crop_cycle_index, :harvest_start_date, :harvest_end_date, :harvested_area_ha, :area_share_pct,
                :production_status, :production_quantity, :unit, :evidence_ref, :notes, :created_by
            )
        """), {
            "org_id": org_id, "record_id": record_id, "field_id": field_id,
            "commodity": commodity, "period_type": period_type, "period_label": period_label,
            "crop_cycle_index": crop_cycle_index, "harvest_start_date": harvest_start_date,
            "harvest_end_date": harvest_end_date, "harvested_area_ha": harvested_area_ha,
            "area_share_pct": area_share_pct, "production_status": production_status,
            "production_quantity": production_quantity, "unit": unit, "evidence_ref": evidence_ref,
            "notes": notes, "created_by": created_by,
        })
        conn.commit()
    return record_id


def import_production_records(org_id: str, field_id: str, records: list[dict], created_by: str) -> dict:
    """Bulk import — each dict takes the same fields as
    create_production_record (minus org_id/field_id/created_by, added
    here). Validated and inserted ONE AT A TIME in the given order (so
    area-share validation sees prior rows in the same batch), and stops
    at the first invalid row rather than partially importing silently —
    returns {"created": [record_id...], "error": None} on full success,
    or {"created": [ids created before the failure], "error": "..."} so
    a caller can report exactly how far an import got."""
    created = []
    for i, r in enumerate(records):
        try:
            record_id = create_production_record(
                org_id, field_id, r["commodity"], r["period_type"], r["period_label"],
                r.get("crop_cycle_index", 0), r.get("harvest_start_date"), r.get("harvest_end_date"),
                r.get("harvested_area_ha"), r.get("area_share_pct", 100.0), r["production_status"],
                r.get("production_quantity"), r.get("unit", ""), r.get("evidence_ref", ""),
                r.get("notes", ""), created_by,
            )
        except (ValueError, KeyError) as exc:
            return {"created": created, "error": f"Row {i}: {exc}"}
        created.append(record_id)
    return {"created": created, "error": None}


def list_production_records(org_id: str, field_id: str, period_type: str | None = None) -> list[dict]:
    query = "SELECT * FROM production_records WHERE org_id = :org_id AND field_id = :field_id"
    params = {"org_id": org_id, "field_id": field_id}
    if period_type is not None:
        query += " AND period_type = :period_type"
        params["period_type"] = period_type
    query += " ORDER BY period_label, crop_cycle_index, commodity"
    with get_db_connection() as conn:
        rows = conn.execute(text(query), params).mappings().fetchall()
    return [{**dict(r), "created_at": str(r["created_at"])} for r in rows]


def commodities_present(org_id: str, field_id: str) -> set[str]:
    return {r["commodity"] for r in list_production_records(org_id, field_id)}


def production_summary(org_id: str, field_id: str) -> dict:
    """Groups this field's records as
    {commodity: {"historical_year": [records], "project_period": [records]}}
    — the shape src.carbon.leakage_vmd0054 reads to build VMD0054 Step 1's
    per-commodity historical-vs-project comparison. Every record is
    passed through exactly as stored — no aggregation/averaging happens
    here, so a 'missing' or 'not_applicable' status is never silently
    dropped."""
    summary: dict = {}
    for r in list_production_records(org_id, field_id):
        c = summary.setdefault(r["commodity"], {"historical_year": [], "project_period": []})
        c[r["period_type"]].append(r)
    return summary


def list_leakage_assessments(org_id: str, field_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text(
            "SELECT * FROM leakage_assessments WHERE org_id=:org AND field_id=:field "
            "ORDER BY created_at DESC, assessment_id DESC"
        ), {"org": org_id, "field": field_id}).mappings().all()
    return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]


def save_leakage_assessment(org_id: str, field_id: str, payload: dict, actor: str) -> dict:
    """Append-only parameter revisions. Approval is a separate evidence-scoped decision."""
    from datetime import datetime, timezone
    row = {"assessment_id": _uid(), "org_id": org_id, "field_id": field_id,
           "project_id": payload["project_id"], "bundle_id": payload["bundle_id"],
           "period_start": payload["monitoring_period_start"], "period_end": payload["monitoring_period_end"],
           "payload_json": json.dumps(payload, allow_nan=False), "created_by": actor,
           "created_at": datetime.now(timezone.utc).isoformat()}
    with get_db_connection() as conn:
        conn.execute(text("""INSERT INTO leakage_assessments
            (assessment_id, org_id, field_id, project_id, bundle_id, period_start, period_end,
             payload_json, created_by, created_at)
            VALUES (:assessment_id, :org_id, :field_id, :project_id, :bundle_id, :period_start,
                    :period_end, :payload_json, :created_by, :created_at)"""), row)
        conn.commit()
    return {**row, "payload": payload}


def leakage_snapshot(org_id: str, field_id: str, project_id: str | None,
                     bundle_id: str | None, start: str, end: str) -> dict:
    assessment = next((row for row in list_leakage_assessments(org_id, field_id)
                       if row["project_id"] == project_id and row["bundle_id"] == bundle_id
                       and row["period_start"] == start and row["period_end"] == end), None)
    from src.projects.repository import list_project_fields
    return {"assessment": assessment, "production_records": list_production_records(org_id, field_id),
            "project_fields": list_project_fields(org_id, project_id) if project_id else []}
