"""Append-only crop seasons, field evidence and observation snapshots.

These records supplement both accounting pathways; a crop declaration or
satellite snapshot does not establish methodology eligibility.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from src.database import get_db_connection


def initialize_tables(conn):
    for table in ("crop_seasons", "field_observations", "observation_reviews", "monitoring_runs",
                  "practice_events"):
        conn.execute(text(f"""CREATE TABLE IF NOT EXISTS {table} (
            id TEXT PRIMARY KEY, org_id TEXT NOT NULL, field_id TEXT NOT NULL,
            season_id TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL
        )"""))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table}_scope ON {table}(org_id, field_id, season_id)"))


TABLES = {"crop_seasons", "field_observations", "observation_reviews", "monitoring_runs", "practice_events"}


def append_record(table, org_id, field_id, season_id, payload):
    if table not in TABLES:
        raise ValueError("Unknown monitoring record type")
    record_id = str(uuid.uuid4())
    row = dict(id=record_id, org_id=org_id, field_id=field_id,
               season_id=season_id or record_id,
               created_at=datetime.now(timezone.utc).isoformat(),
               payload=json.dumps(payload, allow_nan=False, sort_keys=True))
    with get_db_connection() as conn:
        # Prevent orphan records if a field was deleted during an analysis.
        exists = conn.execute(text("SELECT 1 FROM fields WHERE org_id=:org_id AND field_id=:field_id"), row).first()
        if not exists:
            raise ValueError("Field no longer exists")
        conn.execute(text(f"INSERT INTO {table} (id,org_id,field_id,season_id,created_at,payload) "
                          "VALUES (:id,:org_id,:field_id,:season_id,:created_at,:payload)"), row)
        conn.commit()
    return {**row, "payload": payload}


def records(table, org_id, field_id=None, season_id=None):
    if table not in TABLES:
        raise ValueError("Unknown monitoring record type")
    query = f"SELECT * FROM {table} WHERE org_id=:org_id"
    params = {"org_id": org_id}
    for key, value in (("field_id", field_id), ("season_id", season_id)):
        if value is not None:
            query += f" AND {key}=:{key}"
            params[key] = value
    with get_db_connection() as conn:
        rows = conn.execute(text(query + " ORDER BY created_at, id"), params).mappings().all()
    return [{**row, "payload": json.loads(row["payload"])} for row in rows]


def append_record_once_per_job(table, org_id, field_id, season_id, job_id, payload):
    """Idempotent wrapper around append_record() for a worker job whose
    execution might be retried after a crash (Phase 4's durable queue can
    reclaim an abandoned 'running' job and re-run it). append_record()
    itself is a plain INSERT (correct for genuinely distinct events, e.g.
    two different reviews) — but ONE job must produce AT MOST ONE
    monitoring run, even if its process died after the DB write but
    before the job row was marked done. Payload is tagged with job_id;
    a prior successful append for the same job_id is returned as-is
    instead of creating a duplicate."""
    payload = {**payload, "job_id": job_id}
    for existing in records(table, org_id, field_id, season_id):
        if existing["payload"].get("job_id") == job_id:
            return existing
    return append_record(table, org_id, field_id, season_id, payload)


def season(org_id, field_id, season_id):
    """Returns the CURRENT version of a season: its original creation row,
    or its latest correction if any were recorded (see season_versions()).
    Observations/reviews/runs keep pointing at the stable season_id
    regardless of how many correction rows accumulate under it."""
    versions = season_versions(org_id, field_id, season_id)
    return versions[-1] if versions else None


def season_versions(org_id, field_id, season_id):
    """All versions of one season (original first, corrections after, in
    creation order) — records() already filters to this season_id and
    orders by created_at, so every row returned already belongs to this
    season; the original creation row is simply the one whose own id
    equals season_id."""
    return [r for r in records("crop_seasons", org_id, field_id, season_id)]


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def evidence_package(org_id, field_id, season_id):
    crop_season = season(org_id, field_id, season_id)
    if crop_season is None:
        raise ValueError("Season not found")
    package = {"schema_version": "multicrop-evidence-v1", "season": crop_season,
               "season_versions": season_versions(org_id, field_id, season_id),
               "observations": records("field_observations", org_id, field_id, season_id),
               "reviews": records("observation_reviews", org_id, field_id, season_id),
               "practice_events": records("practice_events", org_id, field_id, season_id),
               "runs": records("monitoring_runs", org_id, field_id, season_id),
               "status": "monitoring_evidence_only_not_carbon_verification"}
    return {**package, "sha256": digest(package)}
