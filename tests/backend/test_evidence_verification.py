"""
Retained historical ALM exports use the selected stored calculation result.
Legacy report context is still mutable; these tests do not claim it is an
immutable snapshot. New ALM writes must use evidence-linked calculations.
"""

import json

from sqlalchemy import text

from src.carbon.alm import AlmCarbonEngine
from src.persistence.database import create_job, mark_job_done


def _seed_signal_run(org_id: str, field_id: str, **overrides) -> dict:
    result = {
        "field_id": field_id, "cache_source": "Local relational data store",
        "total_awd": 2, "sowing_date": "2026-01-05", "harvest_date": "2026-04-10",
        "season_length_days": 95, "from_phenology": True,
        "detector_used": "Threshold Gate (rule-based)", "model_fallback_msg": None,
        "n_observations": 20, "vv_mean": -9.5, "vv_std": 0.6,
        "awd_dates": ["2026-02-01", "2026-03-01"],
        "window_start": "2026-01-01", "window_end": "2026-04-15",
        "area_ha": 1.5, "timeseries": [{"date": "2026-01-01", "vv_smoothed": -9.0}],
    }
    result.update(overrides)
    job_id = create_job(org_id, "signal_run")
    mark_job_done(job_id, result)
    return result


def _seed_historical_alm_record(db, field_id, body, computable_leakage):
    """Explicit fixture insertion for rows predating retired ALM writes.

    This is test setup only, not a substitute production write path.
    Run real math with complete leakage evidence to populate report fields.
    """
    livestock = db.get_alm_livestock_schedule("testorg", field_id)
    result = AlmCarbonEngine().calculate_credits(
        db.get_alm_practice_schedule("testorg", field_id), db.get_soc_measurements("testorg", field_id),
        **body, baseline_livestock=livestock.get("baseline"), project_livestock=livestock.get("project"),
        leakage_result=computable_leakage(area_ha=body["area_ha"], years=body["verification_years"]),
    )
    assert result["final_issuance"] is not None
    with db.get_db_connection() as conn:
        conn.execute(text("""INSERT INTO credit_history
            (org_id,field_id,field_type,final_issuance,inputs_json,result_json)
            VALUES ('testorg',:field,'cropland_alm_vm0042',:value,:inputs,:result)"""),
            {"field": field_id, "value": result["final_issuance"],
             "inputs": json.dumps(body), "result": json.dumps(result)})
        conn.commit()
    return {"final_issuance": result["final_issuance"], "result": result}


def _alm_body(**overrides):
    body = {"area_ha": 2.0, "verification_years": 1.0, "non_permanence_risk_pct": 20.0}
    body.update(overrides)
    return body


def test_credit_history_exposes_stable_verification_id(client, alm_field, auth_headers, isolated_db, computable_leakage):
    _seed_historical_alm_record(isolated_db, alm_field, _alm_body(), computable_leakage)

    r = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"])
    assert r.status_code == 200
    history = r.json()
    assert len(history) == 1
    assert isinstance(history[0]["credit_history_id"], int)
    assert history[0]["inputs"] == _alm_body()


def test_verification_export_json_round_trips_committed_inputs(client, alm_field, auth_headers, isolated_db, computable_leakage):
    committed = _seed_historical_alm_record(isolated_db, alm_field, _alm_body(), computable_leakage)
    history = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()
    vid = history[0]["credit_history_id"]

    r = client.get(f"/fields/{alm_field}/verifications/{vid}/evidence/json", headers=auth_headers["admin"])
    assert r.status_code == 200
    # generate_audit_json_alm (src/reporting/reports.py) nests the committed
    # result under "carbon_calculation", not "credits".
    assert r.json()["carbon_calculation"]["final_issuance"] == committed["final_issuance"]
    assert r.json()["carbon_calculation"] == committed["result"]


def test_verification_export_pdf_and_csv_succeed(client, alm_field, auth_headers, isolated_db, computable_leakage):
    _seed_historical_alm_record(isolated_db, alm_field, _alm_body(), computable_leakage)
    vid = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()[0]["credit_history_id"]

    r_pdf = client.get(f"/fields/{alm_field}/verifications/{vid}/evidence/pdf", headers=auth_headers["admin"])
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"

    r_csv = client.get(f"/fields/{alm_field}/verifications/{vid}/evidence/csv", headers=auth_headers["admin"])
    assert r_csv.status_code == 200


def test_alm_verification_export_succeeds(client, alm_field, auth_headers, isolated_db, computable_leakage):
    _seed_historical_alm_record(isolated_db, alm_field, _alm_body(), computable_leakage)
    vid = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()[0]["credit_history_id"]
    r = client.get(f"/fields/{alm_field}/verifications/{vid}/evidence/json", headers=auth_headers["admin"])
    assert r.status_code == 200


