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


def result_is_issuable(result: dict, accounting_pathway: str | None = None) -> tuple[bool, str | None]:
    """Returns (True, None) if this calculate_credits() result may be
    persisted, else (False, human-readable reason).

    `accounting_pathway` is optional ONLY for backward compatibility with
    call sites that predate it (see backend/routers/carbon.py's legacy
    /carbon-credits/commit endpoint, explicitly preserved unchanged) — a
    caller that omits it keeps the original lenient behavior (missing
    flags default to issuable). Passing it applies the tightened,
    unified gate docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md Phase 1
    gap #3 calls for: "src/issuance.py allows missing compatibility
    flags by default... require new claim-ready results to pass a common
    explicit gate across every calculation entry point."

    IMPORTANT: the two engines do NOT share one flag-naming convention —
    AlmCarbonEngine only sets `production_decline_leakage_blocked` on its
    BLOCKING path (it's simply absent, not False, when leakage is clean;
    see src/carbon_calculator_alm.py's calculate_credits()), so a
    "the flag key must be present" rule would incorrectly reject every
    successful ALM calculation. Both engines DO consistently agree on
    one thing: `final_issuance` is a real number when not blocked and
    explicitly None when blocked (verified in both
    src/carbon_calculator.py and src/carbon_calculator_alm.py) — that is
    the actual common, engine-agnostic signal used here, rather than
    inventing a shared flag name neither engine implements. This never
    touches historical credit_history rows, since this function is only
    ever called at COMMIT time, never when reading history back.
    """
    if result.get("qa3_pathway_valid") is False:
        return False, result.get("qa3_block_reason") or "VM0051 QA3 pathway not valid"
    if result.get("production_decline_leakage_blocked"):
        return False, (
            result.get("leakage_block_reason")
            or "VM0042 production-decline leakage blocked"
        )
    if accounting_pathway is not None and result.get("final_issuance") is None:
        return False, "Calculation result has no final_issuance value — cannot confirm issuability."
    return True, None
