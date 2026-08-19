from fastapi import APIRouter, Depends, HTTPException, status

from backend.deps import get_current_user, get_owned_field, require_writer
from backend.schemas.alm import (
    CompletenessOut, LivestockScheduleIn, LivestockScheduleOut,
    PracticeScheduleIn, PracticeScheduleOut, SocMeasurementsOut, SocValuesIn,
)
from src.database import (
    get_alm_livestock_schedule, get_alm_practice_schedule,
    get_soc_measurements, save_alm_livestock_schedule, save_alm_practice_schedule,
    save_soc_measurements,
)
from src.field_types.alm_vm0042 import AlmPracticeValidator

router = APIRouter(tags=["alm-practice-data"])

_SCENARIOS = {"baseline", "project"}
_SITE_TYPES = {"project", "control"}
_TIMEPOINTS = {"t_start", "t_final"}


# Every endpoint in this router is VM0042-specific: it reads or writes
# alm_practice_schedule / alm_livestock_schedule / soc_measurements rows.
# It previously only checked that the field existed and belonged to the
# caller's org, so PUT .../practice-schedule/baseline against a rice_awd
# field wrote ALM rows onto it. expect_type makes that a 422.
_alm_field = get_owned_field(expect_type="cropland_alm_vm0042")


@router.get("/fields/{field_id}/practice-schedule", response_model=PracticeScheduleOut)
def get_practice_schedule(
    field_id: str, user: dict = Depends(get_current_user), field: dict = Depends(_alm_field)
):
    return PracticeScheduleOut(**get_alm_practice_schedule(user["org_id"], field_id))


@router.put("/fields/{field_id}/practice-schedule/{scenario}", response_model=PracticeScheduleOut)
def put_practice_schedule(
    field_id: str, scenario: str, body: PracticeScheduleIn,
    user: dict = Depends(require_writer), field: dict = Depends(_alm_field),
):
    if scenario not in _SCENARIOS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"scenario must be one of {_SCENARIOS}")
    save_alm_practice_schedule(user["org_id"], field_id, scenario, body.model_dump())
    return PracticeScheduleOut(**get_alm_practice_schedule(user["org_id"], field_id))


@router.get("/fields/{field_id}/livestock", response_model=LivestockScheduleOut)
def get_livestock(
    field_id: str, user: dict = Depends(get_current_user), field: dict = Depends(_alm_field)
):
    return LivestockScheduleOut(**get_alm_livestock_schedule(user["org_id"], field_id))


@router.put("/fields/{field_id}/livestock/{scenario}", response_model=LivestockScheduleOut)
def put_livestock(
    field_id: str, scenario: str, body: LivestockScheduleIn,
    user: dict = Depends(require_writer), field: dict = Depends(_alm_field),
):
    if scenario not in _SCENARIOS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"scenario must be one of {_SCENARIOS}")
    save_alm_livestock_schedule(
        user["org_id"], field_id, scenario, [e.model_dump() for e in body.entries]
    )
    return LivestockScheduleOut(**get_alm_livestock_schedule(user["org_id"], field_id))


@router.get("/fields/{field_id}/soc-measurements", response_model=SocMeasurementsOut)
def get_soc(
    field_id: str, user: dict = Depends(get_current_user), field: dict = Depends(_alm_field)
):
    raw = get_soc_measurements(user["org_id"], field_id)
    # Tuple keys -> "{site_type}_{timepoint}", matching report_generator.py's
    # own JSON-export stringification convention.
    return SocMeasurementsOut(**{f"{site}_{tp}": vals for (site, tp), vals in raw.items()})


@router.put("/fields/{field_id}/soc-measurements/{site_type}/{timepoint}", response_model=SocMeasurementsOut)
def put_soc(
    field_id: str, site_type: str, timepoint: str, body: SocValuesIn,
    user: dict = Depends(require_writer), field: dict = Depends(_alm_field),
):
    if site_type not in _SITE_TYPES or timepoint not in _TIMEPOINTS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"site_type must be one of {_SITE_TYPES}, timepoint one of {_TIMEPOINTS}",
        )
    save_soc_measurements(user["org_id"], field_id, site_type, timepoint, body.values)
    raw = get_soc_measurements(user["org_id"], field_id)
    return SocMeasurementsOut(**{f"{site}_{tp}": vals for (site, tp), vals in raw.items()})


@router.get("/fields/{field_id}/completeness", response_model=CompletenessOut)
def get_completeness(
    field_id: str, user: dict = Depends(get_current_user), field: dict = Depends(_alm_field)
):
    org_id = user["org_id"]
    practice_schedule = get_alm_practice_schedule(org_id, field_id)
    soc_measurements = get_soc_measurements(org_id, field_id)
    problems = AlmPracticeValidator().check_completeness(practice_schedule, soc_measurements)
    return CompletenessOut(ready=not problems, problems=problems)
