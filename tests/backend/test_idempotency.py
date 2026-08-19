def test_duplicate_commit_does_not_double_write(client, rice_field, auth_headers):
    body = {"awd_events": 1, "season_length_days": 90, "area_ha": 3.0}
    headers = {**auth_headers["admin"], "Idempotency-Key": "same-key"}

    r1 = client.post(f"/fields/{rice_field}/carbon-credits/commit", json=body, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["already_committed"] is False

    r2 = client.post(f"/fields/{rice_field}/carbon-credits/commit", json=body, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["already_committed"] is True
    assert r2.json()["final_issuance"] == r1.json()["final_issuance"]

    r = client.get(f"/fields/{rice_field}/credit-history", headers=auth_headers["admin"])
    assert len(r.json()) == 1  # not 2


def test_missing_idempotency_key_is_422(client, rice_field, auth_headers):
    r = client.post(
        f"/fields/{rice_field}/carbon-credits/commit",
        json={"awd_events": 1, "season_length_days": 90, "area_ha": 3.0},
        headers=auth_headers["admin"],
    )
    assert r.status_code == 422  # FastAPI's own required-header validation


def test_alm_cumulative_delta_bumps_exactly_once_on_retry(client, alm_field, auth_headers):
    from src.database import get_alm_cumulative_delta

    before = get_alm_cumulative_delta("testorg", alm_field)
    body = {"area_ha": 10.0, "verification_years": 1.0, "non_permanence_risk_pct": 20.0}
    headers = {**auth_headers["admin"], "Idempotency-Key": "alm-key-1"}

    client.post(f"/fields/{alm_field}/carbon-credits/commit", json=body, headers=headers)
    after_first = get_alm_cumulative_delta("testorg", alm_field)
    assert after_first != before

    client.post(f"/fields/{alm_field}/carbon-credits/commit", json=body, headers=headers)
    after_retry = get_alm_cumulative_delta("testorg", alm_field)
    assert after_retry == after_first  # unchanged — not bumped a second time
