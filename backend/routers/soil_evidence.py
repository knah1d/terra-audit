"""Traceable soil evidence — sampling plans, strata, and geolocated
samples. See src/soil_evidence.py's module docstring for how this
relates to (and deliberately does not replace) the existing aggregate
soc_measurements the calculation engine actually reads.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from backend.deps import get_current_user, get_owned_field, require_writer
from backend.schemas.soil_evidence import SamplingPlanCreate, SampleCreate, StratumCreate
from src import soil_evidence

router = APIRouter(tags=["soil-evidence"])
_alm_field = get_owned_field(expect_type="cropland_alm_vm0042")


@router.get("/fields/{field_id}/soil-sampling-plans")
def list_plans(field_id: str, user=Depends(get_current_user), field=Depends(_alm_field)):
    return soil_evidence.list_plans(user["org_id"], field_id)


@router.post("/fields/{field_id}/soil-sampling-plans", status_code=status.HTTP_201_CREATED)
def create_plan(field_id: str, body: SamplingPlanCreate, user=Depends(require_writer), field=Depends(_alm_field)):
    try:
        plan_id = soil_evidence.create_plan(
            user["org_id"], field_id, body.name, body.description, body.measurement_method,
            body.remeasurement_interval_years, user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return soil_evidence.get_plan(user["org_id"], plan_id)


def _owned_plan(org_id: str, field_id: str, plan_id: str) -> dict:
    plan = soil_evidence.get_plan(org_id, plan_id)
    if plan is None or plan["field_id"] != field_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sampling plan not found on this field")
    return plan


@router.get("/fields/{field_id}/soil-sampling-plans/{plan_id}/strata")
def list_strata(field_id: str, plan_id: str, user=Depends(get_current_user), field=Depends(_alm_field)):
    _owned_plan(user["org_id"], field_id, plan_id)
    return soil_evidence.list_strata(user["org_id"], plan_id)


@router.post("/fields/{field_id}/soil-sampling-plans/{plan_id}/strata", status_code=status.HTTP_201_CREATED)
def create_stratum(field_id: str, plan_id: str, body: StratumCreate,
                    user=Depends(require_writer), field=Depends(_alm_field)):
    _owned_plan(user["org_id"], field_id, plan_id)
    try:
        stratum_id = soil_evidence.create_stratum(user["org_id"], plan_id, body.name, body.description, body.area_ha)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return next(s for s in soil_evidence.list_strata(user["org_id"], plan_id) if s["stratum_id"] == stratum_id)


@router.get("/fields/{field_id}/soil-sampling-plans/{plan_id}/samples")
def list_samples(field_id: str, plan_id: str, user=Depends(get_current_user), field=Depends(_alm_field)):
    _owned_plan(user["org_id"], field_id, plan_id)
    return soil_evidence.list_samples(user["org_id"], plan_id)


@router.post("/fields/{field_id}/soil-sampling-plans/{plan_id}/samples", status_code=status.HTTP_201_CREATED)
def create_sample(field_id: str, plan_id: str, body: SampleCreate,
                   user=Depends(require_writer), field=Depends(_alm_field)):
    _owned_plan(user["org_id"], field_id, plan_id)
    try:
        sample_id = soil_evidence.create_sample(
            user["org_id"], plan_id, field_id, body.stratum_id, body.site_type, body.timepoint,
            body.sample_date.isoformat(), body.depth_top_cm, body.depth_bottom_cm, body.latitude, body.longitude,
            body.bulk_density_g_cm3, body.soc_percent, body.soc_value_tco2e_ha, body.lab_name, body.lab_method,
            body.chain_of_custody_ref, body.notes, user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return next(s for s in soil_evidence.list_samples(user["org_id"], plan_id) if s["sample_id"] == sample_id)


@router.get("/fields/{field_id}/soil-samples/aggregate-comparison")
def get_aggregate_comparison(field_id: str, user=Depends(get_current_user), field=Depends(_alm_field)):
    """Cross-check only — compares granular sample-derived aggregates
    against the manually entered soc_measurements the engine actually
    used. Never a substitute input for a calculation."""
    from src.database import get_soc_measurements
    org_id = user["org_id"]
    engine_input = {f"{s}_{t}": v for (s, t), v in get_soc_measurements(org_id, field_id).items()}
    from_samples = {f"{s}_{t}": v for (s, t), v in soil_evidence.aggregate_from_samples(org_id, field_id).items()}
    return {"engine_input_soc_measurements": engine_input, "derived_from_soil_samples": from_samples,
            "note": "derived_from_soil_samples is a comparison view only — it is not what the calculation engine used."}
