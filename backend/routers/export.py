from datetime import date
import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.deps import get_current_user, get_owned_field
from src.persistence.database import (
    get_alm_livestock_schedule, get_alm_practice_schedule,
    get_credit_history_entry, get_latest_signal_result, get_soc_measurements,
)
from src.reporting.reports import (
    generate_audit_json, generate_audit_json_alm, generate_alm_data_csv,
    generate_mrv_report_vm0051, generate_pdf, generate_pdf_alm, generate_project_mrv_report_vm0051,
    generate_timeseries_csv,
)
import hashlib
import json
import pandas as pd

router = APIRouter(tags=["export"])

_field = get_owned_field()


def _mrv_context(org_id: str, calculation: dict, user: dict, users: dict | None = None) -> dict:
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
        "users": users if users is not None else {u["user_id"]: u["email"] for u in list_org_users(org_id)},
        "generated_by": user.get("email"),
    }


def _project_mrv(org_id: str, project_id: str, user: dict, start: date | None, end: date | None) -> dict:
    """The project's monitoring report scope: every field's current
    (latest non-superseded) reviewable VM0051 calculation whose period lies
    inside [start, end]. Drafts and out-of-period fields are listed as
    excluded with the reason, never silently dropped. FINAL only when every
    included calculation is internally approved."""
    from src.accounts.auth import list_org_users
    from src.carbon.calculations import list_calculations
    from src.persistence.database import get_field
    from src.projects import repository as projects_db

    project = projects_db.get_project(org_id, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    users = {u["user_id"]: u["email"] for u in list_org_users(org_id)}
    in_period = lambda c: ((start is None or c["monitoring_period_start"] >= start.isoformat())
                           and (end is None or c["monitoring_period_end"] <= end.isoformat()))
    current = [c for c in list_calculations(org_id, project_id=project_id, latest_only=True)
               if c["accounting_pathway"] == "vm0051_rice_awd" and in_period(c)]
    included = [_mrv_context(org_id, c, user, users) for c in current if c["status"] == "ready_for_review"]
    for item in included:
        sub = item["submission"]
        item["review_status"] = sub["status"] if sub else "not_submitted"
    included.sort(key=lambda i: (i["snapshot"]["field"]["name"], i["calculation"]["monitoring_period_start"]))

    reported = {i["calculation"]["field_id"] for i in included}
    drafts = {c["field_id"] for c in current if c["status"] != "ready_for_review"}
    excluded = []
    for field_id in sorted({m["field_id"] for m in projects_db.list_project_fields(org_id, project_id)} - reported):
        field = get_field(org_id, field_id)
        if field is None or field["field_type"] != "rice_awd":
            continue
        excluded.append({"field_id": field_id, "name": field["name"],
                         "reason": "Latest calculation is a draft (open readiness items)" if field_id in drafts
                                   else "No saved calculation in this period"})

    starts = [i["calculation"]["monitoring_period_start"] for i in included]
    ends = [i["calculation"]["monitoring_period_end"] for i in included]
    approved = bool(included) and all(i["review_status"] == "internally_approved" for i in included)
    return {
        "project": project, "users": users, "included": included, "excluded": excluded,
        "status": "final" if approved else "draft",
        "period_start": start.isoformat() if start else (min(starts) if starts else "-"),
        "period_end": end.isoformat() if end else (max(ends) if ends else "-"),
        "generated_by": user.get("email"),
    }


def _project_access(user: dict, project_id: str) -> None:
    from backend.access import require_project_access
    require_project_access(user["org_id"], project_id, user)


@router.get("/projects/{project_id}/mrv")
def project_mrv_summary(project_id: str, start: date | None = None, end: date | None = None,
                        user: dict = Depends(get_current_user)):
    _project_access(user, project_id)
    ctx = _project_mrv(user["org_id"], project_id, user, start, end)
    return {
        "status": ctx["status"], "period_start": ctx["period_start"], "period_end": ctx["period_end"],
        "net_tco2e": sum(float(i["calculation"]["result"].get("final_issuance") or 0) for i in ctx["included"]),
        "included": [{
            "calculation_id": i["calculation"]["calculation_id"], "version": i["calculation"]["version"],
            "field_id": i["calculation"]["field_id"], "field_name": i["snapshot"]["field"]["name"],
            "area_ha": i["snapshot"]["field"]["area_ha"],
            "period_start": i["calculation"]["monitoring_period_start"],
            "period_end": i["calculation"]["monitoring_period_end"],
            "net_tco2e": i["calculation"]["result"].get("final_issuance"),
            "review_status": i["review_status"],
            "submission_id": i["submission"]["submission_id"] if i["submission"] else None,
        } for i in ctx["included"]],
        "excluded": ctx["excluded"],
    }


def _require_reportable(ctx: dict) -> None:
    if not ctx["included"]:
        raise HTTPException(422, "No field in this project has a reviewable VM0051 calculation in this period.")


@router.get("/projects/{project_id}/mrv/report.pdf")
def project_mrv_report(project_id: str, start: date | None = None, end: date | None = None,
                       user: dict = Depends(get_current_user)):
    _project_access(user, project_id)
    ctx = _project_mrv(user["org_id"], project_id, user, start, end)
    _require_reportable(ctx)
    return Response(content=generate_project_mrv_report_vm0051(ctx), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="project-mrv-report-{project_id}.pdf"'})


@router.get("/projects/{project_id}/mrv/package.zip")
def project_mrv_package(project_id: str, start: date | None = None, end: date | None = None,
                        user: dict = Depends(get_current_user)):
    """Evidence package for a verifier: the project report, every field's
    report, frozen calculation snapshots, the Sentinel-1 analysis results,
    attached field documents, and a manifest of SHA-256 hashes."""
    from src.persistence.database import get_job
    from src.persistence.storage import get_storage, sanitize_filename

    _project_access(user, project_id)
    org_id = user["org_id"]
    ctx = _project_mrv(org_id, project_id, user, start, end)
    _require_reportable(ctx)

    files: dict[str, bytes] = {"project-mrv-report.pdf": generate_project_mrv_report_vm0051(ctx)}
    missing = []
    for item in ctx["included"]:
        calc = item["calculation"]
        folder = f"fields/{sanitize_filename(calc['field_id'])}"
        tag = f"v{calc['version']}-{calc['calculation_id'][:8]}"
        files[f"{folder}/mrv-report-{tag}.pdf"] = generate_mrv_report_vm0051(item)
        files[f"{folder}/calculation-{tag}.json"] = json.dumps(calc, indent=2, sort_keys=True, default=str).encode()
        job_id = (item["snapshot"].get("signal_input_provenance") or {}).get("job_id")
        job = get_job(org_id, job_id) if job_id else None
        if job:
            files[f"{folder}/sentinel1-analysis-{job_id[:8]}.json"] = json.dumps(
                job.get("result"), indent=2, sort_keys=True, default=str).encode()
        for att in item["snapshot"].get("attachments") or []:
            try:
                with get_storage().open(att["storage_key"]) as f:
                    files[f"{folder}/documents/{att['attachment_id'][:8]}-{sanitize_filename(att['filename'])}"] = f.read()
            except (OSError, KeyError, ValueError):
                missing.append(att.get("filename"))

    manifest = {
        "project_id": project_id, "project_name": ctx["project"]["name"], "methodology": "VM0051 v1.1",
        "status": ctx["status"], "monitoring_period": [ctx["period_start"], ctx["period_end"]],
        "generated_by": ctx["generated_by"], "missing_documents": missing,
        "files": [{"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                  for path, data in sorted(files.items())],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in files.items():
            zf.writestr(path, data)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return Response(content=buffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="mrv-package-{project_id}.zip"'})


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
