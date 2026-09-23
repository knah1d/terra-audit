"""Evidence-linked calculations — Phase 2 (see src/calculations.py's
module docstring for the compatibility strategy with the existing
stateless preview/commit endpoints in backend/routers/carbon.py, which
are untouched by this router).
"""
from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.deps import get_current_user, get_owned_field, require_writer
from backend.schemas.calculations import (
    CalculationCommitRequest, CalculationContext, DeterminationRequest, EngineInputsAlm, EngineInputsRice,
    ReadinessRequest,
)
from src import calculations as calculations_db
from src import methodology_registry as registry
from src import projects as projects_db
from src import readiness as readiness_engine
from src.calculations import PATHWAYS
from src.database import get_credit_history
from src.issuance import result_is_issuable
from src.snapshot import build_snapshot, calculate_from_snapshot

router = APIRouter(tags=["calculations"])
_field = get_owned_field()


def _validate_pathway(field: dict, accounting_pathway: str) -> None:
    expected = PATHWAYS.get(field["field_type"])
    if accounting_pathway != expected:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Field type '{field['field_type']}' uses pathway '{expected}', not '{accounting_pathway}'. "
            "The accounting pathway is never inferred — select the one matching this field's methodology.",
        )


def _validate_engine_inputs(accounting_pathway: str, raw: dict) -> dict:
    try:
        if accounting_pathway == "vm0051_rice_awd":
            return EngineInputsRice(**raw).model_dump(mode="json")
        return EngineInputsAlm(**raw).model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid engine_inputs: {exc}") from exc


def _validate_project(org_id: str, project_id: str | None) -> None:
    if project_id is not None and projects_db.get_project(org_id, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")


@router.post("/fields/{field_id}/calculations/readiness")
def get_readiness(field_id: str, body: ReadinessRequest, user=Depends(get_current_user), field=Depends(_field)):
    """Automated completeness checklist only — no engine result, so
    result-derived checks (QA3 gate, leakage) read as 'needs_review: run
    a preview' rather than silently guessing an outcome."""
    _validate_pathway(field, body.accounting_pathway)
    _validate_project(user["org_id"], body.project_id)
    checklist, bundle_id = readiness_engine.build_readiness_checklist(
        user["org_id"], field, body.accounting_pathway, body.season_ids,
        body.monitoring_period_start.isoformat(), body.monitoring_period_end.isoformat(),
        engine_inputs={}, preview_result=None, project_id=body.project_id,
    )
    return {"checklist": checklist, "bundle_id": bundle_id}


@router.post("/fields/{field_id}/calculations/preview")
def preview_calculation(field_id: str, body: CalculationContext, user=Depends(get_current_user), field=Depends(_field)):
    """Exploratory estimate — computes a result and the FULL checklist
    (including result-derived checks) but persists nothing, exactly like
    the legacy /carbon-credits/preview endpoint's no-write contract."""
    org_id = user["org_id"]
    _validate_pathway(field, body.accounting_pathway)
    _validate_project(org_id, body.project_id)
    engine_inputs = _validate_engine_inputs(body.accounting_pathway, body.engine_inputs)
    try:
        snapshot = build_snapshot(
            org_id, field, body.project_id, body.accounting_pathway, body.season_ids,
            body.monitoring_period_start.isoformat(), body.monitoring_period_end.isoformat(),
            engine_inputs, monitoring_run_ids=[], attachment_ids=[],
        )
        result = calculate_from_snapshot(snapshot)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    checklist, bundle_id = readiness_engine.build_readiness_checklist(
        org_id, field, body.accounting_pathway, body.season_ids,
        body.monitoring_period_start.isoformat(), body.monitoring_period_end.isoformat(),
        engine_inputs, preview_result=result, project_id=body.project_id,
    )
    return {"result": result, "readiness": checklist, "bundle_id": bundle_id}


@router.post("/fields/{field_id}/calculations", status_code=status.HTTP_201_CREATED)
def commit_calculation(
    field_id: str, body: CalculationCommitRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user=Depends(require_writer), field=Depends(_field),
):
    """Freezes evidence into an immutable snapshot and persists one
    calculation version. Never becomes 'ready_for_review' while a
    blocking readiness item remains (src.calculations._is_blocking) —
    the caller cannot override this by asking nicely."""
    org_id = user["org_id"]
    _validate_pathway(field, body.accounting_pathway)
    _validate_project(org_id, body.project_id)
    engine_inputs = _validate_engine_inputs(body.accounting_pathway, body.engine_inputs)

    if body.supersedes_calculation_id is not None:
        prior = calculations_db.get_calculation(org_id, body.supersedes_calculation_id)
        if prior is None or prior["field_id"] != field_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Calculation to supersede not found on this field")

    try:
        snapshot = build_snapshot(
            org_id, field, body.project_id, body.accounting_pathway, body.season_ids,
            body.monitoring_period_start.isoformat(), body.monitoring_period_end.isoformat(),
            engine_inputs, body.monitoring_run_ids, body.attachment_ids,
        )
        result = calculate_from_snapshot(snapshot)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    issuable, block_reason = result_is_issuable(result, body.accounting_pathway)
    if not issuable:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, block_reason)

    checklist, bundle_id = readiness_engine.build_readiness_checklist(
        org_id, field, body.accounting_pathway, body.season_ids,
        body.monitoring_period_start.isoformat(), body.monitoring_period_end.isoformat(),
        engine_inputs, preview_result=result, project_id=body.project_id,
    )

    outcome = calculations_db.commit_calculation(
        org_id, field_id, idempotency_key, snapshot, engine_inputs, result, checklist,
        field["field_type"], body.accounting_pathway, body.project_id,
        body.monitoring_period_start.isoformat(), body.monitoring_period_end.isoformat(),
        body.season_ids, body.attachment_ids, user["user_id"], body.supersedes_calculation_id,
        bundle_id=bundle_id,
    )
    return outcome


