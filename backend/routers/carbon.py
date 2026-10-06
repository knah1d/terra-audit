from fastapi import APIRouter, Depends, Header

from backend.deps import get_current_user, get_owned_field, require_writer
from backend.schemas.carbon import (
    CarbonCalcRequestAlm, CarbonCalcRequestRice, CommitResponse,
    CreditHistoryEntry, CarbonResultOut,
)
from src.persistence.database import (
    commit_carbon_credit_result, get_alm_cumulative_delta, get_alm_livestock_schedule,
    get_alm_practice_schedule, get_credit_history, get_soc_measurements,
)
from src.field_types.registry import build_methodology

_field = get_owned_field()

router = APIRouter(tags=["carbon-credits"])


def _calculate(org_id: str, field_id: str, field: dict, body: dict) -> dict:
    """Shared by preview and commit — dispatches on the field's own stored
    (immutable) field_type via build_methodology(), exactly mirroring how
    app.py resolves carbon_engine = build_methodology(selected_field_type).
    """
    engine = build_methodology(field["field_type"])
    if field["field_type"] == "rice_awd":
        req = CarbonCalcRequestRice(**body)
        return engine.calculate_credits(
            awd_events=req.awd_events,
            season_length_days=req.season_length_days,
            area_ha=req.area_ha,
            q_n_kg_per_ha=req.q_n_kg_per_ha,
            preseason_category=req.preseason_category,
            baseline_amendments=req.baseline_amendments,
            project_amendments=req.project_amendments,
        )
    else:
        req = CarbonCalcRequestAlm(**body)
        practice_schedule = get_alm_practice_schedule(org_id, field_id)
        soc_measurements = get_soc_measurements(org_id, field_id)
        livestock_schedule = get_alm_livestock_schedule(org_id, field_id)
        prior_cumulative = get_alm_cumulative_delta(org_id, field_id)
        return engine.calculate_credits(
            practice_schedule=practice_schedule,
            soc_measurements=soc_measurements,
            area_ha=req.area_ha,
            verification_years=req.verification_years,
            non_permanence_risk_pct=req.non_permanence_risk_pct,
            prior_cumulative_delta_co2_wp_t=prior_cumulative,
            baseline_livestock=livestock_schedule.get("baseline"),
            project_livestock=livestock_schedule.get("project"),
        )


@router.post("/fields/{field_id}/carbon-credits/preview", response_model=CarbonResultOut)
def preview_carbon_credits(
    field_id: str, body: dict, user: dict = Depends(get_current_user),
    field: dict = Depends(_field),
):
    """Any authenticated role (including viewer) — no DB write. Mirrors
    app.py's behavior where a viewer can still see a computed result;
    only *persisting* it (commit, below) is role-gated."""
    org_id = user["org_id"]
    result = _calculate(org_id, field_id, field, body)
    return CarbonResultOut(**result)


@router.post("/fields/{field_id}/carbon-credits/commit", response_model=CommitResponse)
def commit_carbon_credits(
    field_id: str, body: dict,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: dict = Depends(require_writer), field: dict = Depends(_field),
):
    """RETIRED for every field_type — src.persistence.database.
    commit_carbon_credit_result always refuses to write (see its
    docstring: a client-supplied, un-frozen area_ha could otherwise
    determine recorded credits). Kept as a real endpoint, not deleted,
    so `Idempotency-Key` is still required/validated and a caller gets
    the SAME clean 422 shape (via NonIssuableResultError's global
    exception handler in backend/main.py) that the old per-methodology
    gate used to return for a blocked result — never a 404 or a 500.
    No calculation is run here; retirement doesn't depend on or expose
    what the client's body would have computed to.
    Use POST /fields/{field_id}/calculations instead."""
    commit_carbon_credit_result(
        user["org_id"], field_id, idempotency_key, field["field_type"], body, {},
    )
    raise AssertionError("unreachable — commit_carbon_credit_result always raises")


@router.get("/fields/{field_id}/credit-history", response_model=list[CreditHistoryEntry])
def credit_history(
    field_id: str, user: dict = Depends(get_current_user), field: dict = Depends(_field)
):
    org_id = user["org_id"]
    return [CreditHistoryEntry(**row) for row in get_credit_history(org_id, field_id)]
