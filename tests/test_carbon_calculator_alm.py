"""
Regression tests for AlmCarbonEngine (VM0042 cropland-ALM credit calculation).
"""

import pytest

from src.carbon_calculator_alm import AlmCarbonEngine


@pytest.fixture
def engine():
    return AlmCarbonEngine()


@pytest.fixture
def practice_schedule():
    return {
        "baseline": {
            "synthetic_n_rate_kg_ha": 120, "organic_n_rate_kg_ha": 0,
            "residue_burned_kg_ha": 500, "fuel_use_l_ha": 40,
        },
        "project": {
            "synthetic_n_rate_kg_ha": 80, "organic_n_rate_kg_ha": 20,
            "residue_burned_kg_ha": 0, "fuel_use_l_ha": 25,
        },
    }


@pytest.fixture
def soc_measurements():
    return {
        ("project", "t_start"): [30, 32, 29],
        ("project", "t_final"): [34, 35, 33],
        ("control", "t_start"): [30, 31, 29],
        ("control", "t_final"): [30, 31, 30],
    }


def test_diesel_ef_matches_vm0042_parameter_table(engine):
    """Regression guard: VM0042 p.102 quotes diesel = 0.002886 t CO2e/L directly;
    the previous 0.00268 was a ~7.6% understatement."""
    assert engine.EF_CO2_DIESEL_T_PER_L == 0.002886
    assert engine._fossil_fuel_co2(1000) == pytest.approx(2.886)


def test_conservative_ef_direction(engine):
    assert engine._conservative_ef_ndirect(baseline_n_t=10, project_n_t=8) == engine.EF_NDIRECT_LOW
    assert engine._conservative_ef_ndirect(baseline_n_t=10, project_n_t=12) == engine.EF_NDIRECT_HIGH
    assert engine._conservative_ef_ndirect(baseline_n_t=10, project_n_t=10) == engine.EF_NDIRECT_LOW


def test_soc_not_ready_falls_back_to_zero_with_full_uncertainty(engine, practice_schedule):
    thin_soc = {
        ("project", "t_start"): [30, 32],  # only 2 samples — below MIN_SOC_SAMPLES
        ("project", "t_final"): [34, 35, 33],
        ("control", "t_start"): [30, 31, 29],
        ("control", "t_final"): [30, 31, 30],
    }
    r = engine.calculate_credits(practice_schedule, thin_soc, area_ha=5.0)
    assert r["soc_ready"] is False
    assert r["delta_co2_soil_wp"] == 0.0
    assert r["delta_co2_soil_bsl"] == 0.0
    assert r["unc_co2_pct"] == 100.0


def test_full_scenario_golden_values(engine, practice_schedule, soc_measurements):
    """Characterization test locking in the corrected engine's output for a
    fixed scenario — catches any accidental regression in the calculation chain."""
    r = engine.calculate_credits(
        practice_schedule, soc_measurements, area_ha=5.0,
        verification_years=2.0, non_permanence_risk_pct=15.0,
    )
    assert r["ef_ndirect_used"] == 0.013
    assert r["delta_co2_soil_wp"] == pytest.approx(9.16666666666667)
    assert r["delta_co2_soil_bsl"] == pytest.approx(0.8333333333333304)
    assert r["unc_co2_pct"] == pytest.approx(64.46127345934141)
    assert r["cumulative_delta_co2_wp"] == pytest.approx(3.257716599560371)
    assert r["final_issuance"] == pytest.approx(3.6027382490109376)


def test_buffer_vcu_arithmetic_holds(engine, practice_schedule, soc_measurements):
    r = engine.calculate_credits(
        practice_schedule, soc_measurements, area_ha=5.0,
        verification_years=2.0, non_permanence_risk_pct=15.0,
    )
    assert r["vcu_er"] + r["vcu_cr"] == pytest.approx(r["final_issuance"])
    assert r["er_t"] - r["bu_er"] == pytest.approx(r["vcu_er"])
    assert r["cr_t"] - r["bu_cr"] == pytest.approx(r["vcu_cr"])


def test_leakage_gap_is_disclosed_not_silently_zero(engine, practice_schedule, soc_measurements):
    """VM0042 §8.4.3 makes production-decline leakage mandatory; this engine
    can't compute it (no VMD0054), but must disclose the gap rather than
    silently returning a clean zero."""
    r = engine.calculate_credits(practice_schedule, soc_measurements, area_ha=5.0)
    assert r["leakage_screened"] is False
    assert r["leakage_gap_note"]  # non-empty


def test_cumulative_indicator_persists_across_verification_periods(engine, practice_schedule, soc_measurements):
    r1 = engine.calculate_credits(practice_schedule, soc_measurements, area_ha=5.0, verification_years=2.0)
    r2 = engine.calculate_credits(
        practice_schedule, soc_measurements, area_ha=5.0, verification_years=2.0,
        prior_cumulative_delta_co2_wp_t=r1["cumulative_delta_co2_wp"],
    )
    assert r2["cumulative_delta_co2_wp"] == pytest.approx(r1["cumulative_delta_co2_wp"] * 2)

    # A naive single-period-only read (the old bug) would have classified this
    # scenario identically every call; the cumulative total must actually grow.
    assert r2["cumulative_delta_co2_wp"] > r1["cumulative_delta_co2_wp"]


def test_cumulative_indicator_can_flip_classification(engine):
    """Construct a case where the current period is positive but the prior
    cumulative deficit keeps the running total negative — I(dCO2wp) must use
    the cumulative total, not the current period alone."""
    schedule = {"baseline": {}, "project": {}}
    soc = {
        ("project", "t_start"): [40, 41, 39],
        ("project", "t_final"): [41, 42, 40],  # small positive current-period gain
        ("control", "t_start"): [30, 31, 29],
        ("control", "t_final"): [30, 31, 30],
    }
    r = engine.calculate_credits(
        schedule, soc, area_ha=1.0, verification_years=1.0,
        prior_cumulative_delta_co2_wp_t=-100.0,  # large prior deficit
    )
    assert r["cumulative_delta_co2_wp"] < 0
    assert r["cr_t"] == 0.0  # I(dCO2wp) must be 0 -> no removals credited


@pytest.mark.parametrize("years,expected", [(1.0, True), (5.0, True), (6.0, False), (10.0, False)])
def test_remeasurement_cadence_validation(engine, practice_schedule, soc_measurements, years, expected):
    r = engine.calculate_credits(practice_schedule, soc_measurements, area_ha=5.0, verification_years=years)
    assert r["cadence_compliant"] is expected
