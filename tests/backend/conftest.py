"""
Shared fixtures for backend contract/integration tests
(.claude/plans/misty-growing-yao.md Part A7).

Each test gets a fresh, isolated throwaway SQLite file — src.persistence.database's
module-level engine singleton is forcibly reset per test so DATABASE_URL
changes actually take effect (it's normally created once per process,
which would otherwise leak state between tests or point at the real
project_store.db). SpatialDataEngine/GEE is never constructed in these
tests (monkeypatched to a stub) — consistent with the plan's own
testing philosophy: none of the contract/role/idempotency tests need a
real Earth Engine call, and requiring GEE credentials in CI isn't
something to introduce for this test suite.
"""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Points src.persistence.database at a fresh temp SQLite file for the duration of
    one test, then restores the module's engine singleton afterward so
    other test files aren't left pointed at a now-deleted temp file.

    The engine is still a module-level singleton created on first use, so
    it has to be reset for a new DATABASE_URL to take effect. What this
    no longer has to work around is src.persistence.database running initialize_database()
    as an import-time side effect — the engine used to be built (and DDL
    run against the developer's real project_store.db) simply by importing
    the module, before any fixture could redirect it.
    """
    import src.persistence.database as db

    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    prior_engine, prior_initialized = db._ENGINE, db._DB_INITIALIZED
    db._ENGINE = None
    db._DB_INITIALIZED = False
    db.initialize_database()
    try:
        yield db
    finally:
        db._ENGINE = prior_engine
        db._DB_INITIALIZED = prior_initialized


@pytest.fixture()
def stub_spatial_engine(monkeypatch):
    """Replaces SpatialDataEngine with a stub that raises if
    extract_clean_timeseries is ever actually called — proves the
    cache-hit signal-run path never touches GEE, and lets every other
    test's app-startup lifespan succeed without real Earth Engine
    credentials."""
    class _StubEngine:
        def __init__(self):
            pass

        def extract_clean_timeseries(self, *a, **kw):
            raise AssertionError(
                "extract_clean_timeseries() was called — this test's path "
                "should never touch GEE (cache-hit fast path expected)."
            )

    monkeypatch.setattr("src.signals.earth_engine.SpatialDataEngine", _StubEngine)
    return _StubEngine


@pytest.fixture()
def client(isolated_db, stub_spatial_engine):
    from backend.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def seeded_users(isolated_db):
    """Creates one admin, one analyst, one viewer in org 'testorg', plus
    a second org 'otherorg' admin — for cross-tenant isolation tests."""
    from src.accounts.auth import create_org_user

    users = {
        "admin": create_org_user("testorg", "admin@test.local", "AdminPass123!", "admin"),
        "analyst": create_org_user("testorg", "analyst@test.local", "AnalystPass123!", "analyst"),
        "viewer": create_org_user("testorg", "viewer@test.local", "ViewerPass123!", "viewer"),
        "other_org_admin": create_org_user("otherorg", "otheradmin@test.local", "OtherPass123!", "admin"),
    }
    return users


@pytest.fixture()
def tokens(seeded_users):
    """Mints JWTs directly (bypassing the /auth/login HTTP round-trip) for
    speed in tests that aren't specifically testing login itself."""
    from backend.config import JWT_EXPIRE_MINUTES, JWT_SECRET
    from backend.security import create_access_token
    from src.accounts.auth import get_user_by_email

    emails = {
        "admin": "admin@test.local", "analyst": "analyst@test.local",
        "viewer": "viewer@test.local", "other_org_admin": "otheradmin@test.local",
    }
    result = {}
    for role, email in emails.items():
        user = get_user_by_email(email)
        result[role] = create_access_token(user, JWT_SECRET, JWT_EXPIRE_MINUTES)
    return result


@pytest.fixture()
def auth_headers(tokens):
    return {role: {"Authorization": f"Bearer {tok}"} for role, tok in tokens.items()}


RICE_FEATURE = {
    "type": "Feature", "properties": {},
    "geometry": {"type": "Polygon", "coordinates": [[
        [90.0, 23.0], [90.01, 23.0], [90.01, 23.01], [90.0, 23.01], [90.0, 23.0],
    ]]},
}


@pytest.fixture()
def rice_field(client, auth_headers):
    """Registers one rice_awd field as the admin user, returns its field_id."""
    r = client.post("/fields", json={
        "field_id": "F-TEST-RICE", "name": "Test Rice Field", "district": "Test District",
        "field_type": "rice_awd", "feature": RICE_FEATURE,
    }, headers=auth_headers["admin"])
    assert r.status_code == 201, r.text
    return "F-TEST-RICE"


@pytest.fixture()
def alm_field(client, auth_headers):
    """Registers one cropland_alm_vm0042 field with a complete practice
    schedule + SOC measurements, returns its field_id."""
    r = client.post("/fields", json={
        "field_id": "F-TEST-ALM", "name": "Test ALM Field", "district": "Test District",
        "field_type": "cropland_alm_vm0042", "feature": RICE_FEATURE,
    }, headers=auth_headers["admin"])
    assert r.status_code == 201, r.text

    practice = {
        "crop_type": "wheat", "crop_rotation": False, "cover_crops": False,
        "intercropping": False, "tillage": True, "tillage_depth_cm": 15.0,
        "residue_removed": False, "residue_burned_kg_ha": 0.0,
        "synthetic_n_rate_kg_ha": 100.0, "organic_n_rate_kg_ha": 0.0,
        "n_fixing_species": False, "n_fixing_dry_matter_kg_ha": 0.0,
        "fuel_use_l_ha": 30.0, "crop_yield_t_ha": 3.0,
    }
    for scenario in ("baseline", "project"):
        r = client.put(f"/fields/F-TEST-ALM/practice-schedule/{scenario}",
                        json=practice, headers=auth_headers["admin"])
        assert r.status_code == 200, r.text

    # project SOC rises t_start->t_final; control stays flat — a genuine,
    # non-zero measurable stock-change delta, not an artifact of identical
    # values everywhere (an earlier version of this fixture used the same
    # numbers for every cell, which legitimately computed to a zero delta
    # and made the idempotency-bump test's "before != after" assertion
    # meaningless rather than actually broken).
    soc_values = {
        ("project", "t_start"): [40.0, 41.0, 39.5],
        ("project", "t_final"): [48.0, 49.0, 47.5],
        ("control", "t_start"): [40.0, 41.0, 39.5],
        ("control", "t_final"): [40.2, 41.1, 39.6],
    }
    for (site_type, timepoint), values in soc_values.items():
        r = client.put(
            f"/fields/F-TEST-ALM/soc-measurements/{site_type}/{timepoint}",
            json={"values": values}, headers=auth_headers["admin"],
        )
        assert r.status_code == 200, r.text

    return "F-TEST-ALM"


@pytest.fixture()
def alm_calculation_context(client, alm_field, auth_headers, seeded_users, leakage_case):
    """Current ALM workflow with real scoped production/assessment rows.

    It deliberately leaves expert/readiness decisions outstanding: an
    internal draft is not an external verified event or an issued credit.
    """
    from src.persistence import database as db
    from src.projects import repository as projects
    from src.evidence import production

    actor = seeded_users["admin"]
    project_id = projects.create_project("testorg", "Regression project", "", "", None, None, "active", actor)
    projects.assign_field_to_project("testorg", project_id, alm_field, "2020-01-01", actor)
    season = client.post(f"/fields/{alm_field}/crop-seasons", headers=auth_headers["admin"], json={
        "name": "Wheat 2026", "crops": ["wheat"], "start_date": "2026-01-01", "end_date": "2026-12-31",
    })
    assert season.status_code == 201, season.text
    case = leakage_case(area_ha=db.get_field("testorg", alm_field)["area_ha"],
                        field_id=alm_field, project_id=project_id)
    for record in case["evidence"]["production_records"]:
        production.create_production_record("testorg", alm_field, **{
            k: record[k] for k in ("commodity", "period_type", "period_label", "crop_cycle_index",
                "harvest_start_date", "harvest_end_date", "harvested_area_ha", "area_share_pct",
                "production_status", "production_quantity", "unit", "evidence_ref", "notes")
        }, created_by=actor)
    production.save_leakage_assessment("testorg", alm_field, case["evidence"]["assessment"]["payload"], actor)
    return {"project_id": project_id, "accounting_pathway": "vm0042_alm",
            "season_ids": [season.json()["id"]], "monitoring_period_start": "2026-01-01",
            "monitoring_period_end": "2026-12-31",
            "engine_inputs": {"verification_years": 1.0, "non_permanence_risk_pct": 20.0}}
