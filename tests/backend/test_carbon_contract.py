"""
The load-bearing test per the plan's Part A7: proves the API is a
byte-for-byte passthrough of the existing pure calculation engines, not
just "returns 200." If CarbonResultOut's extra='allow' passthrough is
ever accidentally narrowed, or a router accidentally transforms a value,
this catches it immediately.
"""

from src.carbon_calculator import CarbonAssetEngine


def test_rice_preview_matches_direct_engine_call(client, rice_field, auth_headers):
    kwargs = dict(
        awd_events=2, season_length_days=90, area_ha=5.0,
        q_n_kg_per_ha=100.0, preseason_category="short",
        baseline_amendments=[["straw_shortly_before", 5.0]],
        project_amendments=[["straw_shortly_before", 5.0]],
    )
    expected = CarbonAssetEngine().calculate_credits(**kwargs)

    r = client.post(
        f"/fields/{rice_field}/carbon-credits/preview",
        json={
            "awd_events": kwargs["awd_events"],
            "season_length_days": kwargs["season_length_days"],
            "area_ha": kwargs["area_ha"],
            "q_n_kg_per_ha": kwargs["q_n_kg_per_ha"],
            "preseason_category": kwargs["preseason_category"],
            "baseline_amendments": kwargs["baseline_amendments"],
            "project_amendments": kwargs["project_amendments"],
        },
        headers=auth_headers["viewer"],  # viewer can preview — no write needed
    )
    assert r.status_code == 200
    actual = r.json()

    # Every key the engine returns must be present with an identical value —
    # this is the exact-equality assertion, not a subset check.
    for key, value in expected.items():
        assert key in actual, f"engine key '{key}' missing from API response"
        assert actual[key] == value, f"key '{key}': API={actual[key]!r} != engine={value!r}"


def test_rice_preview_does_not_persist(client, rice_field, auth_headers):
    r = client.post(
        f"/fields/{rice_field}/carbon-credits/preview",
        json={"awd_events": 1, "season_length_days": 90, "area_ha": 2.0},
        headers=auth_headers["viewer"],
    )
    assert r.status_code == 200

    r = client.get(f"/fields/{rice_field}/credit-history", headers=auth_headers["viewer"])
    assert r.json() == []  # preview alone must never write credit_history


def test_alm_preview_matches_direct_engine_call(client, alm_field, auth_headers):
    from src.carbon_calculator_alm import AlmCarbonEngine
    from src.database import (
        get_alm_cumulative_delta, get_alm_livestock_schedule,
        get_alm_practice_schedule, get_soc_measurements,
    )

    practice_schedule = get_alm_practice_schedule("testorg", alm_field)
    soc_measurements = get_soc_measurements("testorg", alm_field)
    livestock_schedule = get_alm_livestock_schedule("testorg", alm_field)
    prior_cumulative = get_alm_cumulative_delta("testorg", alm_field)

    expected = AlmCarbonEngine().calculate_credits(
        practice_schedule=practice_schedule, soc_measurements=soc_measurements,
        area_ha=10.0, verification_years=1.0, non_permanence_risk_pct=20.0,
        prior_cumulative_delta_co2_wp_t=prior_cumulative,
        baseline_livestock=livestock_schedule.get("baseline"),
        project_livestock=livestock_schedule.get("project"),
    )

    r = client.post(
        f"/fields/{alm_field}/carbon-credits/preview",
        json={"area_ha": 10.0, "verification_years": 1.0, "non_permanence_risk_pct": 20.0},
        headers=auth_headers["analyst"],
    )
    assert r.status_code == 200
    actual = r.json()
    for key, value in expected.items():
        assert actual[key] == value, f"key '{key}': API={actual[key]!r} != engine={value!r}"
