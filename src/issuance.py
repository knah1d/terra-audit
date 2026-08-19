"""
Single source of truth for whether a calculate_credits() result may be
persisted as an issuance record.

This exists because the rule was previously implemented once per client
and the two implementations diverged: app.py wrote credit_history BEFORE
checking VM0051's QA3 project-size gate (so a project that failed the
gate still left an issuance record behind), while
backend/routers/carbon.py checked first. Both clients write to the same
database, so "which rows count as issued credits" depended on which UI
you happened to use.

Rather than fix the ordering in one place and hope, the check is now
enforced inside src.database.commit_carbon_credit_result — the single
write path — so a non-issuable result cannot be persisted no matter
which caller asks or in what order they check. Callers should still
gate first to show the user a useful message; this is the backstop that
makes the invariant structural.

Covers both methodologies' block flags:
  - VM0051 (CarbonAssetEngine): qa3_pathway_valid=False when the project
    exceeds the 60,000 tCO2e/yr gate the flat 15% uncertainty deduction
    is only valid at or below (§8.6.3).
  - VM0042 (AlmCarbonEngine): production_decline_leakage_blocked=True
    when genuine yield decline is detected, since VMD0054 Steps 3-5
    (new-land carbon-stock accounting) are not implemented and the
    engine blocks rather than fabricating a number (§8.4.3).
"""


class NonIssuableResultError(ValueError):
    """Raised when a caller tries to persist a blocked calculation.

    Subclasses ValueError so existing `except ValueError` handlers (and
    FastAPI routers translating ValueError to 4xx) keep working.
    """


def result_is_issuable(result: dict) -> tuple[bool, str | None]:
    """Returns (True, None) if this calculate_credits() result may be
    persisted, else (False, human-readable reason).

    Unknown/missing flags default to issuable: both engines set their
    block flag explicitly on the blocking path, and a result dict that
    predates a flag (or comes from a third methodology that has no such
    gate) must not be silently rejected.
    """
    if result.get("qa3_pathway_valid") is False:
        return False, result.get("qa3_block_reason") or "VM0051 QA3 pathway not valid"
    if result.get("production_decline_leakage_blocked"):
        return False, (
            result.get("leakage_block_reason")
            or "VM0042 production-decline leakage blocked"
        )
    return True, None
