class CarbonAssetEngine:
    """
    Implements the Verra VM0051 / IPCC Tier 2 methodology for calculating 
    carbon credits from AWD verification.
    """
    def __init__(self, ef_c=1.4, gwp_ch4=28):
        self.ef_c = ef_c          # Baseline Daily Emission Factor (kg CH4/ha/day)
        self.gwp_ch4 = gwp_ch4    # Global Warming Potential for CH4

    def calculate_credits(self, awd_events: int, season_length_days: int, area_ha: float, ai_accuracy: float = 92.0):
        # Step 1: Quantify Baseline Scenario
        sf_w_baseline = 1.0
        e_baseline = self.ef_c * sf_w_baseline * season_length_days * area_ha

        # Step 2: Quantify Project Scenario
        if awd_events == 0:
            sf_w_project = 1.0
        elif awd_events == 1:
            sf_w_project = 0.71
        else:
            sf_w_project = 0.52
            
        e_project = self.ef_c * sf_w_project * season_length_days * area_ha

        # Step 3: Compute Net Methane Avoided
        delta_e_ch4 = e_baseline - e_project

        # Step 4: Convert to tCO2e
        delta_e_co2e = (delta_e_ch4 * self.gwp_ch4) / 1000.0

        # Step 5: Apply Conservativeness Penalty
        if ai_accuracy >= 95.0:
            p_uncertainty = 0.0
        elif ai_accuracy >= 90.0:
            p_uncertainty = 0.10
        elif ai_accuracy >= 85.0:
            p_uncertainty = 0.30
        else:
            p_uncertainty = 1.0

        final_issuance = delta_e_co2e * (1.0 - p_uncertainty)

        return {
            "e_baseline": e_baseline,
            "e_project": e_project,
            "delta_e_ch4": delta_e_ch4,
            "delta_e_co2e": delta_e_co2e,
            "p_uncertainty": p_uncertainty,
            "final_issuance": final_issuance,
            "sf_w_project": sf_w_project,
            "ai_accuracy": ai_accuracy
        }
