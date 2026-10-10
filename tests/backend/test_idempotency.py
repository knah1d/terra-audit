def test_retired_rice_commit_is_rejected_without_history_writes(client, rice_field, auth_headers):
    """The legacy rice commit path is retired for the same reason ALM's
    was: a client-supplied, un-frozen area_ha could otherwise determine
    recorded credits (see src.persistence.database.
    commit_carbon_credit_result's docstring). This replaces the old
    test_duplicate_commit_does_not_double_write, which asserted the
    legacy path still wrote credit_history rows."""
    body = {"awd_events": 1, "season_length_days": 90, "area_ha": 3.0}
    headers = {**auth_headers["admin"], "Idempotency-Key": "same-key"}

    r1 = client.post(f"/fields/{rice_field}/carbon-credits/commit", json=body, headers=headers)
    assert r1.status_code == 422
    assert "evidence-linked Calculations" in r1.json()["detail"]

    r2 = client.post(f"/fields/{rice_field}/carbon-credits/commit", json=body, headers=headers)
    assert r2.status_code == 422

    r = client.get(f"/fields/{rice_field}/credit-history", headers=auth_headers["admin"])
    assert r.json() == []


def test_missing_idempotency_key_is_422(client, rice_field, auth_headers):
    r = client.post(
        f"/fields/{rice_field}/carbon-credits/commit",
        json={"awd_events": 1, "season_length_days": 90, "area_ha": 3.0},
        headers=auth_headers["admin"],
    )
    assert r.status_code == 422  # FastAPI's own required-header validation


def test_retired_alm_commit_is_rejected_without_cumulative_or_history_writes(client, alm_field, auth_headers):
    from src.persistence.database import get_alm_cumulative_delta

    before = get_alm_cumulative_delta("testorg", alm_field)
    body = {"area_ha": 10.0, "verification_years": 1.0, "non_permanence_risk_pct": 20.0}
    headers = {**auth_headers["admin"], "Idempotency-Key": "alm-key-1"}

    first = client.post(f"/fields/{alm_field}/carbon-credits/commit", json=body, headers=headers)
    assert first.status_code == 422
    assert "evidence-linked Calculations" in first.json()["detail"]
    after_first = get_alm_cumulative_delta("testorg", alm_field)
    assert after_first == before

    retry = client.post(f"/fields/{alm_field}/carbon-credits/commit", json=body, headers=headers)
    assert retry.status_code == 422
    after_retry = get_alm_cumulative_delta("testorg", alm_field)
    assert after_retry == before
    assert client.get(f"/fields/{alm_field}/credit-history", headers=auth_headers["admin"]).json() == []


def test_alm_snapshot_commit_retry_preserves_one_draft_and_external_cumulative_state(
    client, alm_field, auth_headers, alm_calculation_context, isolated_db,
):
    from sqlalchemy import text

    before = isolated_db.get_alm_cumulative_delta("testorg", alm_field)
    headers = {**auth_headers["admin"], "Idempotency-Key": "alm-snapshot-key"}
    first = client.post(f"/fields/{alm_field}/calculations", json=alm_calculation_context, headers=headers)
    assert first.status_code == 201, first.text
    one = first.json()
    assert one["already_committed"] is False
    calc = one["calculation"]
    assert calc["status"] == "ready_for_review"  # readiness is informational; the reviewer decides
    assert calc["result"]["leakage"]["computable"] is True
    assert calc["result"]["leakage"]["selected_record_ids"]
    assert calc["result"]["final_issuance"] > 0
    assert not any(row["requirement_id"] == "common.additionality" for row in calc["readiness"])
    second = client.post(f"/fields/{alm_field}/calculations", json=alm_calculation_context, headers=headers)
    assert second.status_code == 201, second.text
    assert second.json()["already_committed"] is True
    assert second.json()["calculation"] == calc
    assert isolated_db.get_alm_cumulative_delta("testorg", alm_field) == before
    with isolated_db.get_db_connection() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM calculations WHERE org_id='testorg' AND field_id=:f"),
                            {"f": alm_field}).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM calculation_idempotency_keys WHERE org_id='testorg' AND field_id=:f"),
                            {"f": alm_field}).scalar() == 1
