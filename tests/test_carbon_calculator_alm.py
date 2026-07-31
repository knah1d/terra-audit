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
    fixed scenario — catches any accidental regression in the calculation chain.

    practice_schedule has no crop_type set, so biomass burning uses the
    "Other Crops" combustion factor (0.85, the conservative fallback for an
    unspecified crop) rather than the old hardcoded universal 0.90 -
    final_issuance is correspondingly slightly lower than before this fix."""
    r = engine.calculate_credits(
        practice_schedule, soc_measurements, area_ha=5.0,
        verification_years=2.0, non_permanence_risk_pct=15.0,
    )
    assert r["ef_ndirect_used"] == 0.013
    assert r["delta_co2_soil_wp"] == pytest.approx(9.16666666666667)
    assert r["delta_co2_soil_bsl"] == pytest.approx(0.8333333333333304)
    assert r["unc_co2_pct"] == pytest.approx(64.46127345934141)
    assert r["cumulative_delta_co2_wp"] == pytest.approx(3.257716599560371)
    assert r["final_issuance"] == pytest.approx(3.5909694990109378)


def test_buffer_vcu_arithmetic_holds(engine, practice_schedule, soc_measurements):
    r = engine.calculate_credits(
        practice_schedule, soc_measurements, area_ha=5.0,
        verification_years=2.0, non_permanence_risk_pct=15.0,
    )
    assert r["vcu_er"] + r["vcu_cr"] == pytest.approx(r["final_issuance"])
    assert r["er_t"] - r["bu_er"] == pytest.approx(r["vcu_er"])
    assert r["cr_t"] - r["bu_cr"] == pytest.approx(r["vcu_cr"])


def test_other_leakage_gap_is_disclosed_not_silently_zero(engine, practice_schedule, soc_measurements):
    """VM0042 §8.4.3 makes organic-amendment-import/biomass-displacement
    leakage mandatory; this engine can't compute it, but must disclose the
    gap rather than silently returning a clean zero."""
    r = engine.calculate_credits(practice_schedule, soc_measurements, area_ha=5.0)
    assert r["other_leakage_screened"] is False
    assert r["other_leakage_gap_note"]  # non-empty


def test_production_decline_leakage_unscreened_when_no_yield_data(engine, practice_schedule, soc_measurements):
    """practice_schedule fixture has no crop_yield_t_ha entered — production-
    decline leakage can't be screened, but (unlike a real decline) must not
    block issuance either, since we simply don't know."""
    r = engine.calculate_credits(practice_schedule, soc_measurements, area_ha=5.0)
    assert r["production_decline_leakage_data_available"] is False
    assert r["production_decline_leakage_screened"] is False
    assert "production_decline_leakage_blocked" not in r
    assert r["final_issuance"] is not None


def test_production_decline_leakage_screens_clean_when_yield_maintained(engine, soc_measurements):
    """Yield-neutral practice change (common for reduced tillage/cover crops)
    -> foregone production is zero -> screened clean, not blocked."""
    practice_schedule = {
        "baseline": {"crop_yield_t_ha": 4.0},
        "project": {"crop_yield_t_ha": 4.2},  # yield maintained/improved
    }
    r = engine.calculate_credits(practice_schedule, soc_measurements, area_ha=5.0)
    assert r["production_decline_leakage_data_available"] is True
    assert r["production_decline_leakage_screened"] is True
    assert r["foregone_production_t"] == pytest.approx(0.0)
    assert r["final_issuance"] is not None


def test_production_decline_leakage_blocks_issuance_when_yield_declines(engine, soc_measurements):
    """Real production decline detected -> VMD0054 Steps 3-5 (new-land
    carbon-stock accounting) are required but not implemented -> block
    rather than fabricate a number."""
    practice_schedule = {
        "baseline": {"crop_yield_t_ha": 5.0},
        "project": {"crop_yield_t_ha": 3.5},  # yield declined
    }
    r = engine.calculate_credits(practice_schedule, soc_measurements, area_ha=5.0)
    assert r["production_decline_leakage_blocked"] is True
    assert r["final_issuance"] is None
    assert r["foregone_production_t"] == pytest.approx((5.0 - 3.5) * 5.0)
    assert "VMD0054" in r["leakage_block_reason"]


