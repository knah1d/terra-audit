class CarbonAssetEngine:
    """
    Implements Verra VM0051 v1.0 QA3 (Default Emission Factors) pathway for
    converting satellite-verified AWD events into verified carbon credits.

    Covers (this implementation):
      - CH4 from soil methanogenesis (§8.2.3, Eqs. 6-8)
      - N2O project emission from irrigation regime change (§8.3.2, Eq. 25)
      - QA3 flat 15% uncertainty deduction (§8.6.3)
      - Leakage de minimis screen (§8.4)

    Explicitly excluded (assumed zero / de minimis, documented per §8.4):
      - CO2 from fossil fuels / liming (§8.2.1-8.2.2)
      - CH4 / N2O from biomass burning (§8.2.5-8.2.7)
      - N2O from baseline nitrogen fertilizers (§8.2.6) — no fertilizer
        change between baseline and project scenario assumed
      - Leakage from organic amendments / yield decline (§8.4.1-8.4.2)
    """

    # VM0051 §8.2.3 — Water scaling factors (IPCC 2019 Refinement, Table 5.12)
    SF_CONTINUOUS_FLOODING = 1.00   # 0 drydowns — no reduction
    SF_SINGLE_AERATION     = 0.71   # 1 drydown  — 29% CH4 reduction
    SF_TRUE_AWD            = 0.52   # >=2 drydowns — 48% CH4 reduction

    # VM0051 §8.6.3 — QA3 flat deduction for projects < 60,000 tCO2e/yr
    UNC_QA3_DEFAULT = 0.15

    # VM0051 §8.3.2, Eq. 25 — N2O correction factor for AWD drying periods
    # CF_N2O derived from IPCC 2019 Table 11.1 (see VM0051 footnote 21)
    CF_N2O  = 0.00314  # kg N2O / kg N-input
    GWP_N2O = 265      # IPCC AR5 GWP100 for N2O

    def __init__(self, ef_c: float = 1.4, gwp_ch4: int = 28):
        self.ef_c    = ef_c
        self.gwp_ch4 = gwp_ch4

    def _water_scaling_factor(self, awd_events: int) -> float:
        if awd_events == 0:
            return self.SF_CONTINUOUS_FLOODING
        elif awd_events == 1:
            return self.SF_SINGLE_AERATION
        else:
            return self.SF_TRUE_AWD

    def _n2o_irrigation_penalty(self, q_n_kg_per_ha: float, area_ha: float) -> float:
        """
        VM0051 §8.3.2, Eq. 25 — N2O project emission from AWD drying periods.
        PE_Red-Irri = Q_N x A x CF_N2O x 10^-3 x GWP_N2O  (tCO2e)
        Applied only when irrigation regime changes (awd_events > 0).
        """
        return q_n_kg_per_ha * area_ha * self.CF_N2O * 1e-3 * self.GWP_N2O

    def calculate_credits(
        self,
        awd_events: int,
        season_length_days: int,
        area_ha: float,
        q_n_kg_per_ha: float = 100.0,
    ) -> dict:
        """
        Execute the full VM0051 QA3 calculation chain.

        Net reductions follow Eq. 29 (simplified for AWD-only, no straw burning):
          ER = DCH4_soil x (1 - UNC_CH4) - PE_Red-Irri

        Returns a dict with all intermediate values for audit trail rendering.
        """
        sf_w_project = self._water_scaling_factor(awd_events)

        # Step 1 — Baseline CH4 (Eq. 8, continuous flooding, SF_w = 1.0)
        e_baseline = self.ef_c * 1.0 * season_length_days * area_ha

        # Step 2 — Project CH4 (Eq. 8 with project SF_w)
        e_project  = self.ef_c * sf_w_project * season_length_days * area_ha

        # Step 3 — Gross CH4 avoided (kg CH4)
        delta_e_ch4 = e_baseline - e_project

        # Step 4 — Convert to tCO2e (IPCC AR5 GWP100)
        delta_e_co2e = (delta_e_ch4 * self.gwp_ch4) / 1000.0

        # Step 5 — QA3 flat 15% uncertainty deduction (§8.6.3)
        unc_tco2e     = delta_e_co2e * self.UNC_QA3_DEFAULT
        ch4_after_unc = delta_e_co2e - unc_tco2e

        # Step 6 — N2O project emission from irrigation change (Eq. 25)
        # Only when water regime changes (drying periods introduced)
        pe_n2o = (
            self._n2o_irrigation_penalty(q_n_kg_per_ha, area_ha)
            if awd_events > 0 else 0.0
        )

        # Step 7 — Leakage de minimis screen (§8.4)
        # If N2O penalty < 5% of gross CH4 reduction, may be treated as de minimis
        leakage_pct        = (pe_n2o / delta_e_co2e * 100.0) if delta_e_co2e > 0 else 0.0
        leakage_de_minimis = leakage_pct < 5.0

        # Step 8 — Net reductions per Eq. 29 (CH4 soil term only)
        final_issuance = max(0.0, ch4_after_unc - pe_n2o)

        return {
            "sf_w_project":       sf_w_project,
            "e_baseline":         e_baseline,
            "e_project":          e_project,
            "delta_e_ch4":        delta_e_ch4,
            "delta_e_co2e":       delta_e_co2e,
            "unc_deduction_pct":  self.UNC_QA3_DEFAULT * 100,
            "unc_tco2e":          unc_tco2e,
            "ch4_after_unc":      ch4_after_unc,
            "pe_n2o_tco2e":       pe_n2o,
            "q_n_kg_per_ha":      q_n_kg_per_ha,
            "leakage_pct":        round(leakage_pct, 2),
            "leakage_de_minimis": leakage_de_minimis,
            "final_issuance":     final_issuance,
            # Legacy key retained for report_generator compatibility
            "p_uncertainty":      self.UNC_QA3_DEFAULT,
            "confidence_pct":     None,
        }
