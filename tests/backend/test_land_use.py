from datetime import date, timedelta

import pandas as pd

from src.signals.land_use import classify_land_use
from tests.backend.conftest import RICE_FEATURE

CROPLAND = {40: 0.9, 50: 0.1}


def _series(vh_values, start=date(2025, 1, 1), step_days=12):
    return pd.DataFrame({
        "date": [(start + timedelta(days=i * step_days)).isoformat() for i in range(len(vh_values))],
        "vh": vh_values,
    })


def _classify(fractions, df):
    return classify_land_use(fractions, df, "2025-01-01", "2026-01-01")


def test_flood_then_growth_is_rice_paddy():
    # flooded at transplanting (~-23 dB), canopy rises to ~-14 dB, then stays dry
    vh = [-17, -23, -22, -19, -16, -14, -14, -15, -16, -16, -16, -17, -16, -17, -16]
    land_use, evidence = _classify(CROPLAND, _series(vh))
    assert land_use == "rice_paddy"
    assert len(evidence["rice_seasons"]) == 1
    assert evidence["rice_seasons"][0]["flood_date"] == "2025-01-13"


def test_two_separate_floods_are_two_seasons():
    season = [-23, -21, -18, -15, -14, -15, -16, -16, -16, -16]
    land_use, evidence = _classify(CROPLAND, _series(season * 2))
    assert land_use == "rice_paddy"
    assert len(evidence["rice_seasons"]) == 2


def test_cropland_without_flooding_is_upland():
    vh = [-17, -16, -15, -15, -14, -15, -16, -17, -17, -16, -15, -16]
    land_use, evidence = _classify(CROPLAND, _series(vh))
    assert land_use == "upland_cropland"
    assert evidence["rice_seasons"] == []


def test_persistent_water_without_growth_is_not_rice():
    vh = [-24, -25, -24, -23, -24, -25, -24, -24, -23, -24, -25, -24]
    land_use, _ = _classify({40: 0.6, 80: 0.4}, _series(vh))
    assert land_use == "upland_cropland"


def test_mostly_built_up_is_non_cropland():
    land_use, evidence = _classify({50: 0.8, 40: 0.2}, pd.DataFrame())
    assert land_use == "non_cropland"
    assert evidence["dominant_land_cover"] == "built-up"


def test_too_few_observations_is_undecided():
    land_use, evidence = _classify(CROPLAND, _series([-23, -15, -14]))
    assert land_use is None
    assert evidence["observations"] == 3


def test_no_worldcover_pixels_is_undecided():
    land_use, _ = _classify({}, pd.DataFrame())
    assert land_use is None


def _payload(**extra):
    return {"field_id": "F-LU", "name": "LU", "district": "", "field_type": "rice_awd",
            "feature": RICE_FEATURE, **extra}


def test_create_records_detected_source_when_matching(client, auth_headers, monkeypatch):
    monkeypatch.setattr("backend.routers.fields.detect_land_use",
                        lambda engine, geo: ("rice_paddy", {"summary": "flooded"}))
    r = client.post("/fields", json=_payload(land_use="rice_paddy"), headers=auth_headers["admin"])
    assert r.status_code == 201, r.text
    body = client.get("/fields/F-LU", headers=auth_headers["admin"]).json()
    assert body["land_use"] == "rice_paddy"
    assert body["land_use_source"] == "detected"
    assert body["land_use_evidence"] == {"summary": "flooded"}


def test_create_records_manual_source_on_override(client, auth_headers, monkeypatch):
    """A client can't claim 'detected' for a value detection didn't produce."""
    monkeypatch.setattr("backend.routers.fields.detect_land_use",
                        lambda engine, geo: ("rice_paddy", {"summary": "flooded"}))
    r = client.post("/fields", json=_payload(land_use="upland_cropland"),
                    headers=auth_headers["admin"])
    assert r.json()["land_use"] == "upland_cropland"
    assert r.json()["land_use_source"] == "manual"


def test_create_without_land_use_and_unknown_value(client, auth_headers):
    r = client.post("/fields", json=_payload(land_use="orchard"), headers=auth_headers["admin"])
    assert r.status_code == 422

    r = client.post("/fields", json=_payload(), headers=auth_headers["admin"])
    assert r.status_code == 201
    assert r.json()["land_use"] is None and r.json()["land_use_source"] is None


def test_detection_failure_falls_back_to_manual(client, auth_headers):
    # the conftest stub engine has no land_cover_fractions -> detection raises
    r = client.post("/fields", json=_payload(land_use="rice_paddy"), headers=auth_headers["admin"])
    assert r.status_code == 201
    assert r.json()["land_use_source"] == "manual"


def test_edit_changes_land_use_only_when_sent(client, rice_field, auth_headers):
    r = client.patch(f"/fields/{rice_field}", json={"name": "x", "land_use": "rice_rotation"},
                     headers=auth_headers["analyst"])
    assert r.json()["land_use"] == "rice_rotation"
    assert r.json()["land_use_source"] == "manual"

    r = client.patch(f"/fields/{rice_field}", json={"name": "y"}, headers=auth_headers["analyst"])
    assert r.json()["land_use"] == "rice_rotation"


def test_land_use_endpoint(client, auth_headers, monkeypatch):
    monkeypatch.setattr("backend.routers.fields.detect_land_use",
                        lambda engine, geo: ("upland_cropland", {"summary": "dry"}))
    r = client.post("/geometry/land-use", json=RICE_FEATURE, headers=auth_headers["admin"])
    assert r.status_code == 200
    assert r.json() == {"land_use": "upland_cropland", "evidence": {"summary": "dry"}}

    def boom(engine, geo):
        raise RuntimeError("quota")
    monkeypatch.setattr("backend.routers.fields.detect_land_use", boom)
    r = client.post("/geometry/land-use", json=RICE_FEATURE, headers=auth_headers["admin"])
    assert r.status_code == 502
