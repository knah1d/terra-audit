"""Internal review, correction requests, and approval history — Phase 3
(see src/calculations.py and src/projects.py's module docstrings for the
two structures this reuses: immutable calculation versions, and
project_members for "project authorization").

Scope discipline (explicit in the Phase 3 brief): this is INTERNAL review
only. Nothing here sets or reads any external-verification / registry-
issuance state — those remain entirely separate, future concepts. An
"internally_approved" submission means exactly that: an internal sign-off
event, never surfaced as anything more.

Compatibility: purely additive tables. Calculations (Phase 2) and
projects/farms (Phase 1) are read-only from this module's perspective —
a submission PINS a specific immutable calculation_id; it never edits or
recomputes it. Resubmission always means "supersede the calculation
first (Phase 2's own versioning), then submit the new version" — this
module has no separate versioning scheme of its own for the calculation
side, only for its own submission chain (previous_submission_id).

Concurrency: review_submissions carries a plain optimistic-lock `version`
integer (unrelated to a calculation's version) — every lifecycle-mutating
call must pass the row's current version; a mismatch raises
StaleSubmissionError (a stale browser tab, or a second concurrent
approve/reject, loses instead of silently overwriting the other's
decision).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from src.calculations import get_calculation
from src.database import get_db_connection
from src.projects import get_project_member

STATUSES = {"submitted", "in_review", "changes_requested", "internally_approved", "rejected", "withdrawn"}
TERMINAL_STATUSES = {"internally_approved", "rejected", "withdrawn"}
FINDING_SEVERITIES = {"blocking", "major", "minor", "info"}

# Server-enforced transition table: {from_status: {to_status: reason_required}}
TRANSITIONS = {
    "submitted": {"in_review": False, "withdrawn": True},
    "in_review": {"changes_requested": True, "internally_approved": True, "rejected": True, "withdrawn": True},
    "changes_requested": {"withdrawn": True},
}


class StaleSubmissionError(ValueError):
    """Raised when a caller's `if_version` no longer matches the row —
    translated to 409 by backend/routers/reviews.py (not 422 like a plain
    ValueError) since this is a concurrency conflict, not a bad request."""


def initialize_tables(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS review_submissions (
            org_id                  TEXT NOT NULL,
            submission_id           TEXT NOT NULL,
            project_id              TEXT NOT NULL,
            field_id                TEXT NOT NULL,
            calculation_id          TEXT NOT NULL,
            chain_id                TEXT NOT NULL,
            previous_submission_id  TEXT,
            status                  TEXT NOT NULL DEFAULT 'submitted'
                                    CHECK (status IN ('submitted', 'in_review', 'changes_requested',
                                                       'internally_approved', 'rejected', 'withdrawn')),
            version                 INTEGER NOT NULL DEFAULT 1,
            assigned_reviewer_id    TEXT,
            submitted_by            TEXT NOT NULL,
            submitted_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            decided_at              TIMESTAMP,
            decision_reason         TEXT,
            PRIMARY KEY (org_id, submission_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_review_submissions_project ON review_submissions(org_id, project_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_review_submissions_field ON review_submissions(org_id, field_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_review_submissions_calc ON review_submissions(org_id, calculation_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_review_submissions_reviewer ON review_submissions(org_id, assigned_reviewer_id)"))

    # Append-only: current assignment = latest row per submission_id.
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS reviewer_assignments (
            id             TEXT NOT NULL,
            org_id         TEXT NOT NULL,
            submission_id  TEXT NOT NULL,
            reviewer_id    TEXT,
            assigned_by    TEXT NOT NULL,
            reason         TEXT NOT NULL,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_reviewer_assignments_sub ON reviewer_assignments(org_id, submission_id)"))

    # Append-only lifecycle/audit trail — includes the approval event itself.
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS review_events (
            id             TEXT NOT NULL,
            org_id         TEXT NOT NULL,
            submission_id  TEXT NOT NULL,
            from_status    TEXT NOT NULL,
            to_status      TEXT NOT NULL,
            actor          TEXT NOT NULL,
            reason         TEXT,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_review_events_sub ON review_events(org_id, submission_id)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS findings (
            org_id            TEXT NOT NULL,
            finding_id        TEXT NOT NULL,
            submission_id     TEXT NOT NULL,
            requirement_id    TEXT,
            input_ref         TEXT,
            evidence_ref      TEXT,
            severity          TEXT NOT NULL CHECK (severity IN ('blocking', 'major', 'minor', 'info')),
            description       TEXT NOT NULL,
            requested_action  TEXT NOT NULL DEFAULT '',
            author             TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
            closed_by          TEXT,
            closed_at          TIMESTAMP,
            close_reason       TEXT,
            carried_from_finding_id TEXT,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, finding_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_findings_sub ON findings(org_id, submission_id)"))

    # Append-only replies/proposed resolutions on a finding.
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS finding_comments (
            id                      TEXT NOT NULL,
            org_id                  TEXT NOT NULL,
            finding_id              TEXT NOT NULL,
            author                  TEXT NOT NULL,
            body                    TEXT NOT NULL,
            is_proposed_resolution  INTEGER NOT NULL DEFAULT 0,
            created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_finding_comments_finding ON finding_comments(org_id, finding_id)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS notifications (
            id             TEXT NOT NULL,
            org_id         TEXT NOT NULL,
            user_id        TEXT NOT NULL,
            kind           TEXT NOT NULL,
            submission_id  TEXT,
            finding_id     TEXT,
            batch_id       TEXT,
            issue_id       TEXT,
            message        TEXT NOT NULL,
            read_at        TIMESTAMP,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(org_id, user_id)"))
    # Additive columns for a pre-Phase-4 notifications table (Phase 4 adds
    # batch/issue links alongside the existing submission/finding ones).
    # Postgres supports IF NOT EXISTS directly (no transaction-poisoning
    # risk); SQLite doesn't, so it's guarded the same try/except way
    # src.database's own SQLite ALTER-TABLE migrations already are.
    from src.database import is_sqlite
    for col in ("batch_id", "issue_id"):
        if is_sqlite():
            try:
                conn.execute(text(f"ALTER TABLE notifications ADD COLUMN {col} TEXT"))
            except Exception:
                pass
        else:
            conn.execute(text(f"ALTER TABLE notifications ADD COLUMN IF NOT EXISTS {col} TEXT"))


def _uid():
    return uuid.uuid4().hex


def _notify(conn, org_id, user_id, kind, submission_id, finding_id, message, batch_id=None, issue_id=None):
    if not user_id:
        return
    conn.execute(text("""
        INSERT INTO notifications (id, org_id, user_id, kind, submission_id, finding_id, batch_id, issue_id, message)
        VALUES (:id, :org_id, :user_id, :kind, :submission_id, :finding_id, :batch_id, :issue_id, :message)
    """), {"id": _uid(), "org_id": org_id, "user_id": user_id, "kind": kind,
           "submission_id": submission_id, "finding_id": finding_id, "batch_id": batch_id,
           "issue_id": issue_id, "message": message})


def notify(org_id: str, user_id: str, kind: str, message: str, submission_id: str | None = None,
           finding_id: str | None = None, batch_id: str | None = None, issue_id: str | None = None) -> None:
    """Public entry point for OTHER modules (src.jobs/src.monitoring_ops
    via backend/job_handlers.py) to raise an in-app notification —
    reuses this table/module rather than standing up a parallel one."""
    with get_db_connection() as conn:
        _notify(conn, org_id, user_id, kind, submission_id, finding_id, message, batch_id, issue_id)
        conn.commit()


# --------------------------------------------------------------------------
# Submissions
# --------------------------------------------------------------------------

def create_submission(org_id: str, project_id: str, calculation: dict, submitted_by: str,
                       previous_submission_id: str | None = None) -> dict:
    """Freezes a submission against a specific, already-immutable
    calculation version. Requires that calculation to be
    'ready_for_review' (Phase 2's own no-blocking-readiness-items
    definition) — the caller (router) checks this before calling, this
    function re-checks defensively."""
    if calculation["status"] != "ready_for_review":
        raise ValueError(
            "Only a calculation with status 'ready_for_review' (no blocking readiness items) can be submitted for review."
        )
    with get_db_connection() as conn:
        existing = conn.execute(text("""
            SELECT status FROM review_submissions
            WHERE org_id = :org_id AND calculation_id = :calculation_id
            ORDER BY submitted_at DESC LIMIT 1
        """), {"org_id": org_id, "calculation_id": calculation["calculation_id"]}).mappings().fetchone()
        if existing is not None and existing["status"] != "withdrawn":
            raise ValueError(
                f"A submission already exists for this calculation version (status: {existing['status']}). "
                "Withdraw it first, or create a new calculation version to resubmit."
            )
        if previous_submission_id is not None:
            prior = conn.execute(text("""
                SELECT status FROM review_submissions WHERE org_id = :org_id AND submission_id = :sid
            """), {"org_id": org_id, "sid": previous_submission_id}).mappings().fetchone()
            if prior is None:
                raise ValueError("previous_submission_id not found")

        submission_id = _uid()
        conn.execute(text("""
            INSERT INTO review_submissions
                (org_id, submission_id, project_id, field_id, calculation_id, chain_id,
                 previous_submission_id, status, version, submitted_by)
            VALUES (:org_id, :submission_id, :project_id, :field_id, :calculation_id, :chain_id,
                    :previous_submission_id, 'submitted', 1, :submitted_by)
        """), {"org_id": org_id, "submission_id": submission_id, "project_id": project_id,
               "field_id": calculation["field_id"], "calculation_id": calculation["calculation_id"],
               "chain_id": calculation["chain_id"], "previous_submission_id": previous_submission_id,
               "submitted_by": submitted_by})
        conn.execute(text("""
            INSERT INTO review_events (id, org_id, submission_id, from_status, to_status, actor, reason)
            VALUES (:id, :org_id, :sid, '', 'submitted', :actor, NULL)
        """), {"id": _uid(), "org_id": org_id, "sid": submission_id, "actor": submitted_by})
        conn.commit()
    return get_submission(org_id, submission_id)


def get_submission(org_id: str, submission_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM review_submissions WHERE org_id = :org_id AND submission_id = :submission_id"
        ), {"org_id": org_id, "submission_id": submission_id}).mappings().fetchone()
    return dict(row) if row else None


def list_submissions(org_id: str, project_id: str | None = None, reviewer_id: str | None = None,
                      status_filter: list[str] | None = None) -> list[dict]:
    query = "SELECT * FROM review_submissions WHERE org_id = :org_id"
    params = {"org_id": org_id}
    if project_id is not None:
        query += " AND project_id = :project_id"
        params["project_id"] = project_id
    if reviewer_id is not None:
        query += " AND assigned_reviewer_id = :reviewer_id"
        params["reviewer_id"] = reviewer_id
    if status_filter:
        placeholders = ", ".join(f":status{i}" for i in range(len(status_filter)))
        query += f" AND status IN ({placeholders})"
        params.update({f"status{i}": s for i, s in enumerate(status_filter)})
    query += " ORDER BY submitted_at DESC"
    with get_db_connection() as conn:
        rows = conn.execute(text(query), params).mappings().fetchall()
    return [dict(r) for r in rows]


def _apply_transition(conn, org_id, submission_id, current_version, if_version, from_status, to_status,
                       actor, reason, extra_sql="", extra_params=None):
    if if_version != current_version:
        raise StaleSubmissionError(
            "This submission was changed by someone else since you loaded it. Reload and try again."
        )
    params = {"org_id": org_id, "sid": submission_id, "status": to_status, "new_version": current_version + 1,
              **(extra_params or {})}
    result = conn.execute(text(f"""
        UPDATE review_submissions SET status = :status, version = :new_version {extra_sql}
        WHERE org_id = :org_id AND submission_id = :sid AND version = :old_version
    """), {**params, "old_version": current_version})
    if result.rowcount == 0:
        raise StaleSubmissionError("This submission was changed by someone else since you loaded it. Reload and try again.")
    conn.execute(text("""
        INSERT INTO review_events (id, org_id, submission_id, from_status, to_status, actor, reason)
        VALUES (:id, :org_id, :sid, :from_status, :to_status, :actor, :reason)
    """), {"id": _uid(), "org_id": org_id, "sid": submission_id, "from_status": from_status,
           "to_status": to_status, "actor": actor, "reason": reason})


def transition(org_id: str, submission_id: str, if_version: int, to_status: str, actor: str,
               reason: str | None, notify_user_id: str | None = None, notify_kind: str | None = None,
               notify_message: str | None = None) -> dict:
    submission = get_submission(org_id, submission_id)
    if submission is None:
        raise ValueError("Submission not found")
    allowed = TRANSITIONS.get(submission["status"], {})
    if to_status not in allowed:
        raise ValueError(f"Cannot move a submission from '{submission['status']}' to '{to_status}'")
    if allowed[to_status] and not (reason and reason.strip()):
        raise ValueError(f"A reason is required to move a submission to '{to_status}'")

    if to_status in ("internally_approved", "rejected"):
        blocking_open = [f for f in list_findings(org_id, submission_id)
                          if f["severity"] == "blocking" and f["status"] == "open"]
        if to_status == "internally_approved" and blocking_open:
            raise ValueError(
                f"{len(blocking_open)} blocking finding(s) are still open — resolve or close them before approving."
            )

    extra_sql, extra_params = "", {}
    if to_status in TERMINAL_STATUSES:
        extra_sql = ", decided_at = CURRENT_TIMESTAMP, decision_reason = :decision_reason"
        extra_params = {"decision_reason": reason}

    with get_db_connection() as conn:
        _apply_transition(conn, org_id, submission_id, submission["version"], if_version,
                           submission["status"], to_status, actor, reason, extra_sql, extra_params)
        if notify_user_id:
            _notify(conn, org_id, notify_user_id, notify_kind, submission_id, None, notify_message)
        conn.commit()
    return get_submission(org_id, submission_id)


# --------------------------------------------------------------------------
# Reviewer assignment
# --------------------------------------------------------------------------

def assign_reviewer(org_id: str, submission_id: str, reviewer_id: str | None, assigned_by: str,
                     reason: str) -> dict:
    submission = get_submission(org_id, submission_id)
    if submission is None:
        raise ValueError("Submission not found")
    if submission["status"] in TERMINAL_STATUSES:
        raise ValueError(f"Cannot reassign a reviewer on a submission that is already '{submission['status']}'")
    if not reason or not reason.strip():
        raise ValueError("A reason is required to assign or reassign a reviewer")
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO reviewer_assignments (id, org_id, submission_id, reviewer_id, assigned_by, reason)
            VALUES (:id, :org_id, :sid, :reviewer_id, :assigned_by, :reason)
        """), {"id": _uid(), "org_id": org_id, "sid": submission_id, "reviewer_id": reviewer_id,
               "assigned_by": assigned_by, "reason": reason})
        conn.execute(text("""
            UPDATE review_submissions SET assigned_reviewer_id = :reviewer_id
            WHERE org_id = :org_id AND submission_id = :sid
        """), {"reviewer_id": reviewer_id, "org_id": org_id, "sid": submission_id})
        if reviewer_id:
            _notify(conn, org_id, reviewer_id, "reviewer_assigned", submission_id, None,
                    "You were assigned as reviewer for a submission.")
        conn.commit()
    return get_submission(org_id, submission_id)