@router.get("/fields/{field_id}/calculations")
def list_field_calculations(
    field_id: str, latest_only: bool = False, include_legacy: bool = True,
    user=Depends(get_current_user), field=Depends(_field),
):
    """Merges Phase-2 evidence-linked calculations with legacy
    credit_history rows into one timeline, each row explicitly tagged
    legacy/has_snapshot — never presenting a pre-Phase-2 commit as if it
    had a snapshot it doesn't have."""
    org_id = user["org_id"]
    rows = [{**c, "legacy": False, "has_snapshot": True}
            for c in calculations_db.list_calculations(org_id, field_id=field_id, latest_only=latest_only)]
    if include_legacy:
        rows += [{
            "legacy": True, "has_snapshot": False, "calculation_id": None,
            "credit_history_id": h["credit_history_id"], "created_at": h["calculated_at"],
            "final_issuance": h["final_issuance"], "inputs": h["inputs"], "result": h["result"],
        } for h in get_credit_history(org_id, field_id)]
    rows.sort(key=lambda r: str(r["created_at"]), reverse=True)
    return rows


@router.get("/calculations/{calculation_id}")
def get_calculation(calculation_id: str, user=Depends(get_current_user)):
    calc = calculations_db.get_calculation(user["org_id"], calculation_id)
    if calc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calculation not found")
    return calc


@router.get("/calculations/{calculation_id}/chain")
def get_calculation_chain(calculation_id: str, user=Depends(get_current_user)):
    """Every version linked to this one, oldest first — lets a viewer see
    a superseded calculation's corrections without losing the original."""
    org_id = user["org_id"]
    anchor = calculations_db.get_calculation(org_id, calculation_id)
    if anchor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calculation not found")
    chain = [c for c in calculations_db.list_calculations(org_id, field_id=anchor["field_id"])
             if c["chain_id"] == anchor["chain_id"]]
    return sorted(chain, key=lambda c: c["version"])


@router.get("/fields/{field_id}/calculations/readiness/determinations")
def get_determinations(
    field_id: str, accounting_pathway: str, monitoring_period_start: str, monitoring_period_end: str,
    season_ids: str, project_id: str | None = None, user=Depends(get_current_user), field=Depends(_field),
):
    """`season_ids` is a comma-separated list — needed (not just the
    bundle/dates) to recompute the same evidence fingerprint a
    determination was scoped against; see src.readiness.
    compute_evidence_fingerprint."""
    bundle = registry.resolve_bundle_for_project(user["org_id"], project_id, accounting_pathway)
    sids = [s for s in season_ids.split(",") if s]
    fingerprint = readiness_engine.compute_evidence_fingerprint(user["org_id"], field_id, accounting_pathway, sids)
    return calculations_db.latest_determinations(
        user["org_id"], field_id, accounting_pathway, bundle["bundle_id"] if bundle else None,
        monitoring_period_start, monitoring_period_end, fingerprint,
    )


@router.post("/fields/{field_id}/calculations/readiness/determinations", status_code=status.HTTP_201_CREATED)
def record_determination(
    field_id: str, body: DeterminationRequest, user=Depends(require_writer), field=Depends(_field),
):
    """Manual determinations (e.g. an expert additionality call) always
    require an actor and a reason — enforced by DeterminationRequest's
    required `reason` field, never accepted as a bare status flip.
    Scoped to the resolved methodology bundle, the exact reporting
    period, AND the current evidence fingerprint over `season_ids`;
    restricted to reviewable requirements (raises 422 via the existing
    ValueError handler for anything unsupported/automated_only — see
    src.calculations.record_determination)."""
    bundle = registry.resolve_bundle_for_project(user["org_id"], body.project_id, body.accounting_pathway)
    fingerprint = readiness_engine.compute_evidence_fingerprint(
        user["org_id"], field_id, body.accounting_pathway, body.season_ids,
    )
    return calculations_db.record_determination(
        user["org_id"], field_id, body.accounting_pathway, body.requirement_id,
        bundle["bundle_id"] if bundle else None,
        body.monitoring_period_start.isoformat(), body.monitoring_period_end.isoformat(),
        fingerprint, body.status, body.reason, user["user_id"],
    )
