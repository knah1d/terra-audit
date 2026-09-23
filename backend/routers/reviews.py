"""Internal review, correction requests, and approval history — Phase 3.

Two permission layers, same pattern the rest of the API already uses:
  1. Org role (backend.deps.require_writer/require_admin) — general
     ability to write at all.
  2. Project-scoped role (src.projects.get_project_member) — whether
     THIS user may act on THIS project's submissions. An org 'admin'
     always passes layer 2 too (matches the rest of the app's admin
     model); nothing here ever trusts a client-supplied role claim.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from backend.deps import get_current_user, require_writer
from backend.schemas.reviews import (
    AssignReviewerRequest, CommentCreate, FindingClose, FindingCreate, SubmissionCreate, TransitionRequest,
)
from src import projects as projects_db
from src import reviews as reviews_db
from src.calculations import get_calculation
from src.reviews import StaleSubmissionError

router = APIRouter(tags=["reviews"])


def _project_role(org_id: str, project_id: str, user_id: str) -> str | None:
    member = projects_db.get_project_member(org_id, project_id, user_id)
    return member["project_role"] if member else None


def _require_project_access(user: dict, project_id: str) -> str | None:
    """Returns the caller's project role (None for an org admin acting
    without project membership) — raises 403 if neither applies."""
    if user["role"] == "admin":
        return _project_role(user["org_id"], project_id, user["user_id"])
    role = _project_role(user["org_id"], project_id, user["user_id"])
    if role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not a member of this project")
    return role


def _require_project_lead(user: dict, project_id: str) -> None:
    if user["role"] == "admin":
        return
    role = _project_role(user["org_id"], project_id, user["user_id"])
    if role != "lead":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a project lead or org admin can do this")


_OPEN_STATUSES = {"submitted", "in_review", "changes_requested"}
_OVERDUE_AFTER = timedelta(days=7)


def _with_overdue(rows: list[dict]) -> list[dict]:
    """Adds a server-computed `overdue` flag (open >7 days) — computed
    here rather than client-side so the frontend never has to reason
    about "now" itself (and can filter/sort by it consistently)."""
    now = datetime.now(timezone.utc)
    out = []
    for r in rows:
        overdue = False
        if r["status"] in _OPEN_STATUSES and r.get("submitted_at"):
            try:
                ts = r["submitted_at"]
                ts = datetime.fromisoformat(str(ts).replace(" ", "T"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                overdue = (now - ts) > _OVERDUE_AFTER
            except ValueError:
                pass
        out.append({**r, "overdue": overdue})
    return out


def _owned_submission(org_id: str, submission_id: str) -> dict:
    submission = reviews_db.get_submission(org_id, submission_id)
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    return submission


def _owned_finding(org_id: str, finding_id: str) -> dict:
    finding = reviews_db.get_finding(org_id, finding_id)
    if finding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    return finding


def _require_current_reviewer(user: dict, submission: dict) -> None:
    """Live re-check on every reviewer-gated action — an org admin may
    still override, but a non-admin must be BOTH the currently assigned
    reviewer AND currently have project access (reviews.
    current_reviewer_has_access), so removing someone from the project
    revokes their ability to act even though they're still "assigned"."""
    if user["role"] == "admin":
        return
    if submission["assigned_reviewer_id"] != user["user_id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the currently assigned reviewer can do this")
    if not reviews_db.current_reviewer_has_access(user["org_id"], submission["project_id"], user["user_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your access to this project has been removed")


@router.post("/projects/{project_id}/submissions", status_code=status.HTTP_201_CREATED)
def create_submission(project_id: str, body: SubmissionCreate, user=Depends(require_writer)):
    org_id = user["org_id"]
    _require_project_access(user, project_id)
    if projects_db.get_project(org_id, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    calculation = get_calculation(org_id, body.calculation_id)
    if calculation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calculation not found")
    if calculation["project_id"] != project_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "This calculation was not computed in the context of this project — submit it under its own project.",
        )

    prior_findings = []
    if body.previous_submission_id is not None:
        prior = _owned_submission(org_id, body.previous_submission_id)
        if prior["project_id"] != project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found in this project")
        prior_findings = [f for f in reviews_db.list_findings(org_id, prior["submission_id"]) if f["status"] == "open"]

    try:
        submission = reviews_db.create_submission(
            org_id, project_id, calculation, user["user_id"], body.previous_submission_id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    # Carry forward open findings from the superseded submission so the
    # reviewer must explicitly decide (via the same close-finding action)
    # whether each is actually resolved by the new version — never
    # silently dropped.
    for f in prior_findings:
        reviews_db.create_finding(
            org_id, submission["submission_id"], f["author"], f["severity"], f["description"],
            f["requested_action"], f["requirement_id"], f["input_ref"], f["evidence_ref"],
            carried_from_finding_id=f["finding_id"],
        )
    return reviews_db.get_submission(org_id, submission["submission_id"])


@router.get("/projects/{project_id}/submissions")
def list_project_submissions(project_id: str, status_filter: str | None = None, reviewer_id: str | None = None,
                              user=Depends(get_current_user)):
    _require_project_access(user, project_id)
    statuses = [s.strip() for s in status_filter.split(",")] if status_filter else None
    rows = reviews_db.list_submissions(user["org_id"], project_id=project_id, reviewer_id=reviewer_id,
                                        status_filter=statuses)
    return _with_overdue(rows)


@router.get("/reviews/my")
def my_reviews(user=Depends(get_current_user)):
    """Every submission currently assigned to the caller, across projects."""
    return _with_overdue(reviews_db.list_submissions(user["org_id"], reviewer_id=user["user_id"]))


@router.get("/submissions/{submission_id}")
def get_submission_detail(submission_id: str, user=Depends(get_current_user)):
    submission = _owned_submission(user["org_id"], submission_id)
    _require_project_access(user, submission["project_id"])
    return {
        "submission": submission,
        "calculation": get_calculation(user["org_id"], submission["calculation_id"]),
        "findings": reviews_db.list_findings(user["org_id"], submission_id),
        "events": reviews_db.events(user["org_id"], submission_id),
        "assignment_history": reviews_db.assignment_history(user["org_id"], submission_id),
    }


@router.get("/submissions/{submission_id}/diff")
def get_submission_diff(submission_id: str, user=Depends(get_current_user)):
    submission = _owned_submission(user["org_id"], submission_id)
    _require_project_access(user, submission["project_id"])
    if submission["previous_submission_id"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This submission has no previous version to compare against")
    return reviews_db.diff_submissions(user["org_id"], submission_id, submission["previous_submission_id"])


@router.post("/submissions/{submission_id}/assign-reviewer")
def assign_reviewer(submission_id: str, body: AssignReviewerRequest, user=Depends(require_writer)):
    org_id = user["org_id"]
    submission = _owned_submission(org_id, submission_id)
    _require_project_lead(user, submission["project_id"])
    if body.reviewer_id is not None:
        # Phase 3 correction: assignment must NEVER silently grant project
        # membership. A reviewer must already be an authorized project
        # member — the reviewer picker defaults to that set (frontend),
        # and if someone new is genuinely needed, a project lead/admin
        # must explicitly add them via POST /projects/{id}/members first
        # (its own permission-controlled, audited action — see
        # src.projects.add_project_member's append-only event log).
        if projects_db.get_project_member(org_id, submission["project_id"], body.reviewer_id) is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "That user is not a member of this project. Add them as a project member first "
                "(POST /projects/{project_id}/members), then assign them as reviewer.",
            )
        if body.reviewer_id == submission["submitted_by"]:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The submitter cannot review their own submission")
    try:
        return reviews_db.assign_reviewer(org_id, submission_id, body.reviewer_id, user["user_id"], body.reason)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post("/submissions/{submission_id}/transition")
def transition(submission_id: str, body: TransitionRequest, user=Depends(require_writer)):
    org_id = user["org_id"]
    submission = _owned_submission(org_id, submission_id)

    if body.to_status == "withdrawn":
        if user["role"] != "admin" and user["user_id"] != submission["submitted_by"]:
            _require_project_lead(user, submission["project_id"])
    elif body.to_status == "in_review":
        _require_current_reviewer(user, submission)
    else:  # changes_requested, internally_approved, rejected
        _require_current_reviewer(user, submission)
        if body.to_status == "internally_approved" and submission["submitted_by"] == user["user_id"]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "The submitter cannot approve their own submission")

    notify_kind = notify_message = notify_user = None
    if body.to_status == "changes_requested":
        notify_kind, notify_message, notify_user = "changes_requested", "Changes were requested on your submission.", submission["submitted_by"]
    elif body.to_status in ("internally_approved", "rejected"):
        notify_kind = "decision"
        notify_message = f"Your submission was {body.to_status.replace('_', ' ')}."
        notify_user = submission["submitted_by"]

    try:
        return reviews_db.transition(
            org_id, submission_id, body.if_version, body.to_status, user["user_id"], body.reason,
            notify_user_id=notify_user, notify_kind=notify_kind, notify_message=notify_message,
        )
    except StaleSubmissionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post("/submissions/{submission_id}/findings", status_code=status.HTTP_201_CREATED)
def create_finding(submission_id: str, body: FindingCreate, user=Depends(require_writer)):
    org_id = user["org_id"]
    submission = _owned_submission(org_id, submission_id)
    role = _require_project_access(user, submission["project_id"])
    is_reviewer = submission["assigned_reviewer_id"] == user["user_id"]
    if user["role"] != "admin" and not is_reviewer and role not in ("lead", "contributor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to raise findings on this submission")
    try:
        return reviews_db.create_finding(
            org_id, submission_id, user["user_id"], body.severity, body.description, body.requested_action,
            body.requirement_id, body.input_ref, body.evidence_ref,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/submissions/{submission_id}/findings")
def list_findings(submission_id: str, user=Depends(get_current_user)):
    submission = _owned_submission(user["org_id"], submission_id)
    _require_project_access(user, submission["project_id"])
    return reviews_db.list_findings(user["org_id"], submission_id)


@router.post("/findings/{finding_id}/close")
def close_finding(finding_id: str, body: FindingClose, user=Depends(require_writer)):
    org_id = user["org_id"]
    finding = _owned_finding(org_id, finding_id)
    submission = _owned_submission(org_id, finding["submission_id"])
    _require_current_reviewer(user, submission)
    try:
        return reviews_db.close_finding(org_id, finding_id, user["user_id"], body.reason)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post("/findings/{finding_id}/comments", status_code=status.HTTP_201_CREATED)
def add_comment(finding_id: str, body: CommentCreate, user=Depends(require_writer)):
    org_id = user["org_id"]
    finding = _owned_finding(org_id, finding_id)
    submission = _owned_submission(org_id, finding["submission_id"])
    _require_project_access(user, submission["project_id"])
    return reviews_db.add_comment(org_id, finding_id, user["user_id"], body.body, body.is_proposed_resolution)


@router.get("/findings/{finding_id}/comments")
def list_comments(finding_id: str, user=Depends(get_current_user)):
    org_id = user["org_id"]
    finding = _owned_finding(org_id, finding_id)
    submission = _owned_submission(org_id, finding["submission_id"])
    _require_project_access(user, submission["project_id"])
    return reviews_db.list_comments(org_id, finding_id)


@router.get("/notifications")
def list_notifications(unread_only: bool = False, user=Depends(get_current_user)):
    return reviews_db.list_notifications(user["org_id"], user["user_id"], unread_only)


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: str, user=Depends(get_current_user)):
    ok = reviews_db.mark_notification_read(user["org_id"], user["user_id"], notification_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found or already read")
    return {"ok": True}
