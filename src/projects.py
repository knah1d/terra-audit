"""Projects, farms, and field-membership records — Phase 1 of the
multi-crop/organization plan (docs/MULTICROP.md's product roadmap).

Mirrors src/monitoring.py's separation from src/database.py: a distinct
domain module reusing get_db_connection() rather than growing
database.py further. Unlike monitoring.py's generic append-only
id/org_id/field_id/season_id/payload shape, these are ordinary typed
tables (closer to the `fields` table itself) because projects/farms have
a small, stable set of columns and need real UPDATE semantics (renaming
a project, editing farm contact details) rather than an append-only log.

Field <-> project and field <-> farm links are their own membership
tables with effective_start_date/effective_end_date rather than a column
on `fields`, so:
  - a field can belong to more than one project at once (visible overlap,
    never silently deduplicated) or move between farms over time
  - ending a membership never deletes the row — it stamps removed_at,
    so the field's history through a project/farm survives
  - assigning a field is always an explicit action (this module never
    guesses an assignment from a crop declaration or anything else)
"""
import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import text

from src.database import get_db_connection, get_field, is_sqlite

PROJECT_STATUSES = {"planning", "active", "completed", "archived"}
PROJECT_MEMBER_ROLES = {"lead", "contributor", "viewer"}


def initialize_tables(conn):
    """Called once from src.database.initialize_database() — identical DDL
    on SQLite/Postgres since none of these tables predate org_id or need
    an ALTER-TABLE migration history (same reasoning as
    src.database._init_shared_extra_tables)."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS projects (
            org_id                 TEXT NOT NULL,
            project_id             TEXT NOT NULL,
            name                   TEXT NOT NULL,
            description            TEXT NOT NULL DEFAULT '',
            geography              TEXT NOT NULL DEFAULT '',
            monitoring_start_date  TEXT,
            monitoring_end_date    TEXT,
            status                 TEXT NOT NULL DEFAULT 'planning'
                                    CHECK (status IN ('planning', 'active', 'completed', 'archived')),
            created_by             TEXT,
            created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, project_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_projects_org ON projects(org_id)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS project_members (
            org_id       TEXT NOT NULL,
            project_id   TEXT NOT NULL,
            user_id      TEXT NOT NULL,
            project_role TEXT NOT NULL DEFAULT 'contributor'
                         CHECK (project_role IN ('lead', 'contributor', 'viewer')),
            added_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, project_id, user_id)
        )
    """))

    # Append-only audit trail for membership changes — project_members
    # above is upserted/deleted in place for fast "is this user a member"
    # lookups, so it alone can't answer "who added/removed whom and why."
    # (Phase 3 correction: reviewer assignment must never silently grant
    # membership — every grant/change/removal now goes through here with
    # an actor and, for removal, a reason.)
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS project_membership_events (
            org_id       TEXT NOT NULL,
            id           TEXT NOT NULL,
            project_id   TEXT NOT NULL,
            user_id      TEXT NOT NULL,
            action       TEXT NOT NULL CHECK (action IN ('added', 'role_changed', 'removed')),
            project_role TEXT,
            actor        TEXT NOT NULL,
            reason       TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, id)
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_project_membership_events_scope "
        "ON project_membership_events(org_id, project_id, user_id)"
    ))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS farms (
            org_id             TEXT NOT NULL,
            farm_id            TEXT NOT NULL,
            name               TEXT NOT NULL,
            contact_name       TEXT NOT NULL DEFAULT '',
            contact_phone      TEXT NOT NULL DEFAULT '',
            contact_email      TEXT NOT NULL DEFAULT '',
            consent_given      INTEGER NOT NULL DEFAULT 0,
            consent_reference  TEXT NOT NULL DEFAULT '',
            notes              TEXT NOT NULL DEFAULT '',
            created_by         TEXT,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, farm_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_farms_org ON farms(org_id)"))

    # Membership tables: a field can hold more than one open (removed_at
    # IS NULL) row at once in EITHER table — that overlap is surfaced by
    # list_projects_for_field()/list_farms_for_field(), never collapsed.
    for _table, _owner_col in (("project_fields", "project_id"), ("farm_fields", "farm_id")):
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {_table} (
                membership_id         TEXT NOT NULL,
                org_id                 TEXT NOT NULL,
                {_owner_col}           TEXT NOT NULL,
                field_id               TEXT NOT NULL,
                effective_start_date   TEXT NOT NULL,
                effective_end_date     TEXT,
                assigned_by            TEXT,
                assigned_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                removed_at             TIMESTAMP,
                removed_reason         TEXT,
                PRIMARY KEY (org_id, membership_id)
            )
        """))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{_table}_owner ON {_table}(org_id, {_owner_col})"))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{_table}_field ON {_table}(org_id, field_id)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS attachments (
            org_id        TEXT NOT NULL,
            attachment_id TEXT NOT NULL,
            target_type   TEXT NOT NULL CHECK (target_type IN ('field', 'season', 'observation', 'practice_event')),
            target_id     TEXT NOT NULL,
            field_id      TEXT NOT NULL,
            filename      TEXT NOT NULL,
            content_type  TEXT NOT NULL,
            size_bytes    INTEGER NOT NULL,
            storage_key   TEXT NOT NULL,
            sha256        TEXT NOT NULL,
            uploaded_by   TEXT,
            uploaded_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, attachment_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_attachments_field ON attachments(org_id, field_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_attachments_target ON attachments(org_id, target_type, target_id)"))


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Projects
# --------------------------------------------------------------------------

def create_project(org_id: str, name: str, description: str, geography: str,
                    monitoring_start_date: str | None, monitoring_end_date: str | None,
                    status: str, created_by: str) -> str:
    project_id = uuid.uuid4().hex
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO projects (org_id, project_id, name, description, geography,
                                   monitoring_start_date, monitoring_end_date, status, created_by)
            VALUES (:org_id, :project_id, :name, :description, :geography,
                    :monitoring_start_date, :monitoring_end_date, :status, :created_by)
        """), {
            "org_id": org_id, "project_id": project_id, "name": name, "description": description,
            "geography": geography, "monitoring_start_date": monitoring_start_date,
            "monitoring_end_date": monitoring_end_date, "status": status, "created_by": created_by,
        })
        conn.commit()
    return project_id


