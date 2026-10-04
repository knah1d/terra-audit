"""Server-owned next actions; models cannot invent required records or reviews."""


def action_for(row):
    status = row.get("status")
    if status not in {"missing", "needs_review", "unsupported"}:
        return None
    fix = row.get("fix", {})
    if status == "needs_review":
        kind, label = "review", "Review evidence"
        message = "Reviewer confirmation is outstanding for this requirement."
    elif status == "unsupported":
        kind, label = "implementation", "View requirement"
        message = "This requirement needs expert assessment because this implementation does not support it."
    else:
        kind, label = "evidence", "Add evidence"
        message = "Provide the evidence identified as missing by the readiness checklist."
    reason = row.get("explanation") or row.get("required_evidence") or ""
    # The engine's reason is reproduced, not inferred or rewritten by an LLM.
    return {"requirement_id": row["requirement_id"], "record_type": fix.get("record_type", "expert_review"),
            "action_kind": kind, "readiness_status": status,
            "explanation": message + (" " + str(reason) if reason else ""),
            "route": fix.get("route"), "fix_available": fix.get("fix_available", False),
            "link_label": label}
