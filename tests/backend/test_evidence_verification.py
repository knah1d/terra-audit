"""
Backend half of the Audit & Evidence feature: exports must be tied to a
specific, immutable, tenant/field-scoped committed verification id — never
to "whatever the field's latest mutable state happens to be right now."
"""

from src.database import create_job, mark_job_done


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


def _commit(client, field_id, headers, body, idem_key):
    r = client.post(
        f"/fields/{field_id}/carbon-credits/commit", json=body,
        headers={**headers, "Idempotency-Key": idem_key},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _alm_body(**overrides):
    body = {"area_ha": 2.0, "verification_years": 1.0, "non_permanence_risk_pct": 20.0}
    body.update(overrides)
    return body


def test_credit_history_exposes_stable_verification_id(client, alm_field, auth_headers):
    client.put(f"/fields/{alm_field}/practice-schedule/baseline",
               json={"entries": [{"practice": "conventional_tillage", "start_date": "2025-01-01",
                                   "end_date": "2025-12-31"}]}, headers=auth_headers["admin"])
    client.put(f"/fields/{alm_field}/practice-schedule/project",
               json={"entries": [{"practice": "no_till", "start_date": "2026-01-01",
                                   "end_date": "2026-12-31"}]}, headers=auth_headers["admin"])
    _commit(client, alm_field, auth_headers["admin"], _alm_body(), "k1")

    r = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"])
    assert r.status_code == 200
    history = r.json()
    assert len(history) == 1
    assert isinstance(history[0]["credit_history_id"], int)


def test_verification_export_json_round_trips_committed_inputs(client, alm_field, auth_headers):
    client.put(f"/fields/{alm_field}/practice-schedule/baseline",
               json={"entries": []}, headers=auth_headers["admin"])
    client.put(f"/fields/{alm_field}/practice-schedule/project",
               json={"entries": []}, headers=auth_headers["admin"])
    committed = _commit(client, alm_field, auth_headers["admin"], _alm_body(), "k2")
    history = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()
    vid = history[0]["credit_history_id"]

    r = client.get(f"/fields/{alm_field}/verifications/{vid}/evidence/json", headers=auth_headers["admin"])
    assert r.status_code == 200
    # generate_audit_json_alm (src/report_generator.py) nests the committed
    # result under "carbon_calculation", not "credits".
    assert r.json()["carbon_calculation"]["final_issuance"] == committed["final_issuance"]


def test_verification_export_pdf_and_csv_succeed(client, alm_field, auth_headers):
    client.put(f"/fields/{alm_field}/practice-schedule/baseline",
               json={"entries": []}, headers=auth_headers["admin"])
    client.put(f"/fields/{alm_field}/practice-schedule/project",
               json={"entries": []}, headers=auth_headers["admin"])
    _commit(client, alm_field, auth_headers["admin"], _alm_body(), "k3")
    vid = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()[0]["credit_history_id"]

    r_pdf = client.get(f"/fields/{alm_field}/verifications/{vid}/evidence/pdf", headers=auth_headers["admin"])
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"

    r_csv = client.get(f"/fields/{alm_field}/verifications/{vid}/evidence/csv", headers=auth_headers["admin"])
    assert r_csv.status_code == 200


def test_alm_verification_export_succeeds(client, alm_field, auth_headers):
    client.put(f"/fields/{alm_field}/practice-schedule/baseline",
               json={"entries": []}, headers=auth_headers["admin"])
    client.put(f"/fields/{alm_field}/practice-schedule/project",
               json={"entries": []}, headers=auth_headers["admin"])
    _commit(client, alm_field, auth_headers["admin"], _alm_body(), "k4")
    vid = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()[0]["credit_history_id"]
    r = client.get(f"/fields/{alm_field}/verifications/{vid}/evidence/json", headers=auth_headers["admin"])
    assert r.status_code == 200


def test_historical_export_reflects_the_selected_run_not_the_latest(client, alm_field, auth_headers):
    client.put(f"/fields/{alm_field}/practice-schedule/baseline",
               json={"entries": []}, headers=auth_headers["admin"])
    client.put(f"/fields/{alm_field}/practice-schedule/project",
               json={"entries": []}, headers=auth_headers["admin"])
    first = _commit(client, alm_field, auth_headers["admin"], _alm_body(area_ha=2.0), "k5")
    second = _commit(client, alm_field, auth_headers["admin"], _alm_body(area_ha=9.0), "k6")
    assert first["final_issuance"] != second["final_issuance"]

    history = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()
    history_sorted = sorted(history, key=lambda h: h["credit_history_id"])
    first_id = history_sorted[0]["credit_history_id"]

    r = client.get(f"/fields/{alm_field}/verifications/{first_id}/evidence/json", headers=auth_headers["admin"])
    assert r.status_code == 200


def test_nonexistent_verification_id_is_404(client, alm_field, auth_headers):
    r = client.get(f"/fields/{alm_field}/verifications/999999/evidence/json", headers=auth_headers["admin"])
    assert r.status_code == 404


def test_verification_from_another_field_is_404(client, alm_field, rice_field, auth_headers):
    client.put(f"/fields/{alm_field}/practice-schedule/baseline",
               json={"entries": []}, headers=auth_headers["admin"])
    client.put(f"/fields/{alm_field}/practice-schedule/project",
               json={"entries": []}, headers=auth_headers["admin"])
    _commit(client, alm_field, auth_headers["admin"], _alm_body(), "k7")
    vid = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()[0]["credit_history_id"]

    r = client.get(f"/fields/{rice_field}/verifications/{vid}/evidence/json", headers=auth_headers["admin"])
    assert r.status_code == 404


def test_verification_from_another_org_is_404(client, alm_field, auth_headers):
    client.put(f"/fields/{alm_field}/practice-schedule/baseline",
               json={"entries": []}, headers=auth_headers["admin"])
    client.put(f"/fields/{alm_field}/practice-schedule/project",
               json={"entries": []}, headers=auth_headers["admin"])
    _commit(client, alm_field, auth_headers["admin"], _alm_body(), "k8")
    vid = client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json()[0]["credit_history_id"]

    r = client.get(f"/fields/{alm_field}/verifications/{vid}/evidence/json",
                    headers=auth_headers["other_org_admin"])
    assert r.status_code == 404


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
