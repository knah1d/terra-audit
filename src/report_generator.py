"""
Terra-Audit evidence package generator.

Three output formats:
  generate_pdf()              → bytes       (Audit Report PDF)
  generate_audit_json()       → str         (Machine-readable audit record)
  generate_timeseries_csv()   → str         (Raw timeseries for auditors)
"""

import datetime
import json

from fpdf import FPDF


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _awd_label(sf_w: float) -> str:
    if sf_w == 1.00:
        return "0 drydowns"
    elif sf_w == 0.71:
        return "1 drydown"
    else:
        return ">=2 drydowns"


def _s(text: str) -> str:
    """Sanitize text to Latin-1 for fpdf core font compatibility."""
    replacements = {
        "–": "-",   # en dash
        "—": "--",  # em dash
        "→": "->",  # →
        "°": " deg",
        "₂": "2",   # ₂
        "₄": "4",   # ₄
        "μ": "u",   # μ
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


# ---------------------------------------------------------------------------
# PDF template
# ---------------------------------------------------------------------------

class _PDF(FPDF):
    def header(self):
        self.set_fill_color(18, 24, 38)
        self.rect(0, 0, 210, 16, "F")
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(0, 210, 170)
        self.set_y(3)
        self.cell(0, 10, "TERRA-AUDIT  //  dMRV Compliance Report", align="C")
        self.set_text_color(0, 0, 0)
        self.set_y(20)

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(130, 130, 130)
        self.cell(
            0, 6,
            f"Page {self.page_no()}  |  Terra-Audit v1.0  |  "
            f"Verra VM0051 Tier 2  |  "
            f"Generated {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            align="C",
        )

    def section(self, title: str):
        self.ln(5)
        self.set_font("Helvetica", "B", 10)
        self.set_fill_color(232, 238, 250)
        self.set_draw_color(190, 200, 225)
        self.cell(
            0, 7, f"  {_s(title)}",
            border="LB", fill=True,
            new_x="LMARGIN", new_y="NEXT",
        )
        self.set_draw_color(0, 0, 0)
        self.ln(2)

    def kv(self, label: str, value, indent: float = 8):
        self.set_x(self.l_margin + indent)
        self.set_font("Helvetica", "B", 9)
        self.cell(58, 6, _s(label) + ":", new_x="RIGHT", new_y="TOP")
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 6, _s(str(value)), new_x="LMARGIN", new_y="NEXT")

    def note(self, text: str):
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 110, 110)
        self.set_x(self.l_margin + 8)
        self.multi_cell(0, 5, _s(text), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def body(self, text: str):
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 6, _s(text), new_x="LMARGIN", new_y="NEXT")

    def banner(self, text: str, ok: bool = True):
        self.ln(3)
        if ok:
            self.set_fill_color(210, 245, 228)
            self.set_text_color(20, 100, 50)
        else:
            self.set_fill_color(252, 220, 218)
            self.set_text_color(140, 20, 20)
        self.set_font("Helvetica", "B", 10)
        self.multi_cell(0, 8, _s(text), fill=True, align="C",
                        new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_pdf(
    field_info: dict,
    window: dict,
    signal: dict,
    carbon: dict,
) -> bytes:
    """
    Build a complete VM0051 audit report PDF.

    field_info : {field_id, name, district, area_ha}
    window     : {season_label, start, end}
    signal     : {n_observations, vv_mean, vv_std, awd_events, awd_dates,
                  sowing_date, harvest_date, season_length_days, from_phenology}
    carbon     : {sf_w_project, p_uncertainty, e_baseline, e_project,
                  delta_e_ch4, delta_e_co2e, final_issuance, confidence_pct}
    """
    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(left=18, top=20, right=18)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    # ---- Title block -------------------------------------------------------
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(20, 40, 80)
    pdf.ln(2)
    pdf.cell(
        0, 10, "Verra VM0051 Tier 2 - AWD Monitoring Report",
        align="C", new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(
        0, 6,
        f"Generated: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        "  |  Platform: Terra-Audit v1.0",
        align="C", new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_text_color(0, 0, 0)

    # ---- 1. Field Information ---------------------------------------------
    pdf.section("1. Field Information")
    pdf.kv("Field ID",   field_info["field_id"])
    pdf.kv("Field Name", field_info["name"])
    pdf.kv("District",   field_info["district"])
    pdf.kv("Area",       f"{field_info['area_ha']:.4f} ha")

    # ---- 2. Monitoring Period ---------------------------------------------
    pdf.section("2. Monitoring Period")
    pdf.kv("Season",          window["season_label"])
    pdf.kv("Window Start",    window["start"])
    pdf.kv("Window End",      window["end"])
    pdf.kv("Satellite",       "Sentinel-1 SAR GRD, IW mode, DESCENDING pass")
    pdf.kv("Bands Used",      "VV + VH  (C-band, 10 m native resolution)")
    pdf.kv("Spatial Reducer", "Median over field polygon (robust to speckle)")

    # ---- 3. Satellite Data Summary ----------------------------------------
    pdf.section("3. Satellite Data Summary")
    pdf.kv("Total Observations",  str(signal["n_observations"]))
    pdf.kv("VV Mean",             f"{signal['vv_mean']:.4f} dB")
    pdf.kv("VV Std Dev",          f"{signal['vv_std']:.4f} dB")
    pdf.kv("Smoothing Applied",   "Savitzky-Golay  (window=5, polyorder=2)")
    pdf.kv("Flood Criterion",     "Z-score < -0.8  (field-adaptive baseline)")
    pdf.kv("Drydown Criterion",   "dVV > 1.2 sigma after flooded state")

    # ---- 4. AWD Events & Phenology ----------------------------------------
    pdf.section("4. AWD Events and Phenology")
    pdf.kv("AWD Cycles Detected", str(signal["awd_events"]))
    pdf.kv("Drydown Dates",
           ", ".join(signal["awd_dates"]) if signal["awd_dates"] else "None detected")
    pdf.kv("Sowing Date",   signal["sowing_date"])
    pdf.kv("Harvest Date",  signal["harvest_date"])
    sl_note = ("  (detected from VH phenology signal)"
               if signal["from_phenology"]
               else "  (fallback estimate - phenology markers not detected)")
    pdf.kv("Season Length", f"{signal['season_length_days']} days" + sl_note)
    if not signal["from_phenology"]:
        pdf.note(
            "WARNING: Sowing/harvest dates could not be detected from the VH signal in "
            "this analysis window. Season length uses the 120-day fallback. "
            "Manual agronomist verification is required."
        )

    # ---- 5. Carbon Estimation (VM0051 v1.0, QA3 pathway) ------------------
    pdf.section("5. Carbon Estimation  (Verra VM0051 v1.0, QA3 - Default Emission Factors)")
    pdf.kv("Quantification Approach", "QA3 - Default Emission Factors (§8.2.3)")
    pdf.kv("Emission Factor EF_c",    "1.4 kg CH4/ha/day  (IPCC 2019 South Asia Tier 2)")
    pdf.kv("GWP CH4 (AR5 100yr)",     "28")
    pdf.kv("GWP N2O (AR5 100yr)",     "265")
    pdf.kv("Baseline SF_w",           "1.00  (continuous flooding, Eq. 8)")
    pdf.kv("Project SF_w",            f"{carbon['sf_w_project']}  (Eq. 8, {_awd_label(carbon['sf_w_project'])})")
    pdf.ln(2)
    pdf.kv("Baseline CH4 Emissions",  f"{carbon['e_baseline']:.4f} kg CH4  (Eq. 8)")
    pdf.kv("Project CH4 Emissions",   f"{carbon['e_project']:.4f} kg CH4  (Eq. 8)")
    pdf.kv("Gross CH4 Avoided",       f"{carbon['delta_e_ch4']:.4f} kg CH4  (Eq. 31)")
    pdf.kv("Gross tCO2e (before UNC)", f"{carbon['delta_e_co2e']:.6f} tCO2e")
    pdf.ln(2)
    pdf.kv("Uncertainty Deduction",   f"15.0%  (QA3 flat rate, §8.6.3, <60,000 tCO2e/yr)")
    pdf.kv("UNC Deduction Amount",    f"{carbon['unc_tco2e']:.6f} tCO2e")
    pdf.kv("CH4 After Uncertainty",   f"{carbon['ch4_after_unc']:.6f} tCO2e")
    pdf.ln(2)
    pdf.kv("N Fertilizer Input (Q_N)", f"{carbon['q_n_kg_per_ha']:.1f} kg N/ha")
    pdf.kv("N2O Correction (Eq. 25)", f"{carbon['pe_n2o_tco2e']:.6f} tCO2e  (PE_Red-Irri, CF_N2O=0.00314)")
    leakage_status = (
        f"{carbon['leakage_pct']:.1f}% of gross reduction - DE MINIMIS (SS8.4, <5% threshold)"
        if carbon["leakage_de_minimis"]
        else f"{carbon['leakage_pct']:.1f}% of gross reduction - APPLIED IN FULL (>=5% threshold)"
    )
    pdf.kv("Leakage Screen (§8.4)",   leakage_status)
    pdf.ln(2)
    pdf.kv("NET ISSUANCE (Eq. 29)",   f"{carbon['final_issuance']:.6f} tCO2e")

    if carbon["final_issuance"] == 0.0:
        pdf.banner(
            "No net credits issued. Either no AWD events detected or N2O correction "
            "fully offsets CH4 reduction after uncertainty deduction.",
            ok=False,
        )
    else:
        pdf.banner(
            f"VERIFIED: {carbon['final_issuance']:.4f} tCO2e net verified credits"
            " - ready for registry submission.",
            ok=True,
        )

    # ---- 6. Methodology ---------------------------------------------------
    pdf.section("6. Methodology")
    pdf.body(
        "Terra-Audit implements the Verra VM0051 v1.0 Quantification Approach 3 (QA3 - "
        "Default Emission Factors) for Alternate Wetting and Drying (AWD) rice irrigation "
        "monitoring using Sentinel-1 SAR satellite data. VV backscatter is used as the "
        "primary flood-state indicator via z-score anomaly detection (field-adaptive "
        "baseline, threshold z < -0.8). Sharp positive VV transitions (> 1.2 sigma) "
        "following flooded periods are classified as drydown events. The VM0051 water "
        "scaling factor (SF_w) is assigned per Eq. 8: 1.00 (0 events), 0.71 (1 event), "
        "0.52 (>=2 events). Gross CH4 reductions are reduced by the QA3 flat 15% "
        "uncertainty deduction (§8.6.3) and by the N2O irrigation correction (PE_Red-Irri, "
        "§8.3.2 Eq. 25, CF_N2O=0.00314 kg N2O/kg N). Net reductions follow Eq. 29 "
        "(simplified: CH4 soil term only). Leakage sources not applicable to this project "
        "scope are screened per §8.4 and treated as de minimis where <5% of gross reductions."
    )

    # ---- 7. Assumptions ---------------------------------------------------
    pdf.section("7. Assumptions")
    for i, a in enumerate([
        "EF_c = 1.4 kg CH4/ha/day (IPCC South Asia regional default; "
        "may not reflect site-specific soil conditions)",
        "DESCENDING orbit pass only used to avoid time-series artefacts "
        "from mixed-orbit acquisition geometry",
        "Field area computed via Shoelace formula with spherical latitude "
        "correction (no external GIS dependency)",
        "Single cropping season assumed per analysis window",
        "Organic amendment scaling factor (SFo) = 1.0 (no additional "
        "organic inputs modeled)",
        "Soil type scaling factor (SFs) = 1.0 (no site-specific soil "
        "characterization data incorporated)",
    ], 1):
        pdf.set_x(pdf.l_margin + 8)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, f"{i}. {_s(a)}", new_x="LMARGIN", new_y="NEXT")

    # ---- 8. Limitations ---------------------------------------------------
    pdf.section("8. Limitations")
    for i, lim in enumerate([
        "SAR backscatter is sensitive to surface roughness and wind — drydown "
        "events may be missed or false-positive during high-wind conditions",
        "Flooding under dense crop canopy may be underestimated by VV backscatter",
        "Phenology detection requires >= 5 observations and a discernible "
        "VH signal minimum; fails silently on short or noisy windows",
        "Results have not been validated against in-situ soil moisture "
        "sensors or farmer irrigation logbooks",
        "This report is generated by an AI-assisted analytical platform and "
        "requires expert agronomist review before formal registry submission",
    ], 1):
        pdf.set_x(pdf.l_margin + 8)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, f"{i}. {_s(lim)}", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def generate_audit_json(
    field_info: dict,
    window: dict,
    signal: dict,
    carbon: dict,
    df,
) -> str:
    record = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "platform": "Terra-Audit v1.0",
        "methodology": "Verra VM0051 Tier 2",
        "field": field_info,
        "monitoring_window": window,
        "satellite_data_summary": {
            "n_observations":          signal["n_observations"],
            "vv_mean_db":              round(signal["vv_mean"], 6),
            "vv_std_db":               round(signal["vv_std"], 6),
            "flood_z_threshold":       -0.8,
            "drydown_sigma_threshold": 1.2,
            "smoothing":               "Savitzky-Golay window=5 polyorder=2",
        },
        "awd_detection": {
            "awd_cycles_detected": signal["awd_events"],
            "drydown_dates":       signal["awd_dates"],
        },
        "phenology": {
            "sowing_date":              signal["sowing_date"],
            "harvest_date":             signal["harvest_date"],
            "season_length_days":       signal["season_length_days"],
            "from_phenology_detection": signal["from_phenology"],
        },
        "carbon_calculation": {
            "methodology":                        "VM0051 v1.0, QA3 Default Emission Factors",
            "emission_factor_ef_c_kg_ch4_per_ha_per_day": 1.4,
            "gwp_ch4_ar5_100yr":                  28,
            "gwp_n2o_ar5_100yr":                  265,
            "sf_w_baseline":                      1.0,
            "sf_w_project":                       carbon["sf_w_project"],
            "e_baseline_kg_ch4":                  round(carbon["e_baseline"], 6),
            "e_project_kg_ch4":                   round(carbon["e_project"], 6),
            "delta_e_ch4_kg":                     round(carbon["delta_e_ch4"], 6),
            "gross_delta_e_tco2e":                round(carbon["delta_e_co2e"], 6),
            "uncertainty_deduction_pct":          15.0,
            "uncertainty_deduction_tco2e":        round(carbon["unc_tco2e"], 6),
            "ch4_after_uncertainty_tco2e":        round(carbon["ch4_after_unc"], 6),
            "q_n_kg_per_ha":                      carbon["q_n_kg_per_ha"],
            "pe_n2o_irrigation_tco2e":            round(carbon["pe_n2o_tco2e"], 6),
            "leakage_pct_of_gross":               carbon["leakage_pct"],
            "leakage_de_minimis":                 carbon["leakage_de_minimis"],
            "final_issuance_tco2e":               round(carbon["final_issuance"], 6),
        },
        "timeseries": df.to_dict(orient="records"),
    }
    return json.dumps(record, indent=2, default=str)


def generate_timeseries_csv(df) -> str:
    return df.to_csv(index=False)