def test_historical_export_reflects_the_selected_run_not_the_latest(client, alm_field, auth_headers, isolated_db, computable_leakage):
    first = _seed_historical_alm_record(isolated_db, alm_field, _alm_body(area_ha=2.0), computable_leakage)
    second = _seed_historical_alm_record(isolated_db, alm_field, _alm_body(area_ha=9.0), computable_leakage)
    assert first["final_issuance"] != second["final_issuance"]

    history = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()
    history_sorted = sorted(history, key=lambda h: h["credit_history_id"])
    first_id = history_sorted[0]["credit_history_id"]

    r = client.get(f"/fields/{alm_field}/verifications/{first_id}/evidence/json", headers=auth_headers["admin"])
    assert r.status_code == 200
    assert r.json()["carbon_calculation"] == first["result"]
    assert r.json()["carbon_calculation"]["final_issuance"] != second["final_issuance"]


def test_nonexistent_verification_id_is_404(client, alm_field, auth_headers):
    r = client.get(f"/fields/{alm_field}/verifications/999999/evidence/json", headers=auth_headers["admin"])
    assert r.status_code == 404


def test_verification_from_another_field_is_404(client, alm_field, rice_field, auth_headers, isolated_db, computable_leakage):
    _seed_historical_alm_record(isolated_db, alm_field, _alm_body(), computable_leakage)
    vid = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()[0]["credit_history_id"]

    r = client.get(f"/fields/{rice_field}/verifications/{vid}/evidence/json", headers=auth_headers["admin"])
    assert r.status_code == 404


def test_verification_from_another_org_is_404(client, alm_field, auth_headers, isolated_db, computable_leakage):
    _seed_historical_alm_record(isolated_db, alm_field, _alm_body(), computable_leakage)
    vid = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()[0]["credit_history_id"]

    r = client.get(f"/fields/{alm_field}/verifications/{vid}/evidence/json",
                    headers=auth_headers["other_org_admin"])
    assert r.status_code == 404


def test_current_alm_pdf_uses_frozen_snapshot_and_enforces_scope(
    client, alm_field, auth_headers, alm_calculation_context, isolated_db, monkeypatch,
):
    from backend.routers import export

    committed = client.post(f"/fields/{alm_field}/calculations", json=alm_calculation_context,
                            headers={**auth_headers["admin"], "Idempotency-Key": "snapshot-export"})
    assert committed.status_code == 201, committed.text
    calc = committed.json()["calculation"]
    path = f"/calculations/{calc['calculation_id']}/evidence/pdf"
    assert client.get(path, headers=auth_headers["other_org_admin"]).status_code == 404
    assert client.get(path, headers=auth_headers["viewer"]).status_code == 403

    # Change current field AND practice-schedule data after commit. The
    # report must still render the frozen snapshot, never a live re-read
    # of either — a stale snapshot caught only one of the two would be a
    # real regression hiding behind a passing test.
    isolated_db.update_field_info("testorg", alm_field, "Changed after commit", "Different district")
    mutated_baseline = client.put(
        f"/fields/{alm_field}/practice-schedule/baseline",
        json={"crop_type": "changed_after_commit", "tillage": True, "tillage_depth_cm": 99.0},
        headers=auth_headers["admin"],
    )
    assert mutated_baseline.status_code == 200, mutated_baseline.text
    assert mutated_baseline.json()["baseline"] != calc["snapshot"]["alm_practice_schedule"].get("baseline")
    rendered = []
    generate = export.generate_pdf_alm
    def capture(field, meta, practices, result, livestock):
        rendered.append((field, meta, practices, result, livestock))
        return generate(field, meta, practices, result, livestock)
    monkeypatch.setattr(export, "generate_pdf_alm", capture)
    response = client.get(path, headers=auth_headers["admin"])
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    field, meta, practices, result, livestock = rendered[0]
    assert field == calc["snapshot"]["field"]
    assert practices == calc["snapshot"]["alm_practice_schedule"]
    assert livestock == calc["snapshot"].get("alm_livestock_schedule")
    assert result == calc["result"]
    assert meta["status"] == "ready_for_review" and meta["readiness"] == calc["readiness"]  # readiness is informational; it no longer holds a calculation back
    assert client.get(f"/calculations/{calc['calculation_id']}", headers=auth_headers["admin"]).json() == calc


def test_latest_signal_run_404s_when_none_recorded(client, rice_field, auth_headers):
    r = client.get(f"/fields/{rice_field}/signal-runs/latest", headers=auth_headers["admin"])
    assert r.status_code == 404


def test_latest_signal_run_returns_seeded_result(client, rice_field, auth_headers):
    _seed_signal_run("testorg", rice_field)
    r = client.get(f"/fields/{rice_field}/signal-runs/latest", headers=auth_headers["admin"])
    assert r.status_code == 200
    assert r.json()["field_id"] == rice_field


def test_latest_signal_run_rejects_alm_field(client, alm_field, auth_headers):
    r = client.get(f"/fields/{alm_field}/signal-runs/latest", headers=auth_headers["admin"])
    assert r.status_code == 422
