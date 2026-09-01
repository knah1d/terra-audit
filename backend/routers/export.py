from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.deps import get_current_user, get_owned_field
from src.database import (
    get_alm_livestock_schedule, get_alm_practice_schedule,
    get_credit_history_entry, get_latest_signal_result, get_soc_measurements,
)
from src.report_generator import (
    generate_audit_json, generate_audit_json_alm, generate_alm_data_csv,
    generate_pdf, generate_pdf_alm, generate_timeseries_csv,
)
import pandas as pd

router = APIRouter(tags=["export"])

_field = get_owned_field()


def _owned_verification(field_id: str, verification_id: int, org_id: str) -> dict:
    """Org+field-scoped lookup of a committed verification by its stable
    id. 404s (not 403s) on missing/wrong-org/wrong-field ids, matching the
    get_owned_field pattern's don't-reveal-existence philosophy."""
    entry = get_credit_history_entry(org_id, field_id, verification_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Verification record not found")
    return entry


def _rice_signal_for_report(org_id: str, field_id: str):
    """Best-effort current signal context — NOT provenance-linked to any
    specific committed verification (no schema link exists between a
    credit_history row and the signal_run job that produced its inputs)."""
    signal = get_latest_signal_result(org_id, field_id)
    if signal is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No signal-analytics run recorded for this field yet")
    signal_for_report = {
        "n_observations": signal["n_observations"], "vv_mean": signal["vv_mean"],
        "vv_std": signal["vv_std"], "awd_events": signal["total_awd"],
        "awd_dates": signal["awd_dates"], "sowing_date": signal["sowing_date"],
        "harvest_date": signal["harvest_date"], "season_length_days": signal["season_length_days"],
        "from_phenology": signal["from_phenology"],
    }
    window = {"season_label": "", "start": signal["window_start"], "end": signal["window_end"]}
    return signal_for_report, window, signal


@router.get("/fields/{field_id}/verifications/{verification_id}/evidence/pdf")
def export_verification_pdf(
    field_id: str, verification_id: int,
    user: dict = Depends(get_current_user), field: dict = Depends(_field),
):
    org_id = user["org_id"]
    credit = _owned_verification(field_id, verification_id, org_id)
    field_info = {"field_id": field_id, "name": field["name"], "district": field["district"],
                  "area_ha": field["area_ha"]}

    if field["field_type"] == "rice_awd":
        signal_for_report, window, _ = _rice_signal_for_report(org_id, field_id)
        pdf_bytes = generate_pdf(field_info, window, signal_for_report, credit["result"])
    else:
        meta = {"verification_years": credit["inputs"].get("verification_years"),
                "non_permanence_risk_pct": credit["inputs"].get("non_permanence_risk_pct")}
        practice_schedule = get_alm_practice_schedule(org_id, field_id)
        livestock_schedule = get_alm_livestock_schedule(org_id, field_id)
        pdf_bytes = generate_pdf_alm(field_info, meta, practice_schedule, credit["result"], livestock_schedule)

    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/fields/{field_id}/verifications/{verification_id}/evidence/json")
def export_verification_json(
    field_id: str, verification_id: int,
    user: dict = Depends(get_current_user), field: dict = Depends(_field),
):
    org_id = user["org_id"]
    credit = _owned_verification(field_id, verification_id, org_id)
    field_info = {"field_id": field_id, "name": field["name"], "district": field["district"],
                  "area_ha": field["area_ha"]}

    if field["field_type"] == "rice_awd":
        signal_for_report, window, signal = _rice_signal_for_report(org_id, field_id)
        df = pd.DataFrame(signal["timeseries"])
        json_str = generate_audit_json(field_info, window, signal_for_report, credit["result"], df)
    else:
        meta = {"verification_years": credit["inputs"].get("verification_years"),
                "non_permanence_risk_pct": credit["inputs"].get("non_permanence_risk_pct")}
        practice_schedule = get_alm_practice_schedule(org_id, field_id)
        soc_measurements = get_soc_measurements(org_id, field_id)
        livestock_schedule = get_alm_livestock_schedule(org_id, field_id)
        json_str = generate_audit_json_alm(
            field_info, meta, practice_schedule, soc_measurements, credit["result"], livestock_schedule
        )

    return Response(content=json_str, media_type="application/json")


@router.get("/fields/{field_id}/verifications/{verification_id}/evidence/csv")
def export_verification_csv(
    field_id: str, verification_id: int,
    user: dict = Depends(get_current_user), field: dict = Depends(_field),
):
    org_id = user["org_id"]
    # Existence/ownership check even though the CSV itself (timeseries or
    # practice/SOC rows) doesn't come from the credit_history row — a
    # bad/foreign verification_id must still 404, not silently succeed.
    _owned_verification(field_id, verification_id, org_id)

    if field["field_type"] == "rice_awd":
        signal = get_latest_signal_result(org_id, field_id)
        if signal is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "No signal-analytics run recorded for this field yet")
        csv_str = generate_timeseries_csv(pd.DataFrame(signal["timeseries"]))
    else:
        practice_schedule = get_alm_practice_schedule(org_id, field_id)
        soc_measurements = get_soc_measurements(org_id, field_id)
        csv_str = generate_alm_data_csv(practice_schedule, soc_measurements)

    return Response(content=csv_str, media_type="text/csv")