def assignment_history(org_id: str, submission_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT * FROM reviewer_assignments WHERE org_id = :org_id AND submission_id = :sid ORDER BY created_at
        """), {"org_id": org_id, "sid": submission_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def events(org_id: str, submission_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT * FROM review_events WHERE org_id = :org_id AND submission_id = :sid ORDER BY created_at
        """), {"org_id": org_id, "sid": submission_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def current_reviewer_has_access(org_id: str, project_id: str, reviewer_id: str | None) -> bool:
    """Live re-check — used on every reviewer-gated action, not cached
    from assignment time, so a reviewer removed from the project after
    being assigned can no longer act."""
    if not reviewer_id:
        return False
    return get_project_member(org_id, project_id, reviewer_id) is not None


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------

def create_finding(org_id: str, submission_id: str, author: str, severity: str, description: str,
                    requested_action: str, requirement_id: str | None, input_ref: str | None,
                    evidence_ref: str | None, carried_from_finding_id: str | None = None) -> dict:
    if severity not in FINDING_SEVERITIES:
        raise ValueError(f"severity must be one of {sorted(FINDING_SEVERITIES)}")
    finding_id = _uid()
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO findings (org_id, finding_id, submission_id, requirement_id, input_ref, evidence_ref,
                                   severity, description, requested_action, author, carried_from_finding_id)
            VALUES (:org_id, :finding_id, :sid, :requirement_id, :input_ref, :evidence_ref,
                    :severity, :description, :requested_action, :author, :carried_from_finding_id)
        """), {"org_id": org_id, "finding_id": finding_id, "sid": submission_id, "requirement_id": requirement_id,
               "input_ref": input_ref, "evidence_ref": evidence_ref, "severity": severity,
               "description": description, "requested_action": requested_action, "author": author,
               "carried_from_finding_id": carried_from_finding_id})
        conn.commit()
    return get_finding(org_id, finding_id)


def get_finding(org_id: str, finding_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM findings WHERE org_id = :org_id AND finding_id = :finding_id"
        ), {"org_id": org_id, "finding_id": finding_id}).mappings().fetchone()
    return dict(row) if row else None


def list_findings(org_id: str, submission_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT * FROM findings WHERE org_id = :org_id AND submission_id = :sid ORDER BY created_at
        """), {"org_id": org_id, "sid": submission_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def close_finding(org_id: str, finding_id: str, closed_by: str, reason: str) -> dict:
    if not reason or not reason.strip():
        raise ValueError("A reason is required to close a finding")
    finding = get_finding(org_id, finding_id)
    if finding is None:
        raise ValueError("Finding not found")
    if finding["status"] == "closed":
        raise ValueError("Finding is already closed")
    with get_db_connection() as conn:
        conn.execute(text("""
            UPDATE findings SET status = 'closed', closed_by = :closed_by, closed_at = CURRENT_TIMESTAMP,
                                 close_reason = :reason
            WHERE org_id = :org_id AND finding_id = :finding_id
        """), {"closed_by": closed_by, "reason": reason, "org_id": org_id, "finding_id": finding_id})
        conn.commit()
    return get_finding(org_id, finding_id)


def add_comment(org_id: str, finding_id: str, author: str, body: str, is_proposed_resolution: bool) -> dict:
    comment_id = _uid()
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO finding_comments (id, org_id, finding_id, author, body, is_proposed_resolution)
            VALUES (:id, :org_id, :finding_id, :author, :body, :is_proposed_resolution)
        """), {"id": comment_id, "org_id": org_id, "finding_id": finding_id, "author": author,
               "body": body, "is_proposed_resolution": int(is_proposed_resolution)})
        finding = conn.execute(text(
            "SELECT submission_id FROM findings WHERE org_id = :org_id AND finding_id = :finding_id"
        ), {"org_id": org_id, "finding_id": finding_id}).mappings().fetchone()
        if finding is not None:
            submission = conn.execute(text(
                "SELECT submitted_by, assigned_reviewer_id FROM review_submissions "
                "WHERE org_id = :org_id AND submission_id = :sid"
            ), {"org_id": org_id, "sid": finding["submission_id"]}).mappings().fetchone()
            if submission is not None:
                for recipient in {submission["submitted_by"], submission["assigned_reviewer_id"]} - {author}:
                    _notify(conn, org_id, recipient, "finding_reply", finding["submission_id"], finding_id,
                            "New reply on a finding you're involved in.")
        conn.commit()
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM finding_comments WHERE org_id = :org_id AND id = :id"
        ), {"org_id": org_id, "id": comment_id}).mappings().fetchone()
    return dict(row)


def list_comments(org_id: str, finding_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT * FROM finding_comments WHERE org_id = :org_id AND finding_id = :finding_id ORDER BY created_at
        """), {"org_id": org_id, "finding_id": finding_id}).mappings().fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------

