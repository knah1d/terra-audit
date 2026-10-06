from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pandas as pd
import pytest
from sqlalchemy import text

from src.evidence import monitoring
from src.ai.ml.crop_benchmark import build_corpus
from src.signals.processing import MULTICROP_VERSION
from src.jobs.queue import get_job_row


def run_pending_job(job_id, job_type):
    """Exercise the durable queue claim and actual worker dispatch, not a
    router-local BackgroundTask or a manually fabricated completed result.
    """
    from backend.worker import _run_one
    from src.jobs.queue import claim_next_job, register_worker

    worker_id = f"regression-worker-{uuid4().hex}"
    register_worker(worker_id, "test-host", 0)
    job = claim_next_job(worker_id, [job_type])
    assert job is not None and job["job_id"] == job_id
    assert job["status"] == "running"
    _run_one(job, engine=None)


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


@pytest.mark.parametrize("quality_status", ["insufficient_evidence", "ready_for_exploration"])
def test_monitoring_is_generic_and_snapshots_are_stable(client, auth_headers, alm_field, monkeypatch, quality_status):
    sid = create_season(client, auth_headers["admin"], alm_field)
    original = {"processing_version": MULTICROP_VERSION, "observations": [],
                "quality": {"status": quality_status,
                            "warnings": ["no imagery"] if quality_status == "insufficient_evidence" else []}}
    monkeypatch.setattr("backend.job_handlers.extract_observations", lambda *args: deepcopy(original))
    path = f"/fields/{alm_field}/crop-seasons/{sid}"
    accepted = client.post(f"{path}/monitoring-runs", headers=auth_headers["admin"])
    assert accepted.status_code == 202
    jobid = accepted.json()["job_id"]
    queued = client.get(f"/multi-crop/jobs/{jobid}", headers=auth_headers["admin"]).json()
    assert queued["status"] == "pending"
    assert "payload" not in queued  # Internal frozen inputs are not a public status field.
    queued = get_job_row("testorg", jobid)
    assert queued["payload"]["processing_version"] == MULTICROP_VERSION
    assert queued["payload"]["season_start"] == "2025-11-01"
    assert queued["payload"]["season_end"] == "2026-03-01"
    assert queued["payload"]["geometry"]
    run_pending_job(jobid, "multicrop_monitoring")
    assert client.get(f"/multi-crop/jobs/{jobid}", headers=auth_headers["admin"]).json()["status"] == "done"
    assert client.get(f"/multi-crop/jobs/{jobid}", headers=auth_headers["other_org_admin"]).status_code == 404
    before = client.get(f"{path}/evidence", headers=auth_headers["admin"]).json()
    from src.persistence.database import update_field_info
    update_field_info("testorg", alm_field, "Changed", "Changed")
    after = client.get(f"{path}/evidence", headers=auth_headers["admin"]).json()
    assert before == after
    assert before["runs"][0]["payload"]["field"]["district"] == "Test District"
    # Only usable evidence may be reused. An insufficient run must be
    # collected again and appended, without changing the original evidence.
    calls = []
    def recollect(*args):
        if quality_status == "ready_for_exploration":
            pytest.fail("Reusable evidence must not query imagery again")
        calls.append(args)
        return deepcopy(original)
    monkeypatch.setattr("backend.job_handlers.extract_observations", recollect)
    reused = client.post(f"{path}/monitoring-runs", headers=auth_headers["admin"])
    assert reused.status_code == 202
    run_pending_job(reused.json()["job_id"], "multicrop_monitoring")
    job = client.get(f"/multi-crop/jobs/{reused.json()['job_id']}", headers=auth_headers["admin"]).json()
    assert job["status"] == "done"
    if quality_status == "ready_for_exploration":
        assert job["result"]["source"] == "reused"
        assert job["result"]["run_id"] == before["runs"][0]["id"]
        assert client.get(f"{path}/evidence", headers=auth_headers["admin"]).json() == before
    else:
        assert len(calls) == 1 and job["result"]["source"] == "collected"
        assert job["result"]["run_id"] != before["runs"][0]["id"]
        refreshed = client.get(f"{path}/evidence", headers=auth_headers["admin"]).json()
        assert len(refreshed["runs"]) == 2
        assert next(r for r in refreshed["runs"] if r["id"] == before["runs"][0]["id"]) == before["runs"][0]


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


def test_insufficient_benchmark_returns_actionable_error_after_worker_retries(client, auth_headers, monkeypatch):
    response = client.post("/multi-crop/benchmarks", headers=auth_headers["admin"], json={})
    assert response.status_code == 202
    jobid = response.json()["job_id"]
    path = f"/multi-crop/jobs/{jobid}"
    job = client.get(path, headers=auth_headers["admin"]).json()
    assert job["status"] == "pending"
    assert "payload" not in job
    job = get_job_row("testorg", jobid)
    assert job["payload"]["corpus"]["examples"] == []
    # ValueErrors currently use bounded retry handling. Advance the queue clock
    # across its backoff intervals rather than sleeping or bypassing the worker.
    now = datetime.now(timezone.utc)
    for attempt in range(1, job["max_attempts"] + 1):
        monkeypatch.setattr("src.jobs.queue._now", lambda attempt=attempt: now + timedelta(days=attempt))
        run_pending_job(jobid, "crop_benchmark")
        public_job = client.get(path, headers=auth_headers["admin"]).json()
        job = get_job_row("testorg", jobid)
        assert public_job["status"] == job["status"]
        assert public_job["error"] == job["error"]
        assert job["attempt_count"] == attempt
        assert job["status"] == ("error" if attempt == job["max_attempts"] else "pending")
        assert "four eligible" in job["error"]
    assert job["status"] == "error"
    assert "four eligible" in job["error"]
    assert job["error_kind"] == "retryable"
    assert client.get(path, headers=auth_headers["other_org_admin"]).status_code == 404