def get_project(org_id: str, project_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(
            text("SELECT * FROM projects WHERE org_id = :org_id AND project_id = :project_id"),
            {"org_id": org_id, "project_id": project_id},
        ).mappings().fetchone()
    return dict(row) if row else None


def list_projects(org_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(
            text("SELECT * FROM projects WHERE org_id = :org_id ORDER BY created_at DESC"),
            {"org_id": org_id},
        ).mappings().fetchall()
    return [dict(r) for r in rows]


def update_project(org_id: str, project_id: str, name: str, description: str, geography: str,
                    monitoring_start_date: str | None, monitoring_end_date: str | None, status: str) -> None:
    with get_db_connection() as conn:
        conn.execute(text("""
            UPDATE projects SET name = :name, description = :description, geography = :geography,
                monitoring_start_date = :monitoring_start_date, monitoring_end_date = :monitoring_end_date,
                status = :status
            WHERE org_id = :org_id AND project_id = :project_id
        """), {
            "org_id": org_id, "project_id": project_id, "name": name, "description": description,
            "geography": geography, "monitoring_start_date": monitoring_start_date,
            "monitoring_end_date": monitoring_end_date, "status": status,
        })
        conn.commit()


# --------------------------------------------------------------------------
# Project members (responsible team members)
# --------------------------------------------------------------------------

def add_project_member(org_id: str, project_id: str, user_id: str, project_role: str,
                        actor: str, reason: str | None = None) -> None:
    with get_db_connection() as conn:
        existing = conn.execute(
            text("SELECT project_role FROM project_members WHERE org_id = :org_id AND project_id = :project_id AND user_id = :user_id"),
            {"org_id": org_id, "project_id": project_id, "user_id": user_id},
        ).mappings().fetchone()
        upsert = (
            "INSERT OR REPLACE INTO project_members (org_id, project_id, user_id, project_role) "
            "VALUES (:org_id, :project_id, :user_id, :project_role)"
        ) if is_sqlite() else (
            "INSERT INTO project_members (org_id, project_id, user_id, project_role) "
            "VALUES (:org_id, :project_id, :user_id, :project_role) "
            "ON CONFLICT (org_id, project_id, user_id) DO UPDATE SET project_role = excluded.project_role"
        )
        conn.execute(text(upsert), {
            "org_id": org_id, "project_id": project_id, "user_id": user_id, "project_role": project_role,
        })
        conn.execute(text("""
            INSERT INTO project_membership_events (org_id, id, project_id, user_id, action, project_role, actor, reason)
            VALUES (:org_id, :id, :project_id, :user_id, :action, :project_role, :actor, :reason)
        """), {"org_id": org_id, "id": uuid.uuid4().hex, "project_id": project_id, "user_id": user_id,
               "action": "role_changed" if existing else "added", "project_role": project_role,
               "actor": actor, "reason": reason})
        conn.commit()


def remove_project_member(org_id: str, project_id: str, user_id: str, actor: str, reason: str | None = None) -> None:
    with get_db_connection() as conn:
        conn.execute(
            text("DELETE FROM project_members WHERE org_id = :org_id AND project_id = :project_id AND user_id = :user_id"),
            {"org_id": org_id, "project_id": project_id, "user_id": user_id},
        )
        conn.execute(text("""
            INSERT INTO project_membership_events (org_id, id, project_id, user_id, action, actor, reason)
            VALUES (:org_id, :id, :project_id, :user_id, 'removed', :actor, :reason)
        """), {"org_id": org_id, "id": uuid.uuid4().hex, "project_id": project_id, "user_id": user_id,
               "actor": actor, "reason": reason})
        conn.commit()


def membership_events(org_id: str, project_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT * FROM project_membership_events WHERE org_id = :org_id AND project_id = :project_id
            ORDER BY created_at
        """), {"org_id": org_id, "project_id": project_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def get_project_member(org_id: str, project_id: str, user_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(text("""
            SELECT pm.user_id, pm.project_role, pm.added_at, u.email
            FROM project_members pm JOIN users u ON u.user_id = pm.user_id
            WHERE pm.org_id = :org_id AND pm.project_id = :project_id AND pm.user_id = :user_id
        """), {"org_id": org_id, "project_id": project_id, "user_id": user_id}).mappings().fetchone()
    return dict(row) if row else None


def list_project_members(org_id: str, project_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT pm.user_id, pm.project_role, pm.added_at, u.email
            FROM project_members pm JOIN users u ON u.user_id = pm.user_id
            WHERE pm.org_id = :org_id AND pm.project_id = :project_id
            ORDER BY pm.added_at
        """), {"org_id": org_id, "project_id": project_id}).mappings().fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Farms
# --------------------------------------------------------------------------

def create_farm(org_id: str, name: str, contact_name: str, contact_phone: str, contact_email: str,
                 consent_given: bool, consent_reference: str, notes: str, created_by: str) -> str:
    farm_id = uuid.uuid4().hex
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO farms (org_id, farm_id, name, contact_name, contact_phone, contact_email,
                                consent_given, consent_reference, notes, created_by)
            VALUES (:org_id, :farm_id, :name, :contact_name, :contact_phone, :contact_email,
                    :consent_given, :consent_reference, :notes, :created_by)
        """), {
            "org_id": org_id, "farm_id": farm_id, "name": name, "contact_name": contact_name,
            "contact_phone": contact_phone, "contact_email": contact_email,
            "consent_given": int(consent_given), "consent_reference": consent_reference,
            "notes": notes, "created_by": created_by,
        })
        conn.commit()
    return farm_id


def get_farm(org_id: str, farm_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(
            text("SELECT * FROM farms WHERE org_id = :org_id AND farm_id = :farm_id"),
            {"org_id": org_id, "farm_id": farm_id},
        ).mappings().fetchone()
    if row is None:
        return None
    result = dict(row)
    result["consent_given"] = bool(result["consent_given"])
    return result


def list_farms(org_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(
            text("SELECT * FROM farms WHERE org_id = :org_id ORDER BY created_at DESC"),
            {"org_id": org_id},
        ).mappings().fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["consent_given"] = bool(d["consent_given"])
        result.append(d)
    return result


def update_farm(org_id: str, farm_id: str, name: str, contact_name: str, contact_phone: str,
                 contact_email: str, consent_given: bool, consent_reference: str, notes: str) -> None:
    with get_db_connection() as conn:
        conn.execute(text("""
            UPDATE farms SET name = :name, contact_name = :contact_name, contact_phone = :contact_phone,
                contact_email = :contact_email, consent_given = :consent_given,
                consent_reference = :consent_reference, notes = :notes
            WHERE org_id = :org_id AND farm_id = :farm_id
        """), {
            "org_id": org_id, "farm_id": farm_id, "name": name, "contact_name": contact_name,
            "contact_phone": contact_phone, "contact_email": contact_email,
            "consent_given": int(consent_given), "consent_reference": consent_reference, "notes": notes,
        })
        conn.commit()


# --------------------------------------------------------------------------
# Field <-> project / field <-> farm membership (shared implementation)
# --------------------------------------------------------------------------

def _assign_field(table: str, owner_col: str, org_id: str, owner_id: str, field_id: str,
                   effective_start_date: str, assigned_by: str) -> str:
    membership_id = uuid.uuid4().hex
    with get_db_connection() as conn:
        conn.execute(
            text(f"""
                INSERT INTO {table} (membership_id, org_id, {owner_col}, field_id,
                                      effective_start_date, assigned_by)
                VALUES (:membership_id, :org_id, :owner_id, :field_id, :effective_start_date, :assigned_by)
            """),
            {"membership_id": membership_id, "org_id": org_id, "owner_id": owner_id, "field_id": field_id,
             "effective_start_date": effective_start_date, "assigned_by": assigned_by},
        )
        conn.commit()
    return membership_id


def _end_membership(table: str, org_id: str, membership_id: str, effective_end_date: str, reason: str) -> bool:
    with get_db_connection() as conn:
        result = conn.execute(
            text(f"""
                UPDATE {table} SET effective_end_date = :end_date, removed_at = CURRENT_TIMESTAMP,
                    removed_reason = :reason
                WHERE org_id = :org_id AND membership_id = :membership_id AND removed_at IS NULL
            """),
            {"org_id": org_id, "membership_id": membership_id, "end_date": effective_end_date, "reason": reason},
        )
        conn.commit()
    return result.rowcount > 0


def _list_memberships(table: str, owner_col: str, org_id: str, owner_id: str | None = None,
                       field_id: str | None = None) -> list[dict]:
    query = f"SELECT * FROM {table} WHERE org_id = :org_id"
    params = {"org_id": org_id}
    if owner_id is not None:
        query += f" AND {owner_col} = :owner_id"
        params["owner_id"] = owner_id
    if field_id is not None:
        query += " AND field_id = :field_id"
        params["field_id"] = field_id
    query += " ORDER BY assigned_at"
    with get_db_connection() as conn:
        rows = conn.execute(text(query), params).mappings().fetchall()
    return [dict(r) for r in rows]


def assign_field_to_project(org_id: str, project_id: str, field_id: str,
                             effective_start_date: str, assigned_by: str) -> str:
    return _assign_field("project_fields", "project_id", org_id, project_id, field_id,
                          effective_start_date, assigned_by)


def end_project_field_membership(org_id: str, membership_id: str, effective_end_date: str, reason: str) -> bool:
    return _end_membership("project_fields", org_id, membership_id, effective_end_date, reason)


def list_project_fields(org_id: str, project_id: str) -> list[dict]:
    return _list_memberships("project_fields", "project_id", org_id, owner_id=project_id)


def list_projects_for_field(org_id: str, field_id: str) -> list[dict]:
    return _list_memberships("project_fields", "project_id", org_id, field_id=field_id)


def assign_field_to_farm(org_id: str, farm_id: str, field_id: str,
                          effective_start_date: str, assigned_by: str) -> str:
    return _assign_field("farm_fields", "farm_id", org_id, farm_id, field_id,
                          effective_start_date, assigned_by)


def end_farm_field_membership(org_id: str, membership_id: str, effective_end_date: str, reason: str) -> bool:
    return _end_membership("farm_fields", org_id, membership_id, effective_end_date, reason)


def list_farm_fields(org_id: str, farm_id: str) -> list[dict]:
    return _list_memberships("farm_fields", "farm_id", org_id, owner_id=farm_id)


def list_farms_for_field(org_id: str, field_id: str) -> list[dict]:
    return _list_memberships("farm_fields", "farm_id", org_id, field_id=field_id)


# --------------------------------------------------------------------------
# Attachments (metadata rows — file bytes live in src.storage)
# --------------------------------------------------------------------------

ATTACHMENT_TARGET_TYPES = {"field", "season", "observation", "practice_event"}


def create_attachment(org_id: str, target_type: str, target_id: str, field_id: str, filename: str,
                       content_type: str, size_bytes: int, storage_key: str, sha256: str,
                       uploaded_by: str, attachment_id: str | None = None) -> str:
    attachment_id = attachment_id or uuid.uuid4().hex
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO attachments (org_id, attachment_id, target_type, target_id, field_id,
                                      filename, content_type, size_bytes, storage_key, sha256, uploaded_by)
            VALUES (:org_id, :attachment_id, :target_type, :target_id, :field_id,
                    :filename, :content_type, :size_bytes, :storage_key, :sha256, :uploaded_by)
        """), {
            "org_id": org_id, "attachment_id": attachment_id, "target_type": target_type,
            "target_id": target_id, "field_id": field_id, "filename": filename,
            "content_type": content_type, "size_bytes": size_bytes, "storage_key": storage_key,
            "sha256": sha256, "uploaded_by": uploaded_by,
        })
        conn.commit()
    return attachment_id


