"""Bulk monitoring batches, version-aware reuse, data-quality issues, and
the project monitoring dashboard — Phase 4.

Reuses (never forks): src.monitoring's crop_seasons/monitoring_runs
append-only records, src.jobs' durable queue for batches/children,
src.projects' project/field membership, src.multicrop_data's existing
`quality` dict (the SAME provisional engineering thresholds
docs/MULTICROP.md already documents — this module translates that dict
into actionable issues, it does not invent new thresholds).
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from src import monitoring
from src.database import get_db_connection
from src.processing import MULTICROP_VERSION

ISSUE_TYPES = {
    "no_usable_observations", "insufficient_temporal_coverage", "low_valid_pixel_coverage",
    "missing_or_conflicting_crop_evidence", "stale_processing_version", "failed_collection",
}
ISSUE_STATUSES = {"open", "acknowledged", "resolved"}


def initialize_tables(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS data_quality_issues (
            org_id             TEXT NOT NULL,
            issue_id           TEXT NOT NULL,
            field_id           TEXT NOT NULL,
            season_id          TEXT NOT NULL,
            issue_type         TEXT NOT NULL,
            severity           TEXT NOT NULL DEFAULT 'warning',
            description        TEXT NOT NULL,
            status             TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
            occurrence_count   INTEGER NOT NULL DEFAULT 1,
            related_job_id     TEXT,
            related_run_id     TEXT,
            first_detected_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_detected_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acknowledged_by    TEXT,
            acknowledged_at    TIMESTAMP,
            resolved_by        TEXT,
            resolved_at        TIMESTAMP,
            resolution_reason  TEXT,
            PRIMARY KEY (org_id, issue_id)
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_dqi_scope ON data_quality_issues(org_id, field_id, season_id)"
    ))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dqi_status ON data_quality_issues(org_id, status)"))


# --------------------------------------------------------------------------
# Version-aware reuse
# --------------------------------------------------------------------------

def compute_fingerprint(geometry: dict, start: str, end: str, processing_version: str, sources: list[str]) -> str:
    """Cache identity for one collection request — EVERY input that would
    change the result must be included here (spec's explicit requirement):
    geometry, date range, source collections, and the processing/config
    version. Two requests with the same fingerprint are the same request."""
    payload = {
        "geometry": geometry, "start": start, "end": end,
        "processing_version": processing_version, "sources": sorted(sources),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def find_reusable_run(org_id: str, field_id: str, season_id: str, fingerprint: str) -> dict | None:
    """A prior run is reusable only if its fingerprint matches exactly AND
    it actually produced usable evidence (ready_for_exploration) — a
    prior insufficient-evidence run is never silently "reused" as if it
    were a good result."""
    for run in reversed(monitoring.records("monitoring_runs", org_id, field_id, season_id)):
        payload = run["payload"]
        if payload.get("fingerprint") == fingerprint and payload.get("quality", {}).get("status") == "ready_for_exploration":
            return run
    return None


# --------------------------------------------------------------------------
# Data-quality issues — created/updated from a monitoring run's own
# `quality` dict (src.multicrop_data.quality_summary) or a failed job.
# --------------------------------------------------------------------------

def _upsert_issue(org_id: str, field_id: str, season_id: str, issue_type: str, severity: str,
                   description: str, related_job_id: str | None, related_run_id: str | None) -> tuple[dict, bool]:
    """Finds an OPEN issue of the same (field, season, type) and updates
    it in place (bumping occurrence_count/last_detected_at and the latest
    related job/run) instead of creating a duplicate — "repeated
    processing should update or link the same issue rather than flood
    users with duplicates." Returns (issue, created_new)."""
    with get_db_connection() as conn:
        existing = conn.execute(text("""
            SELECT * FROM data_quality_issues
            WHERE org_id = :org_id AND field_id = :field_id AND season_id = :season_id
              AND issue_type = :issue_type AND status = 'open'
        """), {"org_id": org_id, "field_id": field_id, "season_id": season_id, "issue_type": issue_type}
        ).mappings().fetchone()
        if existing is not None:
            conn.execute(text("""
                UPDATE data_quality_issues SET occurrence_count = occurrence_count + 1,
                    last_detected_at = CURRENT_TIMESTAMP, description = :description,
                    related_job_id = COALESCE(:related_job_id, related_job_id),
                    related_run_id = COALESCE(:related_run_id, related_run_id)
                WHERE org_id = :org_id AND issue_id = :issue_id
            """), {"description": description, "related_job_id": related_job_id, "related_run_id": related_run_id,
                   "org_id": org_id, "issue_id": existing["issue_id"]})
            conn.commit()
            issue_id = existing["issue_id"]
            created_new = False
        else:
            issue_id = uuid.uuid4().hex
            conn.execute(text("""
                INSERT INTO data_quality_issues (org_id, issue_id, field_id, season_id, issue_type, severity,
                                                  description, related_job_id, related_run_id)
                VALUES (:org_id, :issue_id, :field_id, :season_id, :issue_type, :severity,
                        :description, :related_job_id, :related_run_id)
            """), {"org_id": org_id, "issue_id": issue_id, "field_id": field_id, "season_id": season_id,
                   "issue_type": issue_type, "severity": severity, "description": description,
                   "related_job_id": related_job_id, "related_run_id": related_run_id})
            conn.commit()
            created_new = True
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM data_quality_issues WHERE org_id = :org_id AND issue_id = :issue_id"
        ), {"org_id": org_id, "issue_id": issue_id}).mappings().fetchone()
    return dict(row), created_new


