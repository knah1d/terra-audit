"""Commodity-level, multi-year production records feeding VMD0054 Step 1
(see src/evidence/production.py's module docstring). ALM-only, mirroring
backend/routers/soil_evidence.py's field-type gating.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from backend.deps import get_current_user, get_owned_field, require_writer
from backend.schemas.production_records import ProductionRecordCreate, ProductionRecordsImport, Vmd0054LeakageRequest, LeakageAssessmentSave
from src.evidence import production as production_records

router = APIRouter(tags=["production-records"])
_alm_field = get_owned_field(expect_type="cropland_alm_vm0042")


@router.get("/fields/{field_id}/production-records")
def list_records(field_id: str, period_type: str | None = None,
                  user=Depends(get_current_user), field=Depends(_alm_field)):
    return production_records.list_production_records(user["org_id"], field_id, period_type)


@router.post("/fields/{field_id}/production-records", status_code=status.HTTP_201_CREATED)
def create_record(field_id: str, body: ProductionRecordCreate,
                   user=Depends(require_writer), field=Depends(_alm_field)):
    try:
        record_id = production_records.create_production_record(
            user["org_id"], field_id, body.commodity, body.period_type, body.period_label,
            body.crop_cycle_index, body.harvest_start_date.isoformat() if body.harvest_start_date else None,
            body.harvest_end_date.isoformat() if body.harvest_end_date else None, body.harvested_area_ha,
            body.area_share_pct, body.production_status, body.production_quantity, body.unit,
            body.evidence_ref, body.notes, user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return next(r for r in production_records.list_production_records(user["org_id"], field_id)
                if r["record_id"] == record_id)


@router.post("/fields/{field_id}/production-records/import", status_code=status.HTTP_201_CREATED)
def import_records(field_id: str, body: ProductionRecordsImport,
                    user=Depends(require_writer), field=Depends(_alm_field)):
    payload = []
    for r in body.records:
        payload.append({
            "commodity": r.commodity, "period_type": r.period_type, "period_label": r.period_label,
            "crop_cycle_index": r.crop_cycle_index,
            "harvest_start_date": r.harvest_start_date.isoformat() if r.harvest_start_date else None,
            "harvest_end_date": r.harvest_end_date.isoformat() if r.harvest_end_date else None,
            "harvested_area_ha": r.harvested_area_ha, "area_share_pct": r.area_share_pct,
            "production_status": r.production_status, "production_quantity": r.production_quantity,
            "unit": r.unit, "evidence_ref": r.evidence_ref, "notes": r.notes,
        })
    outcome = production_records.import_production_records(user["org_id"], field_id, payload, user["user_id"])
    if outcome["error"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Import stopped after {len(outcome['created'])} row(s): {outcome['error']}",
        )
    return {"created": outcome["created"]}


@router.get("/fields/{field_id}/production-records/summary")
def get_summary(field_id: str, user=Depends(get_current_user), field=Depends(_alm_field)):
    """Grouped {commodity: {period_type: [records]}} view — what
    src.carbon.leakage_vmd0054's Step 1 branching reads."""
    return production_records.production_summary(user["org_id"], field_id)


@router.post("/fields/{field_id}/production-records/vmd0054-leakage")
def compute_vmd0054_leakage(field_id: str, body: Vmd0054LeakageRequest,
                             user=Depends(get_current_user), field=Depends(_alm_field)):
    """Steps 1/3/4/5 of VMD0054 v1.1 (src.carbon.leakage_vmd0054) computed
    against this field's recorded production_records. Read-only —
    exploratory, mirroring the calculation preview endpoints' no-write
    contract. Always reports per-commodity Step 1/3 results even where
    the field total is blocked at Step 4/5 for missing regional data."""
    from src.carbon.leakage_vmd0054 import compute_vmd0054_leakage as _compute
    commodity_params = {
        commodity: params.model_dump() for commodity, params in body.commodity_params.items()
    }
    new_land_params = body.new_land_carbon_stock_params.model_dump() if body.new_land_carbon_stock_params else None
    return _compute(
        user["org_id"], field_id, body.accounting_mode, body.years_elapsed, commodity_params, new_land_params,
    )


@router.get("/fields/{field_id}/production-records/leakage-assessments")
def leakage_assessments(field_id: str, user=Depends(get_current_user), field=Depends(_alm_field)):
    return production_records.list_leakage_assessments(user["org_id"], field_id)


@router.post("/fields/{field_id}/production-records/leakage-assessments", status_code=201)
def save_leakage_assessment(field_id: str, body: LeakageAssessmentSave,
                            user=Depends(require_writer), field=Depends(_alm_field)):
    from src.methodology import registry as methodology_registry
    from src.projects import repository as projects
    from backend.access import require_project_access
    role = require_project_access(user["org_id"], body.project_id, user)
    if role == "viewer":
        raise HTTPException(403, "Project viewers cannot save leakage assessments")
    project = projects.get_project(user["org_id"], body.project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    memberships = projects.list_project_fields(user["org_id"], body.project_id)
    if not any(m["field_id"] == field_id and not m.get("removed_at") for m in memberships):
        raise HTTPException(422, "Assign this field to the selected project first.")
    bundle = methodology_registry.resolve_bundle_for_project(user["org_id"], body.project_id, "vm0042_alm")
    if not bundle or bundle["bundle_id"] != body.bundle_id:
        raise HTTPException(422, "Select the project's applicable methodology bundle.")
    saved = production_records.save_leakage_assessment(user["org_id"], field_id, body.model_dump(mode="json"), user["user_id"])
    from src.carbon.leakage_vmd0054 import calculate_frozen_leakage
    evidence = {"assessment": saved, "production_records": production_records.list_production_records(user["org_id"], field_id),
                "project_fields": memberships}
    from src.carbon.leakage_vmd0054 import _whole_years
    try:
        years = _whole_years(body.monitoring_period_start.isoformat(), body.monitoring_period_end.isoformat())
    except ValueError:
        years = 0  # calculator returns the explicit unsupported-period reason
    result = calculate_frozen_leakage(evidence, bundle,
        {"start": body.monitoring_period_start.isoformat(), "end": body.monitoring_period_end.isoformat()}, years)
    return {"assessment": saved, "result": result}
