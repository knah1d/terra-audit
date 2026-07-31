class CarbonAssetEngine:
    """
    Implements Verra VM0051 v1.0 QA3 (Default Emission Factors) pathway for
    converting satellite-verified AWD events into verified carbon credits.

    Covers (this implementation):
      - CH4 from soil methanogenesis, including water-regime (Table 5.12),
        pre-season water-regime (Table 5.13), and organic-amendment
        (Table 5.14) scaling factors (§8.2.3, Eqs. 6-8)
      - N2O project emission from irrigation regime change (§8.3.2, Eq. 25)
      - QA3 flat 15% uncertainty deduction, gated on the 60,000 tCO2e/yr
        project-size threshold (§8.6.3)
      - Informational N2O-penalty-as-%-of-gross-reduction context (this is
        NOT a §8.4 leakage screen — PE_Red-Irri is a mandatory Eq. 29
        project emission, always subtracted in full; §8.4 leakage sources
        are organic-amendment import / yield decline / biomass diversion,
        none of which this engine computes)

    Explicitly excluded (assumed zero / de minimis, documented per §8.4):
      - CO2 from fossil fuels / liming (§8.2.1-8.2.2)
      - CH4 / N2O from biomass burning (§8.2.5-8.2.7)
      - N2O from baseline nitrogen fertilizers (§8.2.6) — no fertilizer
        change between baseline and project scenario assumed
      - Leakage from organic amendments / yield decline (§8.4.1-8.4.2)
    """

    # VM0051 §8.2.3 Eq. 6, Table 5.12 (Updated) — water-regime scaling factor
    # during the cultivation period (source: VM0051 p.48, quoting IPCC 2019)
    SF_CONTINUOUS_FLOODING = 1.00   # 0 drydowns — no reduction
    SF_SINGLE_AERATION     = 0.71   # 1 drydown  — single drainage period
    SF_TRUE_AWD            = 0.55   # >=2 drydowns — multiple drainage periods
                                     # (corrected from 0.52; VM0051 p.48 states 0.55)

    # VM0051 §8.2.3 Eq. 6, Table 5.13 (Updated) — pre-season water-regime
    # scaling factor (source: VM0051 p.48, quoting IPCC 2019)
    SC_PRESEASON_SHORT = 1.00   # non-flooded pre-season <180 days (double/multi-cropping)
    SC_PRESEASON_LONG  = 0.89   # non-flooded pre-season >180 days (single cropping)

    # VM0051 §8.2.3 Eq. 7, Table 5.14 (Updated) — organic-amendment conversion
    # factors (CFOA), relative to straw incorporated shortly before cultivation
    # (source: IPCC 2019 Refinement Vol 4 Ch 5, Table 5.14 — VM0051 itself
    # defers to this table without reproducing the numbers)
    CFOA_TABLE = {
        "straw_shortly_before": 1.00,  # <30 days before cultivation (reference case)
        "straw_long_before":    0.19,  # >30 days before cultivation
        "compost":              0.17,
        "farmyard_manure":      0.21,
        "green_manure":         0.45,
    }
    # VM0051 §8.2.3 footnote 16 — "For the baseline, 5 t/ha of straw is
    # assumed." Timing isn't specified there; "shortly before cultivation" is
    # Table 5.14's own reference case (CFOA=1.00), so it's used as the default.
    DEFAULT_BASELINE_AMENDMENTS = (("straw_shortly_before", 5.0),)

    # VM0051 §8.6.3 — QA3 flat 15% deduction is only valid below this
    # project-size threshold; above it, the full Eq. 38 probability-of-
    # exceedance uncertainty calculation is required instead (not implemented
    # here — that pathway is out of scope, so this engine blocks rather than
    # silently misapplying the flat deduction).
    UNC_QA3_DEFAULT = 0.15
    QA3_PROJECT_SIZE_GATE_TCO2E_YR = 60_000

    # VM0051 §8.3.2, Eq. 25 — N2O correction factor for AWD drying periods
    # CF_N2O derived from IPCC 2019 Table 11.1 (see VM0051 footnote 21)
    CF_N2O  = 0.00314  # kg N2O / kg N-input
    # VM0051 defers GWP to "the most recent version of the VCS Standard"
    # (p.47/49). Confirmed against VCS Standard v5.0 §3.14.4/Table 9
    # (methodologies/verra/standards/VCS-Standard-v5.0.pdf): AR5 GWP100 is
    # mandatory for reductions/removals on or after 1 Jan 2021 — CH4=28, N2O=265.
    GWP_N2O = 265      # IPCC AR5 GWP100 for N2O

    # VM0051 §9.1 (p.47) doesn't quote EF_c itself — it defers to "Table 5.11
    # in data source." IPCC 2019 Refinement Vol 4 Ch 5, Table 5.11 (Updated)
    # gives the South Asia regional default directly: 0.85 kg CH4/ha/day
    # (error range 0.58-1.26). This is a Tier 1 regional default, not Tier 2
    # (Tier 2 would be a custom, literature-derived, country-specific factor).
    # Corrected from 1.4 kg CH4/ha/day, which appears nowhere in Table 5.11
    # and inflated every rice credit calculation by ~1.65x.
    EF_C_SOUTH_ASIA = 0.85

    def __init__(self, ef_c: float = EF_C_SOUTH_ASIA, gwp_ch4: int = 28):
        self.ef_c    = ef_c
        self.gwp_ch4 = gwp_ch4

    def _water_scaling_factor(self, awd_events: int) -> float:
        if awd_events == 0:
            return self.SF_CONTINUOUS_FLOODING
        elif awd_events == 1:
            return self.SF_SINGLE_AERATION
        else:
            return self.SF_TRUE_AWD

    def _preseason_scaling_factor(self, preseason_category: str) -> float:
        if preseason_category == "short":
            return self.SC_PRESEASON_SHORT
        elif preseason_category == "long":
            return self.SC_PRESEASON_LONG
        raise ValueError(f"Unknown preseason_category: {preseason_category!r}")

    def _organic_amendment_scaling_factor(self, amendments) -> float:
        """
        VM0051 §8.2.3, Eq. 7 — SC_o = (1 + sum(ROA_a * CFOA_a))^0.59.
        amendments: iterable of (amendment_type, rate_t_ha) pairs; amendment_type
        keys into CFOA_TABLE.
        """
        total = sum(rate * self.CFOA_TABLE[amendment_type] for amendment_type, rate in amendments)
        return (1 + total) ** 0.59

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
        preseason_category: str = "short",
        baseline_amendments=None,
        project_amendments=None,
    ) -> dict:
        """
        Execute the full VM0051 QA3 calculation chain.

        Net reductions follow Eq. 29 (simplified for AWD-only, no straw burning):
          ER = DCH4_soil x (1 - UNC_CH4) - PE_Red-Irri

        preseason_category: "short" (<180 days non-flooded pre-season, double/
          multi-cropping, Table 5.13's SF_p=1.00) or "long" (>180 days,
          single cropping, SF_p=0.89). Applies identically to both scenarios
          per VM0051's own convention (subscript bsl -> wp, same table).

        baseline_amendments / project_amendments: iterables of
          (amendment_type, rate_t_ha) pairs keying into CFOA_TABLE. Baseline
          defaults to VM0051's stated default (5 t/ha straw, footnote 16).
          VM0051 states no project-scenario default, so absent explicit input
          this assumes no change in organic-amendment practice between
          scenarios — the same convention already used here for baseline
          nitrogen fertilizer (§8.2.6, no assumed change).

        Returns a dict with all intermediate values for audit trail rendering.
        If the project's gross annual reduction exceeds the QA3 project-size
        gate (§8.6.3), `qa3_pathway_valid` is False and `final_issuance` is
        None — the flat 15% deduction is not a valid pathway above that
        threshold and this engine does not implement the alternative (Eq. 38
        probability-of-exceedance) calculation.
        """
        baseline_amendments = (
            self.DEFAULT_BASELINE_AMENDMENTS if baseline_amendments is None else baseline_amendments
        )
        project_amendments = (
            baseline_amendments if project_amendments is None else project_amendments
        )

        sf_w_project = self._water_scaling_factor(awd_events)
        sc_p         = self._preseason_scaling_factor(preseason_category)
        sc_o_bsl     = self._organic_amendment_scaling_factor(baseline_amendments)
        sc_o_wp      = self._organic_amendment_scaling_factor(project_amendments)

        # Step 1 — Baseline CH4 (Eq. 6/8, continuous flooding, SF_w = 1.0)
        e_baseline = self.ef_c * 1.0 * sc_p * sc_o_bsl * season_length_days * area_ha

        # Step 2 — Project CH4 (Eq. 6/8 with project SF_w)
        e_project  = self.ef_c * sf_w_project * sc_p * sc_o_wp * season_length_days * area_ha

        # Step 3 — Gross CH4 avoided (kg CH4)
        delta_e_ch4 = e_baseline - e_project

        # Step 4 — Convert to tCO2e
        delta_e_co2e = (delta_e_ch4 * self.gwp_ch4) / 1000.0

        # Step 5 — QA3 project-size gate (§8.6.3): flat 15% deduction is only
        # a valid pathway at or below this threshold
        qa3_pathway_valid = delta_e_co2e <= self.QA3_PROJECT_SIZE_GATE_TCO2E_YR
        if not qa3_pathway_valid:
            return {
                "qa3_pathway_valid": False,
                "qa3_block_reason": (
                    f"Gross annual reduction ({delta_e_co2e:.2f} tCO2e) exceeds the "
                    f"QA3 flat-deduction gate ({self.QA3_PROJECT_SIZE_GATE_TCO2E_YR:,} "
                    "tCO2e/yr, §8.6.3) — the full Eq. 38 probability-of-exceedance "
                    "uncertainty calculation is required instead, which this engine "
                    "does not implement."
                ),
                "ef_c_used":    self.ef_c,
                "sf_w_project": sf_w_project,
                "e_baseline":   e_baseline,
                "e_project":    e_project,
                "delta_e_ch4":  delta_e_ch4,
                "delta_e_co2e": delta_e_co2e,
                "final_issuance": None,
                "p_uncertainty":  None,
                "confidence_pct": None,
            }

        # Step 6 — QA3 flat 15% uncertainty deduction (§8.6.3)
        unc_tco2e     = delta_e_co2e * self.UNC_QA3_DEFAULT
        ch4_after_unc = delta_e_co2e - unc_tco2e

        # Step 7 — N2O project emission from irrigation change (Eq. 25)
        # Only when water regime changes (drying periods introduced)
        pe_n2o = (
            self._n2o_irrigation_penalty(q_n_kg_per_ha, area_ha)
            if awd_events > 0 else 0.0
        )

        # Step 8 — Informational context only (NOT a §8.4 leakage screen —
        # see class docstring). PE_Red-Irri is always subtracted in full below
        # regardless of this percentage.
        n2o_penalty_pct_of_gross = (pe_n2o / delta_e_co2e * 100.0) if delta_e_co2e > 0 else 0.0

        # Step 9 — Net reductions per Eq. 29 (CH4 soil term only)
        final_issuance = max(0.0, ch4_after_unc - pe_n2o)

        return {
            "qa3_pathway_valid":  True,
            "ef_c_used":          self.ef_c,
            "sf_w_project":       sf_w_project,
            "sc_preseason":       sc_p,
            "sc_organic_bsl":     sc_o_bsl,
            "sc_organic_wp":      sc_o_wp,
            "e_baseline":         e_baseline,
            "e_project":          e_project,
            "delta_e_ch4":        delta_e_ch4,
            "delta_e_co2e":       delta_e_co2e,
            "unc_deduction_pct":  self.UNC_QA3_DEFAULT * 100,
            "unc_tco2e":          unc_tco2e,
            "ch4_after_unc":      ch4_after_unc,
            "pe_n2o_tco2e":       pe_n2o,
            "q_n_kg_per_ha":      q_n_kg_per_ha,
            "n2o_penalty_pct_of_gross": round(n2o_penalty_pct_of_gross, 2),
            "final_issuance":     final_issuance,
            # Legacy key retained for report_generator compatibility
            "p_uncertainty":      self.UNC_QA3_DEFAULT,
            "confidence_pct":     None,
        }
