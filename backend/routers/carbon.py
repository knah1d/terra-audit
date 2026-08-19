from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.deps import get_current_user, require_writer
from backend.schemas.carbon import (
    CarbonCalcRequestAlm, CarbonCalcRequestRice, CommitResponse,
    CreditHistoryEntry, CarbonResultOut,
)
from src.database import (
    commit_carbon_credit_result, get_alm_cumulative_delta, get_alm_livestock_schedule,
    get_alm_practice_schedule, get_credit_history, get_field, get_soc_measurements,
)
from src.field_types.registry import build_methodology

router = APIRouter(tags=["carbon-credits"])


def _require_field(org_id: str, field_id: str) -> dict:
    field = get_field(org_id, field_id)
    if field is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    return field


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
def preview_carbon_credits(field_id: str, body: dict, user: dict = Depends(get_current_user)):
    """Any authenticated role (including viewer) — no DB write. Mirrors
    app.py's behavior where a viewer can still see a computed result;
    only *persisting* it (commit, below) is role-gated."""
    org_id = user["org_id"]
    field = _require_field(org_id, field_id)
    result = _calculate(org_id, field_id, field, body)
    return CarbonResultOut(**result)


@router.post("/fields/{field_id}/carbon-credits/commit", response_model=CommitResponse)
def commit_carbon_credits(
    field_id: str, body: dict,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: dict = Depends(require_writer),
):
    """Writer-only. Requires an Idempotency-Key header — a retried request
    with the same key returns the original result instead of re-computing
    and double-accruing the ALM cumulative delta (src.database.
    commit_carbon_credit_result handles the atomicity)."""
    org_id = user["org_id"]
    field = _require_field(org_id, field_id)
    field_type = field["field_type"]
    result = _calculate(org_id, field_id, field, body)

    if field_type == "rice_awd":
        if not result.get("qa3_pathway_valid", True):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, result.get("qa3_block_reason"))
        new_cumulative_delta = None
    else:
        if result.get("production_decline_leakage_blocked"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, result.get("leakage_block_reason"))
        new_cumulative_delta = result["cumulative_delta_co2_wp"]

    outcome = commit_carbon_credit_result(
        org_id, field_id, idempotency_key, field_type, body, result, new_cumulative_delta,
    )
    return CommitResponse(**outcome)


@router.get("/fields/{field_id}/credit-history", response_model=list[CreditHistoryEntry])
def credit_history(field_id: str, user: dict = Depends(get_current_user)):
    org_id = user["org_id"]
    _require_field(org_id, field_id)
    return [CreditHistoryEntry(**row) for row in get_credit_history(org_id, field_id)]