def get_attachment(org_id: str, attachment_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(
            text("SELECT * FROM attachments WHERE org_id = :org_id AND attachment_id = :attachment_id"),
            {"org_id": org_id, "attachment_id": attachment_id},
        ).mappings().fetchone()
    return dict(row) if row else None


def list_attachments(org_id: str, target_type: str, target_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT * FROM attachments
            WHERE org_id = :org_id AND target_type = :target_type AND target_id = :target_id
            ORDER BY uploaded_at
        """), {"org_id": org_id, "target_type": target_type, "target_id": target_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def delete_attachment_record(org_id: str, attachment_id: str) -> bool:
    with get_db_connection() as conn:
        result = conn.execute(
            text("DELETE FROM attachments WHERE org_id = :org_id AND attachment_id = :attachment_id"),
            {"org_id": org_id, "attachment_id": attachment_id},
        )
        conn.commit()
    return result.rowcount > 0


# --------------------------------------------------------------------------
# Project dashboard
# --------------------------------------------------------------------------

def project_dashboard(org_id: str, project_id: str) -> dict:
    """Aggregates what the project dashboard needs in one call: open field
    memberships (with farm + latest crop-season + latest monitoring status
    per field) and a missing-information checklist. Reads across
    src.database (fields/credit history) and src.monitoring (crop seasons/
    monitoring runs) — this module doesn't own that data, it just reads it,
    same as backend/routers already do from multiple modules per request."""
    from src import monitoring as _monitoring

    memberships = [m for m in list_project_fields(org_id, project_id) if m["removed_at"] is None]
    members = list_project_members(org_id, project_id)

    field_rows = []
    missing = []
    for m in memberships:
        field = get_field(org_id, m["field_id"])
        if field is None:
            continue  # field was deleted; membership row is kept for history but has nothing to show
        farms = [f for f in list_farms_for_field(org_id, m["field_id"]) if f["removed_at"] is None]
        seasons = _monitoring.records("crop_seasons", org_id, m["field_id"])
        latest_season = seasons[-1] if seasons else None
        runs = _monitoring.records("monitoring_runs", org_id, m["field_id"],
                                    latest_season["id"] if latest_season else None) if latest_season else []
        latest_run = runs[-1] if runs else None

        if not farms:
            missing.append({"field_id": m["field_id"], "issue": "not assigned to a farm"})
        if not seasons:
            missing.append({"field_id": m["field_id"], "issue": "no crop season recorded"})
        elif not latest_run:
            missing.append({"field_id": m["field_id"], "issue": "no monitoring snapshot for its latest season"})

        field_rows.append({
            "field_id": field["field_id"],
            "name": field["name"],
            "district": field["district"],
            "field_type": field["field_type"],
            "farm_ids": [f["farm_id"] for f in farms],
            "latest_season": {"id": latest_season["id"], "name": latest_season["payload"]["name"],
                               "crops": latest_season["payload"]["crops"]} if latest_season else None,
            "latest_monitoring_status": latest_run["payload"]["quality"]["status"] if latest_run else None,
        })

    farm_ids = {fid for row in field_rows for fid in row["farm_ids"]}
    return {
        "field_count": len(field_rows),
        "farm_count": len(farm_ids),
        "fields": field_rows,
        "members": members,
        "missing_information": missing,
    }
