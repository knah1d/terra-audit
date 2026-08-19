from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from backend.deps import get_current_user, get_owned_field
from src.database import (
    get_alm_livestock_schedule, get_alm_practice_schedule, get_credit_history,
    get_soc_measurements, list_completed_jobs,
)
from src.report_generator import (
    generate_audit_json, generate_audit_json_alm, generate_alm_data_csv,
    generate_pdf, generate_pdf_alm, generate_timeseries_csv,
)
import pandas as pd

router = APIRouter(tags=["export"])

_field = get_owned_field()


def _latest_signal_result(org_id: str, field_id: str) -> dict | None:
    """The signal-run job result is this API's persisted replacement for
    Streamlit's export_* session_state keys (see plan Part A5) — export
    endpoints read the most recent completed run for this field rather
    than depending on anything held client-side."""
    for job in list_completed_jobs(org_id, "signal_run"):
        if job["result"] and job["result"].get("field_id") == field_id:
            return job["result"]
    return None


def _latest_or_specified_credit(org_id: str, field_id: str, credit_history_id: int | None) -> dict:
    history = get_credit_history(org_id, field_id)
    if not history:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No credit-history entry to export")
    # get_credit_history doesn't expose row ids today (only calculated_at/
    # final_issuance/inputs/result); "latest" is well-defined (list is
    # already ordered DESC), "specific id" isn't supported by the current
    # helper — documented limitation, not silently ignored.
    if credit_history_id is not None:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Selecting a specific credit_history_id isn't supported yet — "
            "get_credit_history() doesn't expose row ids. Exports use the latest entry.",
        )
    return history[0]


@router.get("/fields/{field_id}/export/pdf")
def export_pdf(field_id: str, credit_history_id: int | None = Query(None),
               user: dict = Depends(get_current_user), field: dict = Depends(_field)):
    org_id = user["org_id"]
    credit = _latest_or_specified_credit(org_id, field_id, credit_history_id)
    field_info = {"field_id": field_id, "name": field["name"], "district": field["district"],
                  "area_ha": field["area_ha"]}

    if field["field_type"] == "rice_awd":
        signal = _latest_signal_result(org_id, field_id)
        if signal is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "No signal-analytics run recorded for this field yet")
        window = {"season_label": "", "start": signal["window_start"], "end": signal["window_end"]}
        signal_for_report = {
            "n_observations": signal["n_observations"], "vv_mean": signal["vv_mean"],
            "vv_std": signal["vv_std"], "awd_events": signal["total_awd"],
            "awd_dates": signal["awd_dates"], "sowing_date": signal["sowing_date"],
            "harvest_date": signal["harvest_date"], "season_length_days": signal["season_length_days"],
            "from_phenology": signal["from_phenology"],
        }
        pdf_bytes = generate_pdf(field_info, window, signal_for_report, credit["result"])
    else:
        meta = {"verification_years": credit["inputs"].get("verification_years"),
                "non_permanence_risk_pct": credit["inputs"].get("non_permanence_risk_pct")}
        practice_schedule = get_alm_practice_schedule(org_id, field_id)
        livestock_schedule = get_alm_livestock_schedule(org_id, field_id)
        pdf_bytes = generate_pdf_alm(field_info, meta, practice_schedule, credit["result"], livestock_schedule)

    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/fields/{field_id}/export/json")
def export_json(field_id: str, credit_history_id: int | None = Query(None),
                 user: dict = Depends(get_current_user), field: dict = Depends(_field)):
    org_id = user["org_id"]
    credit = _latest_or_specified_credit(org_id, field_id, credit_history_id)
    field_info = {"field_id": field_id, "name": field["name"], "district": field["district"],
                  "area_ha": field["area_ha"]}

    if field["field_type"] == "rice_awd":
        signal = _latest_signal_result(org_id, field_id)
        if signal is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "No signal-analytics run recorded for this field yet")
        window = {"season_label": "", "start": signal["window_start"], "end": signal["window_end"]}
        signal_for_report = {
            "n_observations": signal["n_observations"], "vv_mean": signal["vv_mean"],
            "vv_std": signal["vv_std"], "awd_events": signal["total_awd"],
            "awd_dates": signal["awd_dates"], "sowing_date": signal["sowing_date"],
            "harvest_date": signal["harvest_date"], "season_length_days": signal["season_length_days"],
            "from_phenology": signal["from_phenology"],
        }
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


@router.get("/fields/{field_id}/export/csv")
def export_csv(field_id: str, user: dict = Depends(get_current_user),
               field: dict = Depends(_field)):
    org_id = user["org_id"]

    if field["field_type"] == "rice_awd":
        signal = _latest_signal_result(org_id, field_id)
        if signal is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "No signal-analytics run recorded for this field yet")
        csv_str = generate_timeseries_csv(pd.DataFrame(signal["timeseries"]))
    else:
        practice_schedule = get_alm_practice_schedule(org_id, field_id)
        soc_measurements = get_soc_measurements(org_id, field_id)
        csv_str = generate_alm_data_csv(practice_schedule, soc_measurements)

    return Response(content=csv_str, media_type="text/csv")