def evaluate_run_quality(org_id: str, field_id: str, season_id: str, run_id: str, run_payload: dict) -> list[tuple[dict, bool]]:
    """Translates one monitoring run's `quality` dict (provisional
    engineering screens, per docs/MULTICROP.md — NOT a validated accuracy
    claim, and never a statement about management-practice compliance)
    into 0+ data-quality issues. Returns [(issue, created_new), ...] so
    callers can notify only on genuinely new issues."""
    results = []
    quality = run_payload.get("quality", {})
    sensors = quality.get("sensors", {})
    for sensor, stats in sensors.items():
        if stats.get("usable_dates", 0) == 0:
            issue, created = _upsert_issue(
                org_id, field_id, season_id, "no_usable_observations", "blocking",
                f"No usable {sensor} observations in the monitoring period (provisional engineering "
                "screen: >=50% valid pixel coverage per scene).",
                None, run_id,
            )
            results.append((issue, created))
    if any(w.startswith("Fewer than five usable dates") for w in quality.get("warnings", [])):
        issue, created = _upsert_issue(
            org_id, field_id, season_id, "insufficient_temporal_coverage", "warning",
            "Fewer than five usable dates for one or more sensors (provisional engineering threshold, "
            "not a validated agronomic requirement).",
            None, run_id,
        )
        results.append((issue, created))
    if any(w.startswith("An observation gap") for w in quality.get("warnings", [])):
        issue, created = _upsert_issue(
            org_id, field_id, season_id, "insufficient_temporal_coverage", "warning",
            "An observation gap exceeds 30 days (provisional engineering threshold, including season edges).",
            None, run_id,
        )
        results.append((issue, created))

    observations = run_payload.get("observations", [])
    if observations:
        low_valid = [o for o in observations if float(o.get("valid_fraction") or 0) < 0.5]
        if len(low_valid) / len(observations) > 0.5:
            issue, created = _upsert_issue(
                org_id, field_id, season_id, "low_valid_pixel_coverage", "warning",
                f"{len(low_valid)} of {len(observations)} scenes fell below 50% valid-pixel coverage "
                "(cloud masking / mixed pixels — a known limitation for small fields).",
                None, run_id,
            )
            results.append((issue, created))

    if run_payload.get("processing_version") != MULTICROP_VERSION:
        issue, created = _upsert_issue(
            org_id, field_id, season_id, "stale_processing_version", "info",
            f"This run used processing version {run_payload.get('processing_version')!r}; the "
            f"current version is {MULTICROP_VERSION!r}. Re-run to refresh with current processing.",
            None, run_id,
        )
        results.append((issue, created))
    return results


def evaluate_crop_evidence(org_id: str, field_id: str, season_id: str) -> tuple[dict, bool] | None:
    """Missing or conflicting crop_identity evidence — reuses Phase 2's
    existing observation/review records rather than a separate check."""
    observations = monitoring.records("field_observations", org_id, field_id, season_id)
    reviews = monitoring.records("observation_reviews", org_id, field_id, season_id)
    accepted_crops = set()
    for obs in observations:
        if obs["payload"]["kind"] != "crop_identity":
            continue
        obs_reviews = [r for r in reviews if r["payload"]["observation_id"] == obs["id"]]
        latest = obs_reviews[-1] if obs_reviews else None
        if latest and latest["payload"]["decision"] == "accepted":
            accepted_crops.add(obs["payload"]["value"])
    if not accepted_crops:
        return _upsert_issue(org_id, field_id, season_id, "missing_or_conflicting_crop_evidence", "warning",
                              "No reviewer-accepted crop identity evidence exists for this season.", None, None)
    if len(accepted_crops) > 1:
        return _upsert_issue(org_id, field_id, season_id, "missing_or_conflicting_crop_evidence", "warning",
                              f"Conflicting accepted crop identities recorded: {sorted(accepted_crops)}.", None, None)
    return None


