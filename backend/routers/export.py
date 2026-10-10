from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.deps import get_current_user, get_owned_field
from src.persistence.database import (
    get_alm_livestock_schedule, get_alm_practice_schedule,
    get_credit_history_entry, get_latest_signal_result, get_soc_measurements,
)
from src.reporting.reports import (
    generate_audit_json, generate_audit_json_alm, generate_alm_data_csv,
    generate_mrv_report_vm0051, generate_pdf, generate_pdf_alm, generate_timeseries_csv,
)
import hashlib
import json
import pandas as pd

router = APIRouter(tags=["export"])

_field = get_owned_field()


def _mrv_context(org_id: str, calculation: dict, user: dict) -> dict:
    """Everything the VM0051 monitoring report shows, read for ONE calculation
    version: its frozen snapshot, the linked satellite run, and the internal
    review record. FINAL only once a submission of this exact version is
    internally approved; otherwise the report is a watermarked draft."""
    from src.accounts.auth import list_org_users
    from src.persistence.database import get_job
    from src.projects import repository as projects_db
    from src.projects import reviews as reviews_db

    snapshot = calculation["snapshot"]
    provenance = snapshot.get("signal_input_provenance") or {}
    job = get_job(org_id, provenance["job_id"]) if provenance.get("job_id") else None
    submissions = [s for s in reviews_db.list_submissions(org_id, calculation["project_id"])
                   if s["calculation_id"] == calculation["calculation_id"] and s["status"] != "withdrawn"] \
        if calculation["project_id"] else []
    approved = next((s for s in submissions if s["status"] == "internally_approved"), None)
    submission = approved or (submissions[0] if submissions else None)
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "status": "final" if approved else "draft",
        "calculation": calculation,
        "snapshot": snapshot,
        "snapshot_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "project": projects_db.get_project(org_id, calculation["project_id"]) if calculation["project_id"] else None,
        "signal": (job or {}).get("result"),
        "submission": submission,
        "events": reviews_db.events(org_id, submission["submission_id"]) if submission else [],
        "findings": reviews_db.list_findings(org_id, submission["submission_id"]) if submission else [],
        "users": {u["user_id"]: u["email"] for u in list_org_users(org_id)},
        "generated_by": user.get("email"),
    }


@router.get("/calculations/{calculation_id}/evidence/pdf")
def export_calculation_pdf(calculation_id: str, user: dict = Depends(get_current_user)):
    """Render a calculation's report from its stored snapshot only, never
    today's field data: the VM0051 monitoring (MRV) report for rice AWD,
    the ALM estimate report for VM0042."""
    from src.carbon.calculations import get_calculation
    from backend.access import require_project_access
    calculation = get_calculation(user["org_id"], calculation_id)
    if calculation is None:
        raise HTTPException(404, "Calculation not found")
    if calculation["project_id"]:
        require_project_access(user["org_id"], calculation["project_id"], user)
    if calculation["accounting_pathway"] == "vm0051_rice_awd":
        pdf_bytes = generate_mrv_report_vm0051(_mrv_context(user["org_id"], calculation, user))
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="mrv-report-{calculation_id}.pdf"'})
    if calculation["accounting_pathway"] != "vm0042_alm":
        raise HTTPException(422, "No report is available for this accounting pathway.")
    snapshot = calculation["snapshot"]
    inputs = snapshot["engine_inputs"]
    meta = {"verification_years": inputs.get("verification_years", 1),
            "non_permanence_risk_pct": inputs.get("non_permanence_risk_pct", 20),
            "calculation_id": calculation_id, "status": calculation["status"],
            "monitoring_period": snapshot["monitoring_period"],
            "methodology_bundle": snapshot.get("methodology_bundle", {}),
            "readiness": calculation["readiness"]}
    pdf_bytes = generate_pdf_alm(snapshot["field"], meta, snapshot["alm_practice_schedule"],
                                 calculation["result"], snapshot.get("alm_livestock_schedule"))
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="calculation-{calculation_id}.pdf"'})


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
