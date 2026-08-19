"""
Regression tests for field-type correctness holes the per-router
load-or-404 preamble left open. Each of these four passed silently before
the get_owned_field dependency and the request-time field_type check.
"""

from sqlalchemy import text

from tests.backend.conftest import RICE_FEATURE


def _make_field(client, headers, field_id: str, field_type: str):
    r = client.post("/fields", json={
        "field_id": field_id, "name": "F", "district": "D",
        "field_type": field_type, "feature": RICE_FEATURE,
    }, headers=headers)
    assert r.status_code == 201, r.text
    return field_id


# --- field_type was never validated on create ---------------------------

def test_unknown_field_type_is_rejected(client, auth_headers):
    r = client.post("/fields", json={
        "field_id": "F-BOGUS", "name": "F", "district": "D",
        "field_type": "definitely_not_a_methodology", "feature": RICE_FEATURE,
    }, headers=auth_headers["admin"])
    assert r.status_code == 422
    assert "Unknown field_type" in r.text


def test_unknown_field_type_is_not_persisted(client, auth_headers, isolated_db):
    client.post("/fields", json={
        "field_id": "F-BOGUS2", "name": "F", "district": "D",
        "field_type": "bogus", "feature": RICE_FEATURE,
    }, headers=auth_headers["admin"])
    with isolated_db.get_db_connection() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM fields WHERE field_id = :f"), {"f": "F-BOGUS2"}
        ).scalar()
    # field_type is immutable after registration, so a bad value would be
    # permanently stuck on the row.
    assert count == 0


def test_known_field_types_still_accepted(client, auth_headers):
    for i, ft in enumerate(("rice_awd", "cropland_alm_vm0042")):
        r = client.post("/fields", json={
            "field_id": f"F-OK-{i}", "name": "F", "district": "D",
            "field_type": ft, "feature": RICE_FEATURE,
        }, headers=auth_headers["admin"])
        assert r.status_code == 201, r.text


# --- ALM endpoints accepted rice fields ---------------------------------

def test_alm_practice_schedule_rejects_a_rice_field(client, auth_headers):
    _make_field(client, auth_headers["admin"], "F-RICE-1", "rice_awd")
    r = client.put("/fields/F-RICE-1/practice-schedule/baseline", json={
        "crop_type": "wheat", "crop_rotation": False, "cover_crops": False,
        "intercropping": False, "tillage": True, "tillage_depth_cm": 15.0,
        "residue_removed": False, "residue_burned_kg_ha": 0.0,
        "synthetic_n_rate_kg_ha": 100.0, "organic_n_rate_kg_ha": 0.0,
        "n_fixing_species": False, "n_fixing_dry_matter_kg_ha": 0.0,
        "fuel_use_l_ha": 30.0, "crop_yield_t_ha": 3.0,
    }, headers=auth_headers["admin"])
    assert r.status_code == 422
    assert "requires 'cropland_alm_vm0042'" in r.text


def test_alm_soc_rejects_a_rice_field(client, auth_headers):
    _make_field(client, auth_headers["admin"], "F-RICE-2", "rice_awd")
    r = client.put("/fields/F-RICE-2/soc-measurements/project/t_start",
                   json={"values": [40.0, 41.0, 39.5]}, headers=auth_headers["admin"])
    assert r.status_code == 422


def test_alm_endpoints_still_work_on_an_alm_field(client, auth_headers, alm_field):
    r = client.get(f"/fields/{alm_field}/completeness", headers=auth_headers["admin"])
    assert r.status_code == 200


# --- signal-runs ran the rice SAR detector on non-SAR fields ------------

def test_signal_run_rejects_a_non_sar_field(client, auth_headers):
    """cropland_alm_vm0042 has no Sentinel-1 timeseries at all. This used to
    fall straight through to AdaptiveAWDGate. The stub_spatial_engine
    fixture raises if GEE is touched, so a regression here fails loudly
    either way."""
    _make_field(client, auth_headers["admin"], "F-ALM-SIG", "cropland_alm_vm0042")
    r = client.post("/fields/F-ALM-SIG/signal-runs", json={
        "window_start": "2024-01-01", "window_end": "2024-04-01",
    }, headers=auth_headers["admin"])
    assert r.status_code == 422
    assert "not satellite-driven" in r.text


# --- cross-tenant isolation must survive the refactor -------------------

def test_other_org_cannot_reach_a_field(client, auth_headers):
    _make_field(client, auth_headers["admin"], "F-PRIV", "rice_awd")
    r = client.get("/fields/F-PRIV", headers=auth_headers["other_org_admin"])
    assert r.status_code == 404


# --- malformed carbon body was a 500 -----------------------------------

def test_malformed_carbon_body_is_422_not_500(client, auth_headers, rice_field):
    r = client.post(f"/fields/{rice_field}/carbon-credits/preview",
                    json={"season_length_days": "not-a-number"},
                    headers=auth_headers["admin"])
    assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"


# --- engine domain-validation errors were 500s --------------------------

def test_unknown_amendment_type_is_422_not_500(client, auth_headers, rice_field):
    """CFOA_TABLE[amendment_type] was a bare dict index over 5 keys, so a
    bad value raised KeyError inside the engine and escaped as a 500. Only
    the frontend <select> prevented it."""
    r = client.post(f"/fields/{rice_field}/carbon-credits/preview", json={
        "season_length_days": 120, "area_ha": 1.0, "awd_events": 2,
        "q_n_kg_per_ha": 100.0, "preseason_category": "short",
        "baseline_amendments": [["not_a_real_amendment", 5.0]],
        "project_amendments": [["straw_shortly_before", 5.0]],
    }, headers=auth_headers["admin"])
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"
    assert "Unknown amendment_type" in r.text


def test_unknown_preseason_category_is_422_not_500(client, auth_headers, rice_field):
    r = client.post(f"/fields/{rice_field}/carbon-credits/preview", json={
        "season_length_days": 120, "area_ha": 1.0, "awd_events": 2,
        "q_n_kg_per_ha": 100.0, "preseason_category": "sideways",
        "baseline_amendments": [["straw_shortly_before", 5.0]],
        "project_amendments": [["straw_shortly_before", 5.0]],
    }, headers=auth_headers["admin"])
    assert r.status_code == 422, f"got {r.status_code}: {r.text}"


def test_valid_amendment_types_still_calculate(client, auth_headers, rice_field):
    """The ValueError->422 handler must not have swallowed the happy path."""
    r = client.post(f"/fields/{rice_field}/carbon-credits/preview", json={
        "season_length_days": 120, "area_ha": 1.0, "awd_events": 2,
        "q_n_kg_per_ha": 100.0, "preseason_category": "short",
        "baseline_amendments": [["straw_shortly_before", 5.0]],
        "project_amendments": [["compost", 3.0]],
    }, headers=auth_headers["admin"])
    assert r.status_code == 200, r.text
    assert r.json()["final_issuance"] >= 0
