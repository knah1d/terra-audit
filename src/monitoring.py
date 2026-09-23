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
    for table in ("crop_seasons", "field_observations", "observation_reviews", "monitoring_runs"):
        conn.execute(text(f"""CREATE TABLE IF NOT EXISTS {table} (
            id TEXT PRIMARY KEY, org_id TEXT NOT NULL, field_id TEXT NOT NULL,
            season_id TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL
        )"""))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table}_scope ON {table}(org_id, field_id, season_id)"))


TABLES = {"crop_seasons", "field_observations", "observation_reviews", "monitoring_runs"}


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


def season(org_id, field_id, season_id):
    return next((r for r in records("crop_seasons", org_id, field_id, season_id) if r["id"] == season_id), None)


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def evidence_package(org_id, field_id, season_id):
    crop_season = season(org_id, field_id, season_id)
    if crop_season is None:
        raise ValueError("Season not found")
    package = {"schema_version": "multicrop-evidence-v1", "season": crop_season,
               "observations": records("field_observations", org_id, field_id, season_id),
               "reviews": records("observation_reviews", org_id, field_id, season_id),
               "runs": records("monitoring_runs", org_id, field_id, season_id),
               "status": "monitoring_evidence_only_not_carbon_verification"}
    return {**package, "sha256": digest(package)}
