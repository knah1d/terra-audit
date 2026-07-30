"""
Implements a scoped subset of the Verra VM0042 v2.2 Improved Agricultural
Land Management (ALM) methodology, covering tillage/residue management,
fertilizer management, and crop planting/harvesting (rotations, cover crops)
practice changes on non-wetland cropland.

Covers (this implementation):
  - N2O from nitrogen fertilizer, direct + indirect (§8.2.9/8.3, Eqs. 17-23)
  - N2O from N-fixing cover-crop residues (§8.2.9/8.3, Eqs. 24-25)
  - N2O and CH4 from biomass burning (§8.2.8/8.2.11/8.3, Eqs. 14, 32)
  - CO2 from fossil fuel combustion (§8.2.3/8.3, Eqs. 6-7)
  - SOC stock change, Quantification Approach 2 (measure and remeasure,
    §8.2.1/8.3, Eqs. 3-5, 46-47) — driven by manually entered paired lab
    measurements (project site vs. baseline control site), not a
    biogeochemical model
  - SOC-only uncertainty deduction via probability of exceedance
    (§8.6.2/8.6.4, Eqs. 70-71, 74)
  - Net reductions/removals (§8.5, Eqs. 37, 40, 43) and buffer/VCU
    calculation (§8.7, Eqs. 75-79) against a user-supplied non-permanence
    risk rating

Explicitly excluded / assumed zero (documented limitations, not verified):
  - Grazing practices — no enteric fermentation / manure CH4 or N2O
  - Liming CO2 (§8.2.4)
  - Quantification Approach 1 (external biogeochemical model) — SOC is
    Approach 2 only in this implementation
  - Leakage from organic amendment import, livestock displacement, or
    production declines (§8.4) — NOT screened or computed (VM0042 §8.4.3
    makes production-decline leakage accounting mandatory via VMD0054, which
    this engine does not implement). `calculate_credits()` reports
    `leakage_screened=False` with a `leakage_gap_note` so every caller can
    detect and surface this rather than it living only in this docstring.
  - Multi-stratum sampling — the whole field is treated as a single
    quantification unit / stratum (permitted per §8.1)
  - Covariance between t_start and t_final SOC samples in the uncertainty
    calculation is conservatively assumed zero (inflates, not deflates,
    the resulting uncertainty deduction)
  - Approach-3 (default-factor) terms carry no separate uncertainty
    deduction, per §8.6.3 — contingent on management data being collected
    across the whole project area, as assumed here
"""

import math


