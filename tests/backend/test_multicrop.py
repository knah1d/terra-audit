from copy import deepcopy

import pandas as pd
from sqlalchemy import text

from src import monitoring
from src.ai.crop_benchmark import build_corpus
from src.processing import MULTICROP_VERSION


def create_season(client, headers, field, crops=None):
    response = client.post(f"/fields/{field}/crop-seasons", headers=headers, json={
        "name": "Winter", "crops": crops or ["Wheat"], "start_date": "2025-11-01", "end_date": "2026-03-01"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_seasons_for_both_types_and_isolation(client, auth_headers, rice_field, alm_field):
    for field in (rice_field, alm_field):
        sid = create_season(client, auth_headers["admin"], field, ["Wheat", "Lentil"])
        path = f"/fields/{field}/crop-seasons"
        assert client.get(path, headers=auth_headers["viewer"]).json()[0]["payload"]["crops"] == ["wheat", "lentil"]
        assert client.post(path, headers=auth_headers["viewer"], json={"name": "bad"}).status_code == 403
        assert client.get(f"{path}/{sid}/evidence", headers=auth_headers["other_org_admin"]).status_code == 404
    assert client.get(f"/fields/{rice_field}/crop-seasons/{sid}/evidence", headers=auth_headers["admin"]).status_code == 404


def test_invalid_season_and_observations(client, auth_headers, rice_field):
    path = f"/fields/{rice_field}/crop-seasons"
    bad = {"name": "Season", "crops": ["  "], "start_date": "2025-03-01", "end_date": "2025-01-01"}
    assert client.post(path, json=bad, headers=auth_headers["admin"]).status_code == 422
    sid = create_season(client, auth_headers["admin"], rice_field)
    obs = {"observed_at": "2025-12-01T10:00:00Z", "kind": "residue_cover", "source": "field_measurement",
           "value": "Measured residue", "numeric_value": 101, "evidence_reference": "survey-1"}
    assert client.post(f"{path}/{sid}/observations", json=obs, headers=auth_headers["admin"]).status_code == 422
    obs.update(kind="crop_identity", value="wheat", numeric_value=None, observed_at="2025-12-01T10:00:00")
    assert client.post(f"{path}/{sid}/observations", json=obs, headers=auth_headers["admin"]).status_code == 422
    obs["observed_at"] = "2024-01-01T10:00:00Z"
    assert client.post(f"{path}/{sid}/observations", json=obs, headers=auth_headers["admin"]).status_code == 422


def test_review_and_benchmark_provenance(client, auth_headers, alm_field):
    sid = create_season(client, auth_headers["admin"], alm_field)
    path = f"/fields/{alm_field}/crop-seasons/{sid}"
    obs = {"observed_at": "2025-12-01T10:00:00Z", "kind": "crop_identity", "source": "expert_observation",
           "value": "wheat", "evidence_reference": "survey-1"}
    created = client.post(f"{path}/observations", json=obs, headers=auth_headers["admin"])
    assert created.status_code == 201
    oid = created.json()["id"]
    review_path = f"{path}/observations/{oid}/reviews"
    review = {"decision": "accepted", "reason": "Checked field survey"}
    assert client.post(review_path, json=review, headers=auth_headers["admin"]).status_code == 422
    assert client.post(review_path, json=review, headers=auth_headers["viewer"]).status_code == 403
    assert client.post(review_path, json=review, headers=auth_headers["analyst"]).status_code == 201
    payload = {"processing_version": MULTICROP_VERSION, "field": {"district": "Test"},
               "window_start": "2025-11-01", "window_end": "2026-03-01", "observations": [],
               "quality": {"status": "ready_for_exploration"}}
    monitoring.append_record("monitoring_runs", "testorg", alm_field, sid, payload)
    corpus = build_corpus("testorg")
    assert corpus["examples"][0]["label_observation_ids"] == [oid]
    assert corpus["examples"][0]["crop"] == "wheat"
    assert build_corpus("otherorg")["examples"] == []
    # Reviews are append-only and the latest decision controls eligibility.
    client.post(review_path, json={"decision": "rejected", "reason": "Survey location wrong"}, headers=auth_headers["analyst"])
    assert not build_corpus("testorg")["examples"]
    evidence = client.get(f"{path}/evidence", headers=auth_headers["viewer"]).json()
    assert len(evidence["reviews"]) == 2
    assert len(evidence["sha256"]) == 64


def test_monitoring_is_generic_and_snapshots_are_stable(client, auth_headers, alm_field, monkeypatch):
    sid = create_season(client, auth_headers["admin"], alm_field)
    original = {"processing_version": MULTICROP_VERSION, "observations": [],
                "quality": {"status": "insufficient_evidence", "warnings": ["no imagery"]}}
    monkeypatch.setattr("backend.routers.monitoring.extract_observations", lambda *args: deepcopy(original))
    path = f"/fields/{alm_field}/crop-seasons/{sid}"
    accepted = client.post(f"{path}/monitoring-runs", headers=auth_headers["admin"])
    assert accepted.status_code == 202
    jobid = accepted.json()["job_id"]
    assert client.get(f"/multi-crop/jobs/{jobid}", headers=auth_headers["admin"]).json()["status"] == "done"
    assert client.get(f"/multi-crop/jobs/{jobid}", headers=auth_headers["other_org_admin"]).status_code == 404
    before = client.get(f"{path}/evidence", headers=auth_headers["admin"]).json()
    from src.database import update_field_info
    update_field_info("testorg", alm_field, "Changed", "Changed")
    after = client.get(f"{path}/evidence", headers=auth_headers["admin"]).json()
    assert before == after
    assert before["runs"][0]["payload"]["field"]["district"] == "Test District"


def test_old_cache_not_marked_current(isolated_db, client, auth_headers, rice_field):
    df = pd.DataFrame([{"date": "2025-12-01", "vv": -10, "vh": -20, "cross_ratio": -10, "rvi": 0.36}])
    isolated_db.save_cache("testorg", rice_field, df, "2025-11-01", "2026-03-01")
    assert not isolated_db.check_cache("testorg", rice_field, "2025-11-01", "2026-03-01").empty
    with isolated_db.get_db_connection() as conn:
        conn.execute(text("DELETE FROM timeseries_cache_versions")); conn.commit()
    assert isolated_db.check_cache("testorg", rice_field, "2025-11-01", "2026-03-01").empty


def test_delete_field_removes_monitoring_records(client, auth_headers, rice_field):
    create_season(client, auth_headers["admin"], rice_field)
    assert monitoring.records("crop_seasons", "testorg", rice_field)
    assert client.delete(f"/fields/{rice_field}", headers=auth_headers["admin"]).status_code == 204
    assert monitoring.records("crop_seasons", "testorg", rice_field) == []


def test_insufficient_benchmark_returns_actionable_job_error(client, auth_headers):
    response = client.post("/multi-crop/benchmarks", headers=auth_headers["admin"], json={})
    assert response.status_code == 202
    job = client.get(f"/multi-crop/jobs/{response.json()['job_id']}", headers=auth_headers["admin"]).json()
    assert job["status"] == "error"
    assert "four eligible" in job["error"]