def test_combustion_factor_varies_by_crop_type(engine):
    """IPCC 2019 Refinement Vol 4 Ch 2 Table 2.6: Wheat=0.90, Rice=0.80 —
    identical residue mass burned must yield different CH4/N2O for
    different crop types, not a single wheat-derived value for everything."""
    assert engine._combustion_factor("Wheat") == 0.90
    assert engine._combustion_factor("Rice") == 0.80
    assert engine._combustion_factor("Maize") == 0.80
    assert engine._combustion_factor("Sugarcane") == 0.80
    assert engine._combustion_factor("Other Crops") == 0.85

    ch4_wheat, n2o_wheat = engine._biomass_burning(1000.0, "Wheat")
    ch4_rice, n2o_rice = engine._biomass_burning(1000.0, "Rice")
    assert ch4_wheat > ch4_rice
    assert n2o_wheat > n2o_rice
    assert ch4_wheat == pytest.approx(ch4_rice * (0.90 / 0.80))


def test_combustion_factor_falls_back_to_other_crops_for_unknown_type(engine):
    """An unrecognized/missing crop_type must not silently guess at an
    extreme value - it falls back to the middle-of-table Other Crops (0.85)."""
    assert engine._combustion_factor("Lentils") == 0.85
    assert engine._combustion_factor(None) == 0.85
    assert engine._combustion_factor("") == 0.85


def test_enteric_fermentation_uses_ipcc_ef_ent_per_head(engine):
    """Eq. 10.19/10.20 — kg CH4/head/yr straight from Table 10.11, no TAM
    conversion needed (already a per-head-per-year rate)."""
    livestock = [{"livestock_type": "cattle_nondairy", "population_head": 10, "productivity_system": "high"}]
    result = engine._enteric_fermentation(livestock)
    expected_kg_ch4 = 10 * engine.LIVESTOCK_TABLE["cattle_nondairy"]["ef_ent"]["high"]
    assert result == pytest.approx(expected_kg_ch4 * engine.GWP_CH4 / 1000.0)


def test_enteric_fermentation_skips_unknown_type_and_zero_population(engine):
    """Unrecognized livestock_type or non-positive population must be
    skipped, not guessed at with a default emission factor."""
    livestock = [
        {"livestock_type": "unicorn", "population_head": 5},
        {"livestock_type": "goat", "population_head": 0},
    ]
    assert engine._enteric_fermentation(livestock) == 0.0


def test_manure_pasture_ch4_n2o_matches_hand_calc(engine):
    """Eq. 10.22 (CH4, Table 10.14's constant PRP factor) and Ch 11 Eq. 11.5
    (N2O via F_PRP, Table 11.1's EF3PRP) computed from VS_rate/Nex_rate/TAM."""
    livestock = [{"livestock_type": "buffalo", "population_head": 4, "productivity_system": "low"}]
    ch4, n2o = engine._manure_pasture_ch4_n2o(livestock)

    params = engine.LIVESTOCK_TABLE["buffalo"]
    tam = params["tam_kg"]["low"]
    vs_annual = params["vs_rate"]["low"] * tam / 1000 * 365
    nex_annual = params["nex_rate"]["low"] * tam / 1000 * 365
    expected_ch4_tco2e = (4 * vs_annual * engine.EF_CH4_MD_PRP_G_PER_KG_VS / 1000.0) * engine.GWP_CH4 / 1000.0
    expected_n2o_tco2e = (4 * nex_annual * engine.EF3_PRP_CPP) * 44 / 28 * engine.GWP_N2O / 1000.0

    assert ch4 == pytest.approx(expected_ch4_tco2e)
    assert n2o == pytest.approx(expected_n2o_tco2e)


