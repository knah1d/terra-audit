class CarbonAssetEngine:
    """
    Implements the Verra VM0051 / IPCC Tier 2 methodology for converting
    satellite-verified AWD events into tradeable carbon credits.

    Parameters
    ----------
    ef_c : float
        Baseline daily CH₄ emission factor in kg CH₄ / ha / day.
        South Asia IPCC default = 1.4.
    gwp_ch4 : int
        Global Warming Potential of CH₄ over a 100-year horizon (GWP₁₀₀).
        IPCC AR5 value = 28.
    """

    # VM0051 Water Scaling Factors by AWD intensity
    SF_CONTINUOUS_FLOODING = 1.00   # 0 drydowns — no reduction
    SF_SINGLE_AERATION     = 0.71   # 1 drydown  — 29 % CH₄ reduction
    SF_TRUE_AWD            = 0.52   # ≥2 drydowns — 48 % CH₄ reduction

    def __init__(self, ef_c: float = 1.4, gwp_ch4: int = 28):
        self.ef_c    = ef_c
        self.gwp_ch4 = gwp_ch4

    def _water_scaling_factor(self, awd_events: int) -> float:
        """Return the VM0051 water scaling factor for the observed AWD count."""
        if awd_events == 0:
            return self.SF_CONTINUOUS_FLOODING
        elif awd_events == 1:
            return self.SF_SINGLE_AERATION
        else:
            return self.SF_TRUE_AWD

    def _uncertainty_penalty(self, ai_accuracy: float) -> float:
        """
        Return the Verra conservativeness deduction fraction.
          ≥95 %   → 0 %  penalty (full issuance)
          90–94 % → 10 % discount
          85–89 % → 30 % discount
          <85 %   → 100 % disqualification
        """
        if ai_accuracy >= 95.0:
            return 0.0
        elif ai_accuracy >= 90.0:
            return 0.10
        elif ai_accuracy >= 85.0:
            return 0.30
        else:
            return 1.0

    def calculate_credits(
        self,
        awd_events: int,
        season_length_days: int,
        area_ha: float,
        ai_accuracy: float = 92.0,
    ) -> dict:
        """
        Execute the full 5-step VM0051 calculation chain.

        Returns a dict with all intermediate values for audit trail rendering.
        """
        sf_w_project  = self._water_scaling_factor(awd_events)
        p_uncertainty = self._uncertainty_penalty(ai_accuracy)

        # Step 1 — Baseline (continuous flooding)
        e_baseline = self.ef_c * 1.0 * season_length_days * area_ha

        # Step 2 — Project (observed AWD practice)
        e_project  = self.ef_c * sf_w_project * season_length_days * area_ha

        # Step 3 — Net methane avoided (kg CH₄)
        delta_e_ch4 = e_baseline - e_project

        # Step 4 — Convert kg CH₄ → tCO₂e
        delta_e_co2e = (delta_e_ch4 * self.gwp_ch4) / 1000.0

        # Step 5 — Apply conservativeness penalty
        final_issuance = delta_e_co2e * (1.0 - p_uncertainty)

        return {
            "sf_w_project":  sf_w_project,
            "p_uncertainty": p_uncertainty,
            "e_baseline":    e_baseline,
            "e_project":     e_project,
            "delta_e_ch4":   delta_e_ch4,
            "delta_e_co2e":  delta_e_co2e,
            "final_issuance": final_issuance,
            "ai_accuracy":   ai_accuracy,
        }