class AlmCarbonEngine:
    # IPCC 2019 Refinement to the 2006 IPCC Guidelines — Volume 4, Chapter 11
    # Table 11.1 (direct N2O from N inputs, wet climate; conservative range).
    # EF_NDIRECT_LOW/HIGH confirmed verbatim against VM0042 v2.2 §8.6.3 (p.81),
    # which quotes IPCC (2019)'s 0.013-0.019 wet-climate range directly.
    EF_NDIRECT_LOW  = 0.013
    EF_NDIRECT_HIGH = 0.019
    # Table 11.3 (indirect N2O — volatilization / leaching-runoff fractions
    # and emission factors). STILL UNVERIFIED: Chapter 11 itself is not
    # present in methodologies/ipcc/2019_refinement/ (only Ch.2 and Ch.5 are)
    # and neither of those chapters reproduces Table 11.3's values — VM0042's
    # own parameter tables (p.119-121, p.125) also just point to "Lookup Table
    # 11.3" without quoting numbers. These five constants remain plausible
    # (standard literature defaults) but not confirmed in-repo; sourcing
    # Vol 4 Ch 11 would resolve this.
    FRAC_GASF  = 0.11
    FRAC_GASM  = 0.21
    EF_NVOLAT  = 0.014
    FRAC_LEACH = 0.24
    EF_NLEACH  = 0.011

    # N content of N-fixing cover-crop dry matter — literature default for
    # legume cover crops (e.g. VMD0053 crop functional groups); not
    # species-specific in this implementation
    N_CONTENT_NFIX = 0.025

    # EF_RESIDUE_CH4/N2O — CONFIRMED against IPCC 2019 Refinement Vol 4 Ch 2
    # (methodologies/ipcc/2019_refinement/19R_V4_Ch02_Generic_Methodologies.pdf),
    # Table 2.5 "Agricultural residues" row: CH4=2.7, N2O=0.07 g/kg dry matter
    # burnt (exact match).
    EF_RESIDUE_CH4  = 2.7     # g CH4 / kg dry matter burnt
    EF_RESIDUE_N2O  = 0.07    # g N2O / kg dry matter burnt
    # CF_RESIDUE — Table 2.6 gives crop-specific combustion factors, not one
    # generic "agricultural residues" value: Wheat=0.90, Other Crops=0.85,
    # Maize/Rice/Sugarcane=0.80. 0.90 (used here as a single default for all
    # crop types) is the Wheat-specific value, not a universal default — an
    # accurate per-crop table would need practice_schedule's crop_type to key
    # into it, which this scoped implementation does not yet do.
    CF_RESIDUE      = 0.90    # combustion factor (fraction of biomass consumed)

    # Fossil fuel CO2 — VM0042 v2.2 parameter table (p.102) quotes this directly:
    # diesel = 0.002886 t CO2e/L (source: IPCC 2019 Refinement Vol 2 Ch 3 Table 3.3.1)
    EF_CO2_DIESEL_T_PER_L = 0.002886

    # Confirmed against VCS Standard v5.0 §3.14.4/Table 9
    # (methodologies/verra/standards/VCS-Standard-v5.0.pdf): AR5 GWP100 is
    # mandatory for reductions/removals on or after 1 Jan 2021.
    GWP_CH4 = 28    # IPCC AR5 GWP100
    GWP_N2O = 265   # IPCC AR5 GWP100

    # Eq. 74 — one-sided Student's t at 66.7% confidence, large sample size
    T_0667 = 0.4307

    MIN_SOC_SAMPLES = 3

    # VM0042 monitoring tables (p.92/p.128) + June 2026 Corrections & Clarifications
    # (Clarification 8) — SOC remeasurement in both baseline control sites and the
    # project area must occur at least every 5 years, or before each verification
    # event where verification occurs more frequently.
    MAX_VERIFICATION_YEARS = 5

    # VM0042 §8.4.3 (p.52, mandatory language) + June 2026 Corrections Eq. 39/42 —
    # production-decline leakage (LK_disp,t via VMD0054) is a required leakage
    # category this engine does not implement (VMD0054 is not in this repo).
    LEAKAGE_GAP_NOTE = (
        "VM0042 §8.4.3 requires LK_disp,t (via VMD0054) for production-decline "
        "leakage; this engine does not implement VMD0054 and reports er_net/cr_net "
        "unscreened for this mandatory leakage category."
    )

    # -----------------------------------------------------------------
    # Default-factor (Approach 3) emission terms — mirrored baseline/project
    # -----------------------------------------------------------------

    def _conservative_ef_ndirect(self, baseline_n_t: float, project_n_t: float) -> float:
        """
        VM0042 §8.6.3 — the most conservative EF within the IPCC uncertainty
        range must be used across both scenarios: the low value when the
        project scenario reduces the N2O source relative to baseline, the
        high value when it increases it.
        """
        return self.EF_NDIRECT_LOW if project_n_t <= baseline_n_t else self.EF_NDIRECT_HIGH

    def _n2o_fertilizer(self, fsn_t: float, fon_t: float, ef_ndirect: float) -> float:
        """Eqs. 17-23 — direct + indirect N2O from fertilizer N inputs (tCO2e)."""
        n2o_direct = (fsn_t + fon_t) * ef_ndirect * 44 / 28 * self.GWP_N2O
        n2o_volat = (
            (fsn_t * self.FRAC_GASF + fon_t * self.FRAC_GASM)
            * self.EF_NVOLAT * 44 / 28 * self.GWP_N2O
        )
        n2o_leach = (fsn_t + fon_t) * self.FRAC_LEACH * self.EF_NLEACH * 44 / 28 * self.GWP_N2O
        return n2o_direct + n2o_volat + n2o_leach

    def _n2o_n_fixing(self, dry_matter_t: float, ef_ndirect: float) -> float:
        """Eqs. 24-25 — N2O from N-fixing cover-crop residues (tCO2e)."""
        f_cr_t = dry_matter_t * self.N_CONTENT_NFIX
        return f_cr_t * ef_ndirect * 44 / 28 * self.GWP_N2O

    def _biomass_burning(self, mb_kg: float) -> tuple[float, float]:
        """Eqs. 14, 32 — CH4 and N2O from residue burning (tCO2e each)."""
        ch4 = mb_kg * self.CF_RESIDUE * self.EF_RESIDUE_CH4 / 1e6 * self.GWP_CH4
        n2o = mb_kg * self.CF_RESIDUE * self.EF_RESIDUE_N2O / 1e6 * self.GWP_N2O
        return ch4, n2o

    def _fossil_fuel_co2(self, ffc_liters: float) -> float:
        """Eqs. 6-7 — CO2 from fossil fuel combustion (tCO2e)."""
        return ffc_liters * self.EF_CO2_DIESEL_T_PER_L

    def _scenario_terms(self, practices: dict, area_ha: float) -> dict:
        """Converts one scenario's per-ha practice rates into absolute masses."""
        return {
            "fsn_t":         (practices.get("synthetic_n_rate_kg_ha") or 0.0) * area_ha / 1000,
            "fon_t":         (practices.get("organic_n_rate_kg_ha") or 0.0) * area_ha / 1000,
            "nfix_dm_t":     (
                (practices.get("n_fixing_dry_matter_kg_ha") or 0.0) * area_ha / 1000
                if practices.get("n_fixing_species") else 0.0
            ),
            "mb_kg":         (practices.get("residue_burned_kg_ha") or 0.0) * area_ha,
            "ffc_liters":    (practices.get("fuel_use_l_ha") or 0.0) * area_ha,
        }

    # -----------------------------------------------------------------
    # SOC stock change and uncertainty (Approach 2)
    # -----------------------------------------------------------------

    @staticmethod
    def _mean_and_scaled_var(values: list, area_ha: float) -> tuple[float, float]:
        """
        Sample mean and the Eq. 62/71-style variance-of-the-mean estimator,
        scaled by stratum area^2, for a single-stratum design.
        """
        n = len(values)
        mean = sum(values) / n
        if n < 2:
            return mean, 0.0
        var = sum((v - mean) ** 2 for v in values) / (n * (n - 1))
        return mean, var * area_ha ** 2

    def _soc_stock_change(self, soc_measurements: dict, area_ha: float, verification_years: float):
        """
        Eqs. 46-47 — SOC stock change (tCO2e) for baseline (control site) and
        project scenario, plus Eqs. 70-71/74 — the SOC-only uncertainty
        deduction. Requires >= MIN_SOC_SAMPLES samples per (site, timepoint).

        VT0014 cross-check (methodologies/verra/vm0042/VT0014-v1.0.pdf):
        VT0014 governs Digital Soil Mapping — spatial models predicting SOC at
        unsampled locations across the project area. Its Applicability
        Condition 1 (p.10) requires "a calibration dataset and validation
        dataset...to calibrate and validate a model." This engine uses no
        such model — it's a direct, single-stratum sample mean/variance
        estimate (VM0042's plain "Measure and Re-Measure," permitted per
        §8.1 for a single quantification unit). VT0014 is therefore not
        applicable to this implementation; it would only become relevant if
        this engine were extended to spatially interpolate SOC across a
        multi-stratum project area instead of treating the whole field as
        one unit.
        """
        means, variances = {}, {}
        for site_type in ("project", "control"):
            for timepoint in ("t_start", "t_final"):
                values = soc_measurements.get((site_type, timepoint), [])
                mean, var = self._mean_and_scaled_var(values, area_ha)
                means[(site_type, timepoint)] = mean
                variances[(site_type, timepoint)] = var

        delta_co2_soil_wp  = (means[("project", "t_final")] - means[("project", "t_start")]) / verification_years * area_ha
        delta_co2_soil_bsl = (means[("control", "t_final")] - means[("control", "t_start")]) / verification_years * area_ha

        # Eq. 71 (project change variance) and its control-site analogue —
        # covariance between t_start/t_final samples assumed zero (conservative)
        var_wp_change  = variances[("project", "t_final")] + variances[("project", "t_start")]
        var_bsl_change = variances[("control", "t_final")] + variances[("control", "t_start")]
        var_h_t = var_wp_change + var_bsl_change            # Eq. 70 (single stratum h)
        var_total = var_h_t / area_ha ** 2                   # Eq. 70 (single-stratum total)

        mean_err_per_ha = (delta_co2_soil_wp - delta_co2_soil_bsl) / verification_years / area_ha
        if abs(mean_err_per_ha) < 1e-9:
            unc_co2 = 1.0  # degenerate case — no detectable signal, fully conservative
        else:
            unc_pct = (math.sqrt(var_total) / abs(mean_err_per_ha)) * 100 * self.T_0667
            unc_co2 = min(1.0, unc_pct / 100)

        return delta_co2_soil_wp, delta_co2_soil_bsl, unc_co2

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def calculate_credits(
        self,
        practice_schedule: dict,
        soc_measurements: dict,
        area_ha: float,
        verification_years: float = 1.0,
        non_permanence_risk_pct: float = 20.0,
        prior_cumulative_delta_co2_wp_t: float = 0.0,
    ) -> dict:
        """
        practice_schedule  : {'baseline': {...}, 'project': {...}} — see
                              src.database.ALM_PRACTICE_COLUMNS for keys
        soc_measurements   : {(site_type, timepoint): [values in tCO2e/ha]},
                              site_type in {'project','control'},
                              timepoint in {'t_start','t_final'}
        area_ha            : field area (single quantification unit)
        verification_years : length of the verification period (x in Eqs. 46-47).
                              Must be <= MAX_VERIFICATION_YEARS (5) per VM0042's
                              mandatory SOC remeasurement cadence — a value above
                              that is flagged via `cadence_compliant=False` in the
                              return dict, not rejected outright (the caller
                              decides whether to block on it).
        non_permanence_risk_pct : AFOLU buffer-pool risk rating (%) — a
                              project-specific value from the standard's risk
                              tool; NOT computed by this engine
        prior_cumulative_delta_co2_wp_t : cumulative project SOC change (t CO2)
                              summed across all prior verification periods
                              since project start. VM0042's ER/CR classification
                              indicator I(ΔCO2wp) (Eqs. 37/40) is defined on this
                              cumulative total, not the current period alone —
                              callers persisting state across verifications must
                              pass this in (see src.database.get_alm_cumulative_delta)
                              or the classification will only reflect the current
                              period, which VM0042 does not permit.
        """
        bsl = practice_schedule.get("baseline") or {}
        wp  = practice_schedule.get("project") or {}
        bsl_terms = self._scenario_terms(bsl, area_ha)
        wp_terms  = self._scenario_terms(wp, area_ha)

        ef_ndirect = self._conservative_ef_ndirect(
            bsl_terms["fsn_t"] + bsl_terms["fon_t"], wp_terms["fsn_t"] + wp_terms["fon_t"]
        )

        n2o_fert_bsl = self._n2o_fertilizer(bsl_terms["fsn_t"], bsl_terms["fon_t"], ef_ndirect)
        n2o_fert_wp  = self._n2o_fertilizer(wp_terms["fsn_t"], wp_terms["fon_t"], ef_ndirect)

        n2o_nfix_bsl = self._n2o_n_fixing(bsl_terms["nfix_dm_t"], ef_ndirect)
        n2o_nfix_wp  = self._n2o_n_fixing(wp_terms["nfix_dm_t"], ef_ndirect)

        ch4_bb_bsl, n2o_bb_bsl = self._biomass_burning(bsl_terms["mb_kg"])
        ch4_bb_wp,  n2o_bb_wp  = self._biomass_burning(wp_terms["mb_kg"])

        co2_ff_bsl = self._fossil_fuel_co2(bsl_terms["ffc_liters"])
        co2_ff_wp  = self._fossil_fuel_co2(wp_terms["ffc_liters"])

        delta_co2_ff   = co2_ff_bsl - co2_ff_wp
        delta_ch4_bb   = ch4_bb_bsl - ch4_bb_wp
        delta_n2o_soil = (n2o_fert_bsl + n2o_nfix_bsl) - (n2o_fert_wp + n2o_nfix_wp)
        delta_n2o_bb   = n2o_bb_bsl - n2o_bb_wp

        soc_ready = all(
            len(soc_measurements.get((s, t), [])) >= self.MIN_SOC_SAMPLES
            for s in ("project", "control") for t in ("t_start", "t_final")
        )
        if soc_ready:
            delta_co2_soil_wp, delta_co2_soil_bsl, unc_co2 = self._soc_stock_change(
                soc_measurements, area_ha, verification_years
            )
        else:
            delta_co2_soil_wp, delta_co2_soil_bsl, unc_co2 = 0.0, 0.0, 1.0

        # Eq. 44/45 — sign-flip indicator, applied to the SOC uncertainty deduction
        i_soil = 1 if (delta_co2_soil_wp - delta_co2_soil_bsl) >= 0 else -1
        delta_co2_bsl_t = delta_co2_soil_bsl * (1 - unc_co2 * i_soil)
        delta_co2_wp_t  = delta_co2_soil_wp  * (1 - unc_co2 * i_soil)

        # Eqs. 37/40 — I(ΔCO2wp) is defined on the CUMULATIVE SOC change since
        # project start (Σ from year 1 to t), not the current period alone.
        cumulative_delta_co2_wp = prior_cumulative_delta_co2_wp_t + delta_co2_wp_t
        i_wp = 1 if cumulative_delta_co2_wp > 0 else 0
        non_soc_terms = delta_co2_ff + delta_ch4_bb + delta_n2o_soil + delta_n2o_bb
        min_diff = min(0.0, delta_co2_wp_t) - min(0.0, delta_co2_bsl_t)
        max_diff = max(0.0, delta_co2_wp_t) - max(0.0, delta_co2_bsl_t)
        er_t = non_soc_terms + min_diff + (0 if i_wp else max_diff)

        # Eq. 40 — carbon dioxide removals (only when cumulative project SOC change > 0)
        cr_t = i_wp * max_diff

        er_net = er_t     # leakage terms out of scope → LK_ER,t = 0
        cr_net = cr_t     # LK_CR,t = 0
        err_net = er_net + cr_net  # Eq. 43

        # Eqs. 75-76 — buffer deduction on the SOC (CO2 stock) terms only
        npr_frac = non_permanence_risk_pct / 100
        bu_er = npr_frac * (min_diff + (0 if i_wp else max_diff))
        bu_cr = npr_frac * cr_t

        vcu_er = er_net - bu_er  # Eq. 77
        vcu_cr = cr_net - bu_cr  # Eq. 78
        vcu_total = vcu_er + vcu_cr                             # Eq. 79
        final_issuance = max(0.0, vcu_total)

        return {
            "ef_ndirect_used":     ef_ndirect,
            "n2o_fert_bsl":        n2o_fert_bsl,
            "n2o_fert_wp":         n2o_fert_wp,
            "n2o_nfix_bsl":        n2o_nfix_bsl,
            "n2o_nfix_wp":         n2o_nfix_wp,
            "ch4_bb_bsl":          ch4_bb_bsl,
            "ch4_bb_wp":           ch4_bb_wp,
            "n2o_bb_bsl":          n2o_bb_bsl,
            "n2o_bb_wp":           n2o_bb_wp,
            "co2_ff_bsl":          co2_ff_bsl,
            "co2_ff_wp":           co2_ff_wp,
            "delta_co2_ff":        delta_co2_ff,
            "delta_ch4_bb":        delta_ch4_bb,
            "delta_n2o_soil":      delta_n2o_soil,
            "delta_n2o_bb":        delta_n2o_bb,
            "soc_ready":           soc_ready,
            "delta_co2_soil_wp":   delta_co2_soil_wp,
            "delta_co2_soil_bsl":  delta_co2_soil_bsl,
            "unc_co2_pct":         unc_co2 * 100,
            "er_t":                er_t,
            "cr_t":                cr_t,
            "err_net":             err_net,
            "cumulative_delta_co2_wp": cumulative_delta_co2_wp,
            "leakage_screened":    False,
            "leakage_gap_note":    self.LEAKAGE_GAP_NOTE,
            "cadence_compliant":   verification_years <= self.MAX_VERIFICATION_YEARS,
            "non_permanence_risk_pct": non_permanence_risk_pct,
            "bu_er":               bu_er,
            "bu_cr":               bu_cr,
            "vcu_er":              vcu_er,
            "vcu_cr":              vcu_cr,
            "final_issuance":      final_issuance,
            # Kept for report_generator.py compatibility with the rice_awd shape
            "p_uncertainty":       unc_co2,
            "confidence_pct":      None,
        }