def test_manure_pasture_n2o_uses_so_factor_for_sheep_and_goats(engine):
    """Table 11.1 gives sheep/'other animals' (which includes goats) a
    distinct, lower EF3PRP (SO) than cattle/buffalo/poultry/pigs (CPP)."""
    livestock = [{"livestock_type": "sheep", "population_head": 20, "productivity_system": "high"}]
    _, n2o = engine._manure_pasture_ch4_n2o(livestock)

    params = engine.LIVESTOCK_TABLE["sheep"]
    tam = params["tam_kg"]["high"]
    nex_annual = params["nex_rate"]["high"] * tam / 1000 * 365
    expected = (20 * nex_annual * engine.EF3_PRP_SO) * 44 / 28 * engine.GWP_N2O / 1000.0
    assert n2o == pytest.approx(expected)


def test_livestock_defaults_to_no_op_when_omitted(engine, practice_schedule, soc_measurements):
    """Zero livestock (the default, and existing pre-Phase-3 call sites) must
    be a strict no-op — backward compatibility for every existing caller."""
    r_without = engine.calculate_credits(practice_schedule, soc_measurements, area_ha=5.0)
    r_with_empty = engine.calculate_credits(
        practice_schedule, soc_measurements, area_ha=5.0,
        baseline_livestock=[], project_livestock=[],
    )
    assert r_without["final_issuance"] == pytest.approx(r_with_empty["final_issuance"])
    assert r_without["delta_ch4_livestock"] == 0.0
    assert r_without["delta_n2o_livestock"] == 0.0


def test_livestock_reduction_increases_final_issuance(engine, practice_schedule, soc_measurements):
    """Removing baseline livestock in the project scenario is an emission
    reduction and must increase final_issuance relative to no livestock."""
    r_no_livestock = engine.calculate_credits(practice_schedule, soc_measurements, area_ha=5.0)
    r_with_livestock = engine.calculate_credits(
        practice_schedule, soc_measurements, area_ha=5.0,
        baseline_livestock=[{"livestock_type": "cattle_nondairy", "population_head": 5, "productivity_system": "low"}],
        project_livestock=[],
    )
    assert r_with_livestock["delta_ch4_livestock"] > 0
    assert r_with_livestock["final_issuance"] > r_no_livestock["final_issuance"]


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


def test_alm_end_to_end_ui_walkthrough_fixture(engine):
    """
    Locks in the first-ever real-data walkthrough of the ALM workflow through
    the actual Streamlit UI (field F-102): a wheat field switching from
    conventional tillage/full synthetic N/residue burning (baseline) to
    reduced tillage/partial organic-N substitution/cover cropping/no burning
    (project), with lab-measured SOC samples. Exercised via app.py's Practice
    & Soil Data and Carbon Ledger tabs (registration, save, calculate,
    export) with no exceptions before this fixture was written.
    """
    practice_schedule = {
        "baseline": {
            "crop_type": "Wheat", "tillage": 1, "tillage_depth_cm": 20.0,
            "residue_removed": 0, "residue_burned_kg_ha": 500.0,
            "synthetic_n_rate_kg_ha": 120.0, "organic_n_rate_kg_ha": 0.0,
            "n_fixing_species": 0, "n_fixing_dry_matter_kg_ha": 0.0,
            "fuel_use_l_ha": 40.0,
        },
        "project": {
            "crop_type": "Wheat", "tillage": 0, "tillage_depth_cm": 0.0,
            "residue_removed": 0, "residue_burned_kg_ha": 0.0,
            "synthetic_n_rate_kg_ha": 80.0, "organic_n_rate_kg_ha": 20.0,
            "n_fixing_species": 1, "n_fixing_dry_matter_kg_ha": 1000.0,
            "fuel_use_l_ha": 25.0,
        },
    }
    soc_measurements = {
        ("project", "t_start"): [30.0, 32.0, 29.0],
        ("project", "t_final"): [34.0, 35.0, 33.0],
        ("control", "t_start"): [30.0, 31.0, 29.0],
        ("control", "t_final"): [30.0, 31.0, 30.0],
    }
    r = engine.calculate_credits(
        practice_schedule, soc_measurements, area_ha=31.837,
        verification_years=1.0, non_permanence_risk_pct=20.0,
    )
    assert r["er_t"] == pytest.approx(2.6024541650714172)
    assert r["cr_t"] == pytest.approx(89.0212203072913)
    assert r["unc_co2_pct"] == pytest.approx(16.115318364835353)
    assert r["final_issuance"] == pytest.approx(73.81943041090446)
    assert r["other_leakage_screened"] is False
    assert r["production_decline_leakage_data_available"] is False  # fixture predates crop_yield_t_ha
    assert r["cadence_compliant"] is True


