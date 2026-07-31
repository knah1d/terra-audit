"""
Regression tests for CarbonAssetEngine (VM0051 rice-AWD credit calculation).

GWP constants are referenced symbolically (engine.gwp_ch4 / engine.GWP_N2O)
rather than hardcoded, so a future AR5->AR6 constant change doesn't require
rewriting every golden value here.
"""

import pytest

from src.carbon_calculator import CarbonAssetEngine


@pytest.fixture
def engine():
    return CarbonAssetEngine()


def test_zero_awd_events_yields_no_reduction(engine):
    r = engine.calculate_credits(awd_events=0, season_length_days=120, area_ha=1.0)
    assert r["sf_w_project"] == engine.SF_CONTINUOUS_FLOODING
    assert r["e_baseline"] == pytest.approx(r["e_project"])
    assert r["delta_e_ch4"] == pytest.approx(0.0)
    assert r["final_issuance"] == pytest.approx(0.0)


def test_single_drydown_uses_single_aeration_factor(engine):
    r = engine.calculate_credits(awd_events=1, season_length_days=120, area_ha=1.0, q_n_kg_per_ha=100.0)
    assert r["sf_w_project"] == engine.SF_SINGLE_AERATION == 0.71
    assert r["pe_n2o_tco2e"] > 0.0
    assert r["delta_e_ch4"] > 0.0


def test_true_awd_uses_corrected_scaling_factor(engine):
    """Regression guard: SF_TRUE_AWD must be 0.55 (IPCC 2019, 'multiple drainage
    periods'), not the previously-hardcoded 0.52."""
    r = engine.calculate_credits(awd_events=2, season_length_days=120, area_ha=1.0)
    assert engine.SF_TRUE_AWD == 0.55
    assert r["sf_w_project"] == 0.55


def test_default_organic_amendment_scaling_matches_footnote_16(engine):
    """VM0051 §8.2.3 footnote 16: baseline default is 5 t/ha straw, Table 5.14's
    reference case (CFOA=1.00, straw incorporated shortly before cultivation)."""
    r = engine.calculate_credits(awd_events=0, season_length_days=120, area_ha=1.0)
    expected_sc_o = (1 + 5.0 * 1.00) ** 0.59
    assert r["sc_organic_bsl"] == pytest.approx(expected_sc_o)
    # No explicit project_amendments given -> mirrors baseline (no assumed change)
    assert r["sc_organic_wp"] == pytest.approx(expected_sc_o)


def test_preseason_category_short_vs_long(engine):
    r_short = engine.calculate_credits(awd_events=0, season_length_days=120, area_ha=1.0, preseason_category="short")
    r_long  = engine.calculate_credits(awd_events=0, season_length_days=120, area_ha=1.0, preseason_category="long")
    assert r_short["sc_preseason"] == 1.00
    assert r_long["sc_preseason"] == 0.89
    assert r_long["e_baseline"] < r_short["e_baseline"]


def test_custom_amendments_applied_per_scenario(engine):
    r = engine.calculate_credits(
        awd_events=2, season_length_days=120, area_ha=1.0,
        baseline_amendments=(("straw_shortly_before", 5.0),),
        project_amendments=(("straw_long_before", 0.0),),
    )
    assert r["sc_organic_bsl"] == pytest.approx((1 + 5.0 * 1.00) ** 0.59)
    assert r["sc_organic_wp"] == pytest.approx(1.0)  # zero-rate amendment -> SC_o = 1


def test_qa3_project_size_gate_blocks_oversized_projects(engine):
    """§8.6.3: the flat 15% deduction is only valid at/below the 60,000 tCO2e/yr
    gate. Above it, this engine must block rather than silently misapply it."""
    r = engine.calculate_credits(awd_events=2, season_length_days=120, area_ha=500_000.0, q_n_kg_per_ha=0.0)
    assert r["qa3_pathway_valid"] is False
    assert r["final_issuance"] is None
    assert "60,000" in r["qa3_block_reason"] or "60000" in r["qa3_block_reason"]


def test_qa3_gate_allows_typical_smallholder_field(engine):
    r = engine.calculate_credits(awd_events=2, season_length_days=120, area_ha=1.0)
    assert r["qa3_pathway_valid"] is True
    assert r["final_issuance"] is not None


def test_zero_n_input_yields_zero_n2o_penalty(engine):
    r = engine.calculate_credits(awd_events=2, season_length_days=120, area_ha=1.0, q_n_kg_per_ha=0.0)
    assert r["pe_n2o_tco2e"] == pytest.approx(0.0)


def test_zero_area_does_not_raise(engine):
    r = engine.calculate_credits(awd_events=2, season_length_days=120, area_ha=0.0)
    assert r["final_issuance"] == pytest.approx(0.0)


def test_n2o_penalty_uses_gwp_n2o_and_cf_n2o_constants(engine):
    """Eq. 25 structural check, referencing constants symbolically."""
    q_n, area = 100.0, 2.0
    r = engine.calculate_credits(awd_events=1, season_length_days=100, area_ha=area, q_n_kg_per_ha=q_n)
    expected = q_n * area * engine.CF_N2O * 1e-3 * engine.GWP_N2O
    assert r["pe_n2o_tco2e"] == pytest.approx(expected)


def test_ef_c_matches_ipcc_2019_table_5_11_south_asia(engine):
    """Regression guard: EF_c must be 0.85 kg CH4/ha/day (IPCC 2019 Refinement
    Table 5.11, South Asia regional default), not the previously-hardcoded
    1.4 - which appears nowhere in Table 5.11 and inflated final_issuance by
    ~1.65x."""
    assert engine.ef_c == 0.85
    r = engine.calculate_credits(awd_events=2, season_length_days=120, area_ha=1.0)
    assert r["ef_c_used"] == 0.85


def test_final_issuance_uses_symbolic_ch4_gwp(engine):
    """delta_e_co2e must scale with engine.gwp_ch4, not a hardcoded 28, so a
    future GWP vintage change doesn't require rewriting this test."""
    r = engine.calculate_credits(awd_events=2, season_length_days=120, area_ha=1.0)
    expected_co2e = (r["delta_e_ch4"] * engine.gwp_ch4) / 1000.0
    assert r["delta_e_co2e"] == pytest.approx(expected_co2e)