def record_failed_collection(org_id: str, field_id: str, season_id: str, job_id: str, error: str) -> tuple[dict, bool]:
    return _upsert_issue(org_id, field_id, season_id, "failed_collection", "warning",
                          f"The most recent collection attempt failed: {error}", job_id, None)


def list_issues(org_id: str, field_id: str | None = None, project_id: str | None = None,
                 status_filter: str | None = None) -> list[dict]:
    from src import projects as projects_db
    query = "SELECT * FROM data_quality_issues WHERE org_id = :org_id"
    params = {"org_id": org_id}
    if field_id is not None:
        query += " AND field_id = :field_id"
        params["field_id"] = field_id
    if status_filter:
        query += " AND status = :status_filter"
        params["status_filter"] = status_filter
    query += " ORDER BY last_detected_at DESC"
    with get_db_connection() as conn:
        rows = [dict(r) for r in conn.execute(text(query), params).mappings().fetchall()]
    if project_id is not None:
        field_ids = {m["field_id"] for m in projects_db.list_project_fields(org_id, project_id) if m["removed_at"] is None}
        rows = [r for r in rows if r["field_id"] in field_ids]
    return rows


def acknowledge_issue(org_id: str, issue_id: str, actor: str, reason: str | None) -> dict:
    with get_db_connection() as conn:
        conn.execute(text("""
            UPDATE data_quality_issues SET status = 'acknowledged', acknowledged_by = :actor,
                acknowledged_at = CURRENT_TIMESTAMP
            WHERE org_id = :org_id AND issue_id = :issue_id AND status = 'open'
        """), {"actor": actor, "org_id": org_id, "issue_id": issue_id})
        conn.commit()
    return get_issue(org_id, issue_id)


def resolve_issue(org_id: str, issue_id: str, actor: str, reason: str) -> dict:
    with get_db_connection() as conn:
        conn.execute(text("""
            UPDATE data_quality_issues SET status = 'resolved', resolved_by = :actor,
                resolved_at = CURRENT_TIMESTAMP, resolution_reason = :reason
            WHERE org_id = :org_id AND issue_id = :issue_id AND status != 'resolved'
        """), {"actor": actor, "reason": reason, "org_id": org_id, "issue_id": issue_id})
        conn.commit()
    return get_issue(org_id, issue_id)


def get_issue(org_id: str, issue_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM data_quality_issues WHERE org_id = :org_id AND issue_id = :issue_id"
        ), {"org_id": org_id, "issue_id": issue_id}).mappings().fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------
# Project monitoring dashboard
# --------------------------------------------------------------------------

def project_monitoring_dashboard(org_id: str, project_id: str) -> dict:
    from src import projects as projects_db
    from src.database import get_field
    from src import jobs as jobs_db

    memberships = [m for m in projects_db.list_project_fields(org_id, project_id) if m["removed_at"] is None]
    rows = []
    for m in memberships:
        field = get_field(org_id, m["field_id"])
        if field is None:
            continue
        seasons = monitoring.records("crop_seasons", org_id, m["field_id"])
        for season in seasons:
            season_id = season["id"]
            runs = monitoring.records("monitoring_runs", org_id, m["field_id"], season_id)
            latest_run = runs[-1] if runs else None
            open_issues = list_issues(org_id, field_id=m["field_id"], status_filter="open")
            season_issues = [i for i in open_issues if i["season_id"] == season_id]
            rows.append({
                "field_id": field["field_id"], "field_name": field["name"], "district": field["district"],
                "season_id": season_id, "season_name": season["payload"]["name"],
                "crops": season["payload"]["crops"],
                "latest_run_status": latest_run["payload"]["quality"]["status"] if latest_run else None,
                "latest_run_source": latest_run["payload"].get("source") if latest_run else None,
                "latest_run_at": latest_run["created_at"] if latest_run else None,
                "open_issue_count": len(season_issues),
                "open_issue_types": sorted({i["issue_type"] for i in season_issues}),
            })

    batches = jobs_db.list_batches(org_id, project_id=project_id)
    coverage_ready = sum(1 for r in rows if r["latest_run_status"] == "ready_for_exploration")
    return {
        "field_season_count": len(rows), "fields": rows,
        "coverage_summary": {"ready": coverage_ready, "total": len(rows),
                              "insufficient_or_missing": len(rows) - coverage_ready},
        "batches": batches,
        "open_issue_count": sum(r["open_issue_count"] for r in rows),
    }