def test_alm_livestock_ui_walkthrough_fixture(engine):
    """
    Locks in the first-ever real-data walkthrough of VM0042's integrated
    crop-livestock feature through the actual Streamlit UI (field F-102):
    the same wheat baseline/project practice schedule as
    test_alm_end_to_end_ui_walkthrough_fixture, with 5 non-dairy cattle
    (low productivity) grazing in the baseline scenario and none in the
    project scenario (a rotational-grazing-to-cropland-only practice
    change). Exercised via app.py's Practice & Soil Data tab (enabling the
    livestock checkbox, entering head count/productivity system, saving)
    and Carbon Ledger tab (calculate, export PDF/JSON/CSV) with no
    exceptions before this fixture was written.
    """
    practice_schedule = {
        "baseline": {
            "crop_type": "Wheat", "tillage": 1, "tillage_depth_cm": 20.0,
            "residue_removed": 0, "residue_burned_kg_ha": 500.0,
            "synthetic_n_rate_kg_ha": 120.0, "organic_n_rate_kg_ha": 0.0,
            "n_fixing_species": 0, "n_fixing_dry_matter_kg_ha": 0.0,
            "fuel_use_l_ha": 40.0,
        },
        "project": {
            "crop_type": "Wheat", "tillage": 0, "tillage_depth_cm": 0.0,
            "residue_removed": 0, "residue_burned_kg_ha": 0.0,
            "synthetic_n_rate_kg_ha": 80.0, "organic_n_rate_kg_ha": 20.0,
            "n_fixing_species": 1, "n_fixing_dry_matter_kg_ha": 1000.0,
            "fuel_use_l_ha": 25.0,
        },
    }
    soc_measurements = {
        ("project", "t_start"): [30.0, 32.0, 29.0],
        ("project", "t_final"): [34.0, 35.0, 33.0],
        ("control", "t_start"): [30.0, 31.0, 29.0],
        ("control", "t_final"): [30.0, 31.0, 30.0],
    }
    r = engine.calculate_credits(
        practice_schedule, soc_measurements, area_ha=31.837,
        verification_years=1.0, non_permanence_risk_pct=20.0,
        baseline_livestock=[{"livestock_type": "cattle_nondairy", "population_head": 5, "productivity_system": "low"}],
        project_livestock=[],
    )
    assert r["ch4_ent_bsl"] == pytest.approx(6.58)
    assert r["ch4_ent_wp"] == pytest.approx(0.0)
    assert r["ch4_manure_bsl"] == pytest.approx(0.08682912)
    assert r["n2o_manure_bsl"] == pytest.approx(0.4412152328571428)
    assert r["er_t"] == pytest.approx(9.71049851792856)
    assert r["cr_t"] == pytest.approx(89.0212203072913)  # SOC term unaffected by livestock
    assert r["final_issuance"] == pytest.approx(80.9274747637616)