def list_notifications(org_id: str, user_id: str, unread_only: bool = False) -> list[dict]:
    query = "SELECT * FROM notifications WHERE org_id = :org_id AND user_id = :user_id"
    if unread_only:
        query += " AND read_at IS NULL"
    query += " ORDER BY created_at DESC"
    with get_db_connection() as conn:
        rows = conn.execute(text(query), {"org_id": org_id, "user_id": user_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def mark_notification_read(org_id: str, user_id: str, notification_id: str) -> bool:
    with get_db_connection() as conn:
        result = conn.execute(text("""
            UPDATE notifications SET read_at = CURRENT_TIMESTAMP
            WHERE org_id = :org_id AND user_id = :user_id AND id = :id AND read_at IS NULL
        """), {"org_id": org_id, "user_id": user_id, "id": notification_id})
        conn.commit()
    return result.rowcount > 0


# --------------------------------------------------------------------------
# Cross-version comparison ("show reviewers what changed")
# --------------------------------------------------------------------------

def diff_submissions(org_id: str, submission_id: str, previous_submission_id: str) -> dict:
    current = get_submission(org_id, submission_id)
    previous = get_submission(org_id, previous_submission_id)
    if current is None or previous is None:
        raise ValueError("Submission not found")
    current_calc = get_calculation(org_id, current["calculation_id"])
    previous_calc = get_calculation(org_id, previous["calculation_id"])

    def _flat_diff(a: dict, b: dict) -> dict:
        keys = set(a) | set(b)
        return {k: {"previous": b.get(k), "current": a.get(k)} for k in keys if a.get(k) != b.get(k)}

    readiness_by_id_current = {c["requirement_id"]: c["status"] for c in current_calc["readiness"]}
    readiness_by_id_previous = {c["requirement_id"]: c["status"] for c in previous_calc["readiness"]}
    readiness_changes = {
        rid: {"previous": readiness_by_id_previous.get(rid), "current": readiness_by_id_current.get(rid)}
        for rid in set(readiness_by_id_current) | set(readiness_by_id_previous)
        if readiness_by_id_current.get(rid) != readiness_by_id_previous.get(rid)
    }
    return {
        "previous_calculation_id": previous_calc["calculation_id"],
        "current_calculation_id": current_calc["calculation_id"],
        "inputs_changed": _flat_diff(current_calc["inputs"], previous_calc["inputs"]),
        "result_changed": _flat_diff(current_calc["result"], previous_calc["result"]),
        "readiness_changed": readiness_changes,
        "season_ids_changed": current_calc["season_ids"] != previous_calc["season_ids"],
    }


def field_has_submissions(org_id: str, field_id: str) -> bool:
    """Used by the fields router to refuse deleting a field that has any
    review history (submitted, in progress, or terminal) — approved or
    otherwise decided packages must stay reproducible, not silently
    vanish because someone deleted the underlying field."""
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT 1 FROM review_submissions WHERE org_id = :org_id AND field_id = :field_id LIMIT 1"
        ), {"org_id": org_id, "field_id": field_id}).fetchone()
    return row is not None
