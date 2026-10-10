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
from fpdf.fonts import FontFace


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
        "≥": ">=", "≤": "<=", "’": "'", "‘": "'", "“": '"', "”": '"',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="ignore").decode("latin-1")


# ---------------------------------------------------------------------------
# PDF template
# ---------------------------------------------------------------------------

class _PDF(FPDF):
    methodology_label = "Verra VM0051 Tier 2"

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
            f"{self.methodology_label}  |  "
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


_RICE_METHOD_TEXT = (
    "Terra-Audit implements the Verra VM0051 v1.1 Quantification Approach 3 (QA3 - "
    "Default Emission Factors) for Alternate Wetting and Drying (AWD) rice irrigation "
    "monitoring using Sentinel-1 SAR satellite data. VV backscatter is used as the "
    "primary flood-state indicator via z-score anomaly detection (field-adaptive "
    "baseline, threshold z < -0.8). Sharp positive VV transitions (> 1.2 sigma) "
    "following flooded periods are classified as drydown events. The VM0051 water "
    "scaling factor (SF_w) is assigned per Eq. 6/Table 5.12: 1.00 (0 events), 0.71 "
    "(1 event), 0.55 (>=2 events), alongside a pre-season water-regime factor (SC_p, "
    "Table 5.13) and an organic-amendment factor (SC_o, Eq. 7/Table 5.14). Gross CH4 "
    "reductions are reduced by the QA3 flat 15% uncertainty deduction (§8.6.3, valid "
    "only at or below the 60,000 tCO2e/yr project-size gate) and by the N2O irrigation "
    "correction (PE_Red-Irri, §8.3.2 Eq. 25, CF_N2O=0.00314 kg N2O/kg N) — a mandatory "
    "project emission subtracted in full, not a §8.4 leakage source. Net reductions "
    "follow Eq. 29 (simplified: CH4 soil term only; §8.4 leakage sources such as "
    "organic-amendment import and yield decline are not computed by this engine)."
)


def _rice_assumptions(carbon: dict) -> list[str]:
    return [
        f"EF_c = {carbon['ef_c_used']} kg CH4/ha/day (IPCC 2019 Table 5.11, South Asia "
        "Tier 1 regional default; may not reflect site-specific soil conditions)",
        "DESCENDING orbit pass only used to avoid time-series artefacts "
        "from mixed-orbit acquisition geometry",
        "Field area computed via Shoelace formula with spherical latitude "
        "correction (no external GIS dependency)",
        "Single cropping season assumed per analysis window",
        "Pre-season water regime (SC_p) and organic-amendment (SC_o) factors "
        "are user-entered (default: 5 t/ha straw, incorporated shortly before "
        "cultivation, per §8.2.3 footnote 16) — verify against actual farm practice",
        "Soil type / rice cultivar scaling (SFs/SFr) not modeled — no "
        "site-specific soil characterization data incorporated",
    ]


_RICE_LIMITATIONS = [
    "SAR backscatter is sensitive to surface roughness and wind — drydown "
    "events may be missed or false-positive during high-wind conditions",
    "Flooding under dense crop canopy may be underestimated by VV backscatter",
    "Phenology detection requires >= 5 observations and a discernible "
    "VH signal minimum; fails silently on short or noisy windows",
    "Results have not been validated against in-situ soil moisture "
    "sensors or farmer irrigation logbooks",
    "This report is generated by an AI-assisted analytical platform and "
    "requires expert agronomist review before formal registry submission",
]


def _rice_quantification(pdf: "_PDF", carbon: dict, title: str, closing: str) -> bool:
    """VM0051 QA3 quantification block shared by the legacy audit report and
    the MRV report. Returns False (after a blocking banner) when the QA3
    pathway is not valid for this result."""
    pdf.section(title)

    if not carbon.get("qa3_pathway_valid", True):
        pdf.banner(
            "QA3 PATHWAY NOT VALID: " + carbon.get("qa3_block_reason", "project exceeds "
            "the 60,000 tCO2e/yr QA3 flat-deduction gate (§8.6.3) - the full Eq. 38 "
            "probability-of-exceedance uncertainty calculation is required instead."),
            ok=False,
        )
        return False

    pdf.kv("Quantification Approach", "QA3 - Default Emission Factors (§8.2.3)")
    pdf.kv("Emission Factor EF_c",    f"{carbon['ef_c_used']} kg CH4/ha/day  (IPCC 2019 Table 5.11, South Asia Tier 1 regional default)")
    pdf.kv("GWP CH4 (AR5 100yr)",     "28")
    pdf.kv("GWP N2O (AR5 100yr)",     "265")
    pdf.kv("Baseline SF_w",           "1.00  (continuous flooding, Eq. 6)")
    pdf.kv("Project SF_w",            f"{carbon['sf_w_project']}  (Eq. 6, {_awd_label(carbon['sf_w_project'])})")
    pdf.kv("Pre-season SC_p",         f"{carbon['sc_preseason']}  (Eq. 6, Table 5.13)")
    pdf.kv("Organic amendment SC_o (baseline)", f"{carbon['sc_organic_bsl']:.4f}  (Eq. 7, Table 5.14)")
    pdf.kv("Organic amendment SC_o (project)",  f"{carbon['sc_organic_wp']:.4f}  (Eq. 7, Table 5.14)")
    pdf.ln(2)
    pdf.kv("Baseline CH4 Emissions",  f"{carbon['e_baseline']:.4f} kg CH4  (Eq. 6/8)")
    pdf.kv("Project CH4 Emissions",   f"{carbon['e_project']:.4f} kg CH4  (Eq. 6/8)")
    pdf.kv("Gross CH4 Avoided",       f"{carbon['delta_e_ch4']:.4f} kg CH4")
    pdf.kv("Gross tCO2e (before UNC)", f"{carbon['delta_e_co2e']:.6f} tCO2e")
    pdf.ln(2)
    pdf.kv("Uncertainty Deduction",   f"15.0%  (QA3 flat rate, §8.6.3, <=60,000 tCO2e/yr)")
    pdf.kv("UNC Deduction Amount",    f"{carbon['unc_tco2e']:.6f} tCO2e")
    pdf.kv("CH4 After Uncertainty",   f"{carbon['ch4_after_unc']:.6f} tCO2e")
    pdf.ln(2)
    pdf.kv("N Fertilizer Input (Q_N)", f"{carbon['q_n_kg_per_ha']:.1f} kg N/ha")
    pdf.kv("N2O Correction (Eq. 25)", f"{carbon['pe_n2o_tco2e']:.6f} tCO2e  (PE_Red-Irri, CF_N2O=0.00314)")
    pdf.kv("N2O Penalty (% of gross, informational)",
           f"{carbon['n2o_penalty_pct_of_gross']:.1f}%  (mandatory Eq. 29 term, not a §8.4 leakage screen)")
    pdf.ln(2)
    pdf.kv("NET ISSUANCE (Eq. 29)",   f"{carbon['final_issuance']:.6f} tCO2e")

    if carbon["final_issuance"] == 0.0:
        pdf.banner(
            "No positive calculated estimate. Either no AWD events detected or N2O correction "
            "fully offsets CH4 reduction after uncertainty deduction.",
            ok=False,
        )
    else:
        pdf.banner(
            f"CALCULATED ESTIMATE: {carbon['final_issuance']:.4f} tCO2e (not registry-issued credits)"
            f" - {closing}",
            ok=True,
        )
    return True


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
    carbon     : {sf_w_project, sc_preseason, sc_organic_bsl, sc_organic_wp,
                  p_uncertainty, e_baseline, e_project, delta_e_ch4,
                  delta_e_co2e, unc_tco2e, ch4_after_unc, pe_n2o_tco2e,
                  q_n_kg_per_ha, n2o_penalty_pct_of_gross, final_issuance,
                  confidence_pct}
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

    # ---- 5. Carbon Estimation (VM0051 v1.1, QA3 pathway) ------------------
    if not _rice_quantification(pdf, carbon, "5. Carbon Estimation  (Verra VM0051 v1.1, QA3 - Default Emission Factors)",
                                "ready for registry submission."):
        return bytes(pdf.output())

    # ---- 6. Methodology ---------------------------------------------------
    pdf.section("6. Methodology")
    pdf.body(_RICE_METHOD_TEXT)

    # ---- 7. Assumptions ---------------------------------------------------
    pdf.section("7. Assumptions")
    for i, a in enumerate(_rice_assumptions(carbon), 1):
        pdf.set_x(pdf.l_margin + 8)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, f"{i}. {_s(a)}", new_x="LMARGIN", new_y="NEXT")

    # ---- 8. Limitations ---------------------------------------------------
    pdf.section("8. Limitations")
    for i, lim in enumerate(_RICE_LIMITATIONS, 1):
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
        "carbon_calculation": (
            {
                "methodology":         "VM0051 v1.1, QA3 Default Emission Factors",
                "qa3_pathway_valid":   False,
                "qa3_block_reason":    carbon.get("qa3_block_reason"),
                "sf_w_project":        carbon.get("sf_w_project"),
                "e_baseline_kg_ch4":   round(carbon["e_baseline"], 6) if carbon.get("e_baseline") is not None else None,
                "e_project_kg_ch4":    round(carbon["e_project"], 6) if carbon.get("e_project") is not None else None,
                "delta_e_ch4_kg":      round(carbon["delta_e_ch4"], 6) if carbon.get("delta_e_ch4") is not None else None,
                "gross_delta_e_tco2e": round(carbon["delta_e_co2e"], 6) if carbon.get("delta_e_co2e") is not None else None,
                "final_issuance_tco2e": None,
            }
            if not carbon.get("qa3_pathway_valid", True)
            else {
                "methodology":                        "VM0051 v1.1, QA3 Default Emission Factors",
                "qa3_pathway_valid":                   True,
                "emission_factor_ef_c_kg_ch4_per_ha_per_day": carbon["ef_c_used"],
                "gwp_ch4_ar5_100yr":                  28,
                "gwp_n2o_ar5_100yr":                  265,
                "sf_w_baseline":                      1.0,
                "sf_w_project":                       carbon["sf_w_project"],
                "sc_preseason":                       carbon["sc_preseason"],
                "sc_organic_baseline":                carbon["sc_organic_bsl"],
                "sc_organic_project":                 carbon["sc_organic_wp"],
                "e_baseline_kg_ch4":                  round(carbon["e_baseline"], 6),
                "e_project_kg_ch4":                   round(carbon["e_project"], 6),
                "delta_e_ch4_kg":                     round(carbon["delta_e_ch4"], 6),
                "gross_delta_e_tco2e":                round(carbon["delta_e_co2e"], 6),
                "uncertainty_deduction_pct":          15.0,
                "uncertainty_deduction_tco2e":        round(carbon["unc_tco2e"], 6),
                "ch4_after_uncertainty_tco2e":        round(carbon["ch4_after_unc"], 6),
                "q_n_kg_per_ha":                      carbon["q_n_kg_per_ha"],
                "pe_n2o_irrigation_tco2e":            round(carbon["pe_n2o_tco2e"], 6),
                "n2o_penalty_pct_of_gross_informational": carbon["n2o_penalty_pct_of_gross"],
                "final_issuance_tco2e":               round(carbon["final_issuance"], 6),
            }
        ),
        "timeseries": df.to_dict(orient="records"),
    }
    return json.dumps(record, indent=2, default=str)


def generate_timeseries_csv(df) -> str:
    return df.to_csv(index=False)


# ---------------------------------------------------------------------------
# VM0042 Improved Agricultural Land Management (ALM) — cropland field type
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# VM0051 monitoring (MRV) reports — field and project level
# ---------------------------------------------------------------------------

_INK = (33, 37, 41)
_MUTED = (108, 117, 125)
_BRAND = (22, 101, 52)
_BRAND_TINT = (232, 243, 236)
_ZEBRA = (248, 250, 249)
_RULE = (210, 215, 220)
_TONES = {  # text colour, fill colour
    "amber": ((146, 64, 14), (254, 243, 199)),
    "green": ((22, 101, 52), (220, 252, 231)),
    "red": ((153, 27, 27), (254, 226, 226)),
}
# VM0051 §8.6.3: the QA3 flat uncertainty deduction is valid only up to this
# project-wide annual size; per-field checks cannot see the project total.
_QA3_PROJECT_GATE_TCO2E = 60000.0


def _n(value, decimals: int = 2) -> str:
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "-"


def _date(value) -> str:
    return str(value or "")[:10] or "-"


def _who(users: dict, user_id) -> str:
    return users.get(user_id, user_id or "-")


def _positions(geojson) -> list:
    """Every [lon, lat] in a GeoJSON geometry, Feature or FeatureCollection."""
    if not isinstance(geojson, dict):
        return []
    if geojson.get("type") == "FeatureCollection":
        return [p for f in geojson.get("features") or [] for p in _positions(f)]
    if geojson.get("type") == "Feature":
        return _positions(geojson.get("geometry"))
    out, stack = [], [geojson.get("coordinates") or []]
    while stack:
        item = stack.pop()
        if isinstance(item, (list, tuple)) and len(item) >= 2 and all(isinstance(v, (int, float)) for v in item[:2]):
            out.append(item)
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
    return out


def _label(value) -> str:
    return str(value or "-").replace("_", " ").capitalize()


class _MRVPDF(FPDF):
    """Shared layout for the VM0051 monitoring reports: running header and
    footer, numbered sections, fact and data tables, status notices, and a
    diagonal DRAFT watermark until internal approval."""

    def __init__(self, running_title: str, status_label: str, draft: bool):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.running_title, self.status_label, self.draft = running_title, status_label, draft
        self.generated = datetime.datetime.now(datetime.timezone.utc)
        self.set_margins(left=20, top=22, right=20)
        self.set_auto_page_break(auto=True, margin=20)
        self.set_title(_s(running_title))
        self.set_author("Terra Audit")
        self.set_creator("Terra Audit")
        self.set_draw_color(*_RULE)
        self.set_line_width(0.2)
        self.add_page()

    @property
    def content_width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def header(self):
        if self.draft:
            with self.local_context(text_color=(234, 234, 234)):
                self.set_font("Helvetica", "B", 46)
                mark = "DRAFT - NOT APPROVED"
                with self.rotation(45, x=105, y=148):
                    self.text(105 - self.get_string_width(mark) / 2, 152, mark)
        self.set_y(10)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*_BRAND)
        self.cell(self.content_width / 2, 5, "TERRA AUDIT")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*_MUTED)
        self.cell(self.content_width / 2, 5, _s(self.running_title), align="R")
        self.set_draw_color(*_RULE)
        self.line(self.l_margin, 16.5, self.w - self.r_margin, 16.5)
        self.set_xy(self.l_margin, 22)
        self.set_text_color(*_INK)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(*_RULE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*_MUTED)
        third = self.content_width / 3
        self.cell(third, 4, _s(self.status_label))
        self.cell(third, 4, f"Generated {self.generated:%d %b %Y %H:%M} UTC", align="C")
        self.cell(third, 4, f"Page {self.page_no()} of {{nb}}", align="R")

    # ---- building blocks ---------------------------------------------------
    def _room(self, height: float):
        if self.get_y() + height > self.page_break_trigger:
            self.add_page()

    def title_block(self, kicker: str, title: str, subtitle: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(*_BRAND)
        self.cell(0, 5, _s(kicker.upper()), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*_INK)
        self.multi_cell(0, 9, _s(title), align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(0.5)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*_MUTED)
        self.multi_cell(0, 5.2, _s(subtitle), align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*_INK)
        self.ln(5)

    def notice(self, text: str, tone: str = "amber"):
        ink, fill = _TONES[tone]
        self.set_font("Helvetica", "B", 9)
        self._room(14)
        top = self.get_y()
        self.set_fill_color(*fill)
        self.set_text_color(*ink)
        self.multi_cell(0, 5, _s(text), fill=True, align="L", padding=(2.5, 3, 2.5, 4.5),
                        new_x="LMARGIN", new_y="NEXT")
        self.set_fill_color(*ink)
        self.rect(self.l_margin, top, 1.2, self.get_y() - top, style="F")
        self.set_fill_color(255, 255, 255)
        self.set_text_color(*_INK)
        self.ln(4)

    def section(self, title: str):
        self._room(32)
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*_BRAND)
        self.cell(0, 7, _s(title), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*_BRAND)
        self.set_line_width(0.5)
        self.line(self.l_margin, self.get_y() + 0.5, self.l_margin + 14, self.get_y() + 0.5)
        self.set_line_width(0.2)
        self.set_draw_color(*_RULE)
        self.set_text_color(*_INK)
        self.ln(4)

    def subsection(self, title: str):
        self._room(20)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*_INK)
        self.cell(0, 6, _s(title), new_x="LMARGIN", new_y="NEXT")
        self.ln(0.5)

    def paragraph(self, text: str):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*_INK)
        self.multi_cell(0, 4.8, _s(text), align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def note(self, text: str):
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*_MUTED)
        self.multi_cell(0, 4.2, _s(text), align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*_INK)
        self.ln(2)

    def numbered(self, items: list[str]):
        self.set_font("Helvetica", "", 8.5)
        for i, item in enumerate(items, 1):
            self._room(10)
            self.cell(7, 4.6, f"{i}.")
            self.multi_cell(0, 4.6, _s(item), align="L", new_x="LMARGIN", new_y="NEXT")
            self.ln(0.8)
        self.ln(1)

    def facts(self, rows: list[tuple], label_width: float = 50):
        """Two-column label/value list. A value given as ("mono", text) is
        set in a fixed-width face (identifiers, hashes)."""
        self.set_font("Helvetica", "", 9)
        self.set_fill_color(255, 255, 255)
        label_style = FontFace(emphasis="B", color=_MUTED)
        mono = FontFace(family="Courier", size_pt=8)
        with self.table(col_widths=(label_width, self.content_width - label_width), width=self.content_width,
                        first_row_as_headings=False, borders_layout="HORIZONTAL_LINES", text_align="LEFT",
                        line_height=4.8, padding=(1.4, 1.5)) as table:
            for label, value in rows:
                row = table.row()
                row.cell(_s(label), style=label_style)
                if isinstance(value, tuple) and value[0] == "mono":
                    row.cell(_s(str(value[1])), style=mono)
                else:
                    row.cell(_s("-" if value in (None, "") else str(value)))
        self.ln(4)

    def data_table(self, headers: list[str], rows: list[list], widths: tuple, align: tuple | None = None,
                   mono: tuple = (), emphasize_last: bool = False):
        self.set_font("Helvetica", "", 8)
        self.set_fill_color(*_ZEBRA)
        scale = self.content_width / sum(widths)
        heading = FontFace(emphasis="B", color=_BRAND, fill_color=_BRAND_TINT)
        mono_face = FontFace(family="Courier", size_pt=7)
        total_face = FontFace(emphasis="B", fill_color=_TONES["green"][1])
        with self.table(col_widths=tuple(w * scale for w in widths), width=self.content_width,
                        text_align=align or "LEFT", line_height=4.2, padding=(1.5, 1.8),
                        headings_style=heading, cell_fill_color=_ZEBRA, cell_fill_mode="ROWS",
                        borders_layout="HORIZONTAL_LINES") as table:
            head = table.row()
            for h in headers:
                head.cell(_s(h))
            for index, values in enumerate(rows):
                last = emphasize_last and index == len(rows) - 1
                row = table.row(style=total_face if last else None)
                for col, value in enumerate(values):
                    row.cell(_s("-" if value in (None, "") else str(value)),
                             style=mono_face if col in mono and not last else None)
        self.set_fill_color(255, 255, 255)
        self.ln(4)


_STATUS_FINAL = "FINAL - internally approved"
_STATUS_DRAFT = "DRAFT - not internally approved"
_METHODOLOGY = "Verra VM0051 v1.1 - Improved Rice Cultivation (Alternate Wetting and Drying), QA3"
_DECLARATION = ("This monitoring report presents calculated greenhouse gas emission reductions for internal "
                "and verifier use. It does not constitute issued Verified Carbon Units (VCUs). Issuance requires "
                "validation and verification by an accredited validation/verification body (VVB) and "
                "registration under the Verra VCS Program.")


def _quantification_rows(r: dict) -> list[list]:
    """VM0051 QA3 quantification as Item / Value / Reference rows; `r` is one
    calculation result or a project-level sum of results."""
    rows = []
    if r.get("ef_c_used") is not None:
        rows += [
            ["Emission factor EF_c", f"{r['ef_c_used']} kg CH4/ha/day", "IPCC 2019, Table 5.11 (South Asia default)"],
            ["Baseline water scaling factor SF_w", "1.00 (continuous flooding)", "Eq. 6, Table 5.12"],
            ["Project water scaling factor SF_w", f"{r['sf_w_project']} ({_awd_label(r['sf_w_project'])})", "Eq. 6, Table 5.12"],
            ["Pre-season water regime SC_p", _n(r.get("sc_preseason"), 2), "Eq. 6, Table 5.13"],
            ["Organic amendment SC_o (baseline / project)",
             f"{_n(r.get('sc_organic_bsl'), 4)} / {_n(r.get('sc_organic_wp'), 4)}", "Eq. 7, Table 5.14"],
        ]
    rows += [
        ["Baseline CH4 emissions", f"{_n(r.get('e_baseline'))} kg CH4", "Eq. 6, Eq. 8"],
        ["Project CH4 emissions", f"{_n(r.get('e_project'))} kg CH4", "Eq. 6, Eq. 8"],
        ["CH4 emissions avoided", f"{_n(r.get('delta_e_ch4'))} kg CH4", "Baseline - project"],
        ["Gross emission reductions", f"{_n(r.get('delta_e_co2e'), 4)} tCO2e", "GWP CH4 = 28 (AR5, 100-yr)"],
        ["Uncertainty deduction (15%)", f"-{_n(r.get('unc_tco2e'), 4)} tCO2e", "QA3 flat rate, Section 8.6.3"],
        ["N2O irrigation correction (PE_Red-Irri)", f"-{_n(r.get('pe_n2o_tco2e'), 4)} tCO2e",
         "Eq. 25, CF_N2O = 0.00314; GWP N2O = 265"],
        ["Net emission reductions", f"{_n(r.get('final_issuance'), 4)} tCO2e", "Eq. 29"],
    ]
    return rows


def generate_mrv_report_vm0051(ctx: dict) -> bytes:
    """VM0051 v1.1 monitoring report for ONE committed calculation version,
    built only from its frozen snapshot plus the internal review record —
    never from today's field data. `ctx` is assembled by
    backend/routers/export.py (see _mrv_context there)."""
    calc, snap, users = ctx["calculation"], ctx["snapshot"], ctx["users"]
    carbon, field, period = calc["result"], snap["field"], snap["monitoring_period"]
    inputs, provenance = snap["engine_inputs"], snap.get("signal_input_provenance") or {}
    signal, submission, project = ctx.get("signal"), ctx.get("submission"), ctx.get("project") or {}
    final = ctx["status"] == "final"

    pdf = _MRVPDF(f"Field Monitoring Report | {field['name']}",
                  f"{_STATUS_FINAL if final else _STATUS_DRAFT} | VM0051 v1.1", draft=not final)
    pdf.title_block("Field monitoring report", field["name"],
                    f"{_METHODOLOGY}\nMonitoring period {period['start']} to {period['end']}")
    pdf.notice(_STATUS_FINAL + "." if final else
               _STATUS_DRAFT + ". Not for submission to a registry or VVB.", "green" if final else "amber")
    pdf.facts([
        ("Project", f"{project.get('name', '-')}"),
        ("Field", f"{field['name']} ({field['field_id']})"),
        ("Monitoring period", f"{period['start']} to {period['end']}"),
        ("Net emission reductions", f"{_n(carbon.get('final_issuance'), 4)} tCO2e (calculated estimate, not issued credits)"),
        ("Calculation", ("mono", f"{calc['calculation_id']}  v{calc['version']}")),
        ("Report status", "Final" if final else "Draft"),
        ("Prepared", f"{_date(calc['created_at'])} by {_who(users, calc['created_by'])}"),
        ("Generated by", ctx.get("generated_by") or "-"),
    ])

    # ---- 1. Project boundary ----------------------------------------------
    pdf.section("1. Project Boundary")
    points = _positions(field.get("geojson_geometry"))
    bounds = "-"
    if points:
        lons, lats = [pt[0] for pt in points], [pt[1] for pt in points]
        bounds = (f"{len(points)} boundary vertices; longitude {min(lons):.5f} to {max(lons):.5f}, "
                  f"latitude {min(lats):.5f} to {max(lats):.5f} (WGS 84)")
    pdf.facts([
        ("Field ID", ("mono", field["field_id"])),
        ("Field name", field["name"]),
        ("District", field.get("district") or "-"),
        ("Area", f"{_n(field['area_ha'], 4)} ha"),
        ("Boundary", bounds),
    ])
    pdf.note("The full boundary geometry is frozen in the calculation snapshot (see Section 8).")

    # ---- 2. Crop seasons and field evidence ---------------------------------
    pdf.section("2. Crop Seasons and Field Evidence")
    for entry in snap.get("seasons", []):
        sp = entry["season"]["payload"]
        pdf.subsection(f"{sp.get('name')}  ({sp.get('start_date')} to {sp.get('end_date')}, version {entry.get('version')})")
        pdf.facts([("Declared crops", ", ".join(sp.get("crops") or []) or "-")])
        reviews = {}
        for r in entry.get("reviews", []):
            reviews.setdefault(r["payload"].get("observation_id"), []).append(r)
        rows = []
        for o in entry.get("observations", []):
            op = o["payload"]
            latest = (reviews.get(o["id"]) or [None])[-1]
            decision = (f"{_label(latest['payload'].get('decision'))} by {_who(users, latest['payload'].get('reviewed_by'))}"
                        if latest else "Not reviewed")
            rows.append([_date(op.get("observed_at")), _label(op.get("kind")), op.get("value"), _label(op.get("source")),
                         op.get("evidence_reference"), _who(users, op.get("created_by")), decision])
        if rows:
            pdf.data_table(["Date", "Observation", "Value", "Source", "Evidence ref.", "Recorded by", "Independent review"],
                           rows, (17, 20, 17, 21, 24, 28, 33))
        else:
            pdf.note("No field observations recorded for this season.")
        events = [e["payload"] for e in entry.get("practice_events", [])]
        if events:
            pdf.data_table(["Date", "Practice event", "Source"],
                           [[_date(e.get("event_date")), _label(e.get("kind")), _label(e.get("source"))] for e in events],
                           (25, 85, 50))
    attachments = snap.get("attachments") or []
    if attachments:
        pdf.subsection("Supporting documents")
        pdf.data_table(["File", "Size", "SHA-256"],
                       [[a.get("filename"), f"{_n((a.get('size_bytes') or 0) / 1024, 1)} KB", a.get("sha256")] for a in attachments],
                       (50, 16, 104), mono=(2,))

    # ---- 3. Monitored data and parameters ---------------------------------
    pdf.section("3. Data and Parameters Monitored")
    from_signal = provenance.get("mode") == "saved_signal"
    signal_src = f"Sentinel-1 analysis {str(provenance.get('job_id', ''))[:8]}" if from_signal else "Manual entry"
    overridden = set(provenance.get("overridden_inputs") or [])
    amend = (inputs.get("project_amendments") or [[None, None]])[0]
    pdf.data_table(["Parameter", "Value", "Unit", "Source", "Reference"], [
        ["Drainage (AWD) events", inputs.get("awd_events"), "events",
         signal_src + (" (manually overridden)" if "awd_events" in overridden else ""), "Eq. 6, Table 5.12"],
        ["Cultivation period", inputs.get("season_length_days"), "days",
         signal_src + (" (manually overridden)" if "season_length_days" in overridden else ""), "Eq. 6"],
        ["Field area", _n(field["area_ha"], 4), "ha", "Registered field boundary", "Eq. 6"],
        ["Pre-season water regime", _label(inputs.get("preseason_category")), "-", "Operator declaration", "Table 5.13"],
        ["Organic amendment", f"{_label(amend[0])}, {amend[1]}", "t/ha", "Operator declaration", "Eq. 7, Table 5.14"],
        ["Synthetic N input (Q_N)", _n(inputs.get("q_n_kg_per_ha"), 1), "kg N/ha", "Operator declaration", "Eq. 25"],
        ["Emission factor EF_c", carbon.get("ef_c_used"), "kg CH4/ha/day", "IPCC 2019 default", "Eq. 6"],
    ], (42, 22, 22, 50, 30), align=("LEFT", "RIGHT", "LEFT", "LEFT", "LEFT"))

    # ---- 4. Remote-sensing evidence ----------------------------------------
    pdf.section("4. Remote Sensing Evidence (Sentinel-1 SAR)")
    if from_signal:
        facts = [
            ("Analysis run", ("mono", provenance.get("job_id"))),
            ("Completed", _date(provenance.get("finished_at"))),
            ("Detector", provenance.get("detector") or "-"),
            ("Analysis window", f"{provenance.get('window_start')} to {provenance.get('window_end')}"),
            ("Sensor", "Sentinel-1 C-band SAR GRD, IW mode, VV and VH, 10 m"),
        ]
        if signal:
            facts += [
                ("Observations", signal.get("n_observations", "-")),
                ("VV backscatter mean / std", f"{_n(signal.get('vv_mean'), 2)} dB / {_n(signal.get('vv_std'), 2)} dB"),
                ("Drydown dates", ", ".join(signal.get("awd_dates") or []) or "None detected"),
                ("Sowing / harvest", f"{signal.get('sowing_date') or '-'} / {signal.get('harvest_date') or '-'}"
                                     + ("" if signal.get("from_phenology") else " (fallback estimate)")),
            ]
        pdf.facts(facts)
        if overridden:
            pdf.note(f"Values entered manually instead of the satellite result: {', '.join(sorted(overridden))}.")
        if provenance.get("notice"):
            pdf.note(provenance["notice"])
    else:
        pdf.note(provenance.get("notice") or "No satellite analysis linked; monitored values were entered manually.")

    # ---- 5. Quantification --------------------------------------------------
    pdf.section("5. Quantification of Emission Reductions")
    if not carbon.get("qa3_pathway_valid", True):
        pdf.notice("QA3 pathway not valid: " + str(carbon.get("qa3_block_reason") or
                   "the project exceeds the 60,000 tCO2e/yr QA3 gate (Section 8.6.3)."), "red")
    else:
        pdf.data_table(["Item", "Value", "Reference"], _quantification_rows(carbon), (62, 48, 60),
                       align=("LEFT", "RIGHT", "LEFT"), emphasize_last=True)
    pdf.note("Leakage (Section 8.4) and biomass burning are not quantified by this platform; see Section 9.")

    # ---- 6. Methodology conformance ----------------------------------------
    pdf.section("6. Methodology Requirements")
    pdf.data_table(["Requirement", "Status", "Basis"],
                   [[c.get("requirement_id"), _label(c.get("status")),
                     (c.get("explanation") or "") + (f" Decided by {_who(users, c.get('decided_by'))}: {c.get('reason')}"
                                                     if c.get("decided_by") else "")]
                    for c in calc.get("readiness") or []], (60, 20, 90), mono=(0,))

    # ---- 7. Internal review (QA/QC) -----------------------------------------
    pdf.section("7. Internal Review (QA/QC)")
    if not submission:
        pdf.note("This calculation version has not been submitted for internal review.")
    else:
        pdf.facts([
            ("Submission", ("mono", submission["submission_id"])),
            ("Status", _label(submission["status"])),
            ("Submitted", f"{_date(submission['submitted_at'])} by {_who(users, submission['submitted_by'])}"),
            ("Reviewer", _who(users, submission.get("assigned_reviewer_id"))),
            ("Decision", f"{_date(submission['decided_at'])}: {submission.get('decision_reason') or '-'}"
                         if submission.get("decided_at") else "Pending"),
        ])
        if ctx.get("events"):
            pdf.subsection("Review history")
            pdf.data_table(["Date", "Change", "By", "Reason"],
                           [[_date(e["created_at"]), f"{_label(e['from_status'])} to {_label(e['to_status'])}",
                             _who(users, e["actor"]), e.get("reason") or ""] for e in ctx["events"]], (20, 46, 44, 60))
        if ctx.get("findings"):
            pdf.subsection("Findings")
            pdf.data_table(["Severity", "Finding", "Status / resolution"],
                           [[_label(f["severity"]),
                             f["description"] + (f" Requested: {f['requested_action']}" if f.get("requested_action") else ""),
                             _label(f["status"]) + (f": {f.get('close_reason')}" if f.get("close_reason") else "")]
                            for f in ctx["findings"]], (20, 95, 55))

    # ---- 8. Data integrity ---------------------------------------------------
    pdf.section("8. Data Integrity and Traceability")
    bundle = snap.get("methodology_bundle") or {}
    pdf.facts([
        ("Methodology bundle", f"{bundle.get('bundle_id', '-')} ({calc.get('methodology_version')})"),
        ("Engine version", calc.get("engine_version") or "-"),
        ("Snapshot schema", snap.get("schema_version") or "-"),
        ("Evidence fingerprint", ("mono", snap.get("evidence_fingerprint") or "-")),
        ("Snapshot SHA-256", ("mono", ctx["snapshot_sha256"])),
    ])
    documents = bundle.get("documents") or []
    if documents:
        pdf.data_table(["Source document", "Version"],
                       [[d.get("title") or d.get("document_id"), d.get("version") or "-"] for d in documents], (140, 30))
    pdf.note("Every value in this report is read from the immutable calculation snapshot, so the report can be "
             "regenerated identically; the SHA-256 lets a verifier check the exported JSON snapshot.")

    # ---- 9. Assumptions, limitations, declaration --------------------------
    pdf.section("9. Assumptions and Limitations")
    pdf.numbered(_rice_assumptions(carbon) + _RICE_LIMITATIONS)
    pdf.section("10. Declaration and Sign-off")
    pdf.paragraph(_DECLARATION)
    pdf.facts([
        ("Prepared by", f"{_who(users, calc['created_by'])}, {_date(calc['created_at'])}"),
        ("Internal reviewer", _who(users, submission.get("assigned_reviewer_id")) if submission else "-"),
        ("Internal approval", _date(submission.get("decided_at")) if final and submission else "Not yet approved"),
    ])
    return bytes(pdf.output())


def generate_project_mrv_report_vm0051(ctx: dict) -> bytes:
    """Project-level VM0051 monitoring report: aggregates the current,
    reviewable calculation of every field in the reporting period. Each
    field's own report (generate_mrv_report_vm0051) and frozen snapshot ship
    alongside it in the evidence package. `ctx` comes from
    backend/routers/export.py (_project_mrv)."""
    project, items, users = ctx["project"], ctx["included"], ctx["users"]
    final = ctx["status"] == "final"
    period = f"{ctx['period_start']} to {ctx['period_end']}"
    field = lambda i: i["calculation"]["snapshot"]["field"]
    total = lambda key: sum(float(i["calculation"]["result"].get(key) or 0) for i in items)
    area = sum(float(field(i)["area_ha"]) for i in items)
    net, gross = total("final_issuance"), total("delta_e_co2e")
    # The QA3 gate is per year. A period of up to a year holds that year's
    # seasons as they are; a longer period is averaged per year (never
    # scaled up, which would overstate a single short rice season).
    try:
        days = (datetime.date.fromisoformat(ctx["period_end"]) - datetime.date.fromisoformat(ctx["period_start"])).days + 1
    except (TypeError, ValueError):
        days = 365
    years = max(1.0, days / 365.25)
    gross_per_year = gross / years

    pdf = _MRVPDF(f"Project Monitoring Report | {project['name']}",
                  f"{_STATUS_FINAL if final else _STATUS_DRAFT} | VM0051 v1.1", draft=not final)
    pdf.title_block("Project monitoring report", project["name"], f"{_METHODOLOGY}\nMonitoring period {period}")
    pdf.notice("FINAL - every included field calculation is internally approved." if final else
               "DRAFT - not every included field calculation is internally approved. "
               "Not for submission to a registry or VVB.", "green" if final else "amber")
    pdf.facts([
        ("Project ID", ("mono", project["project_id"])),
        ("Geography", project.get("geography") or "-"),
        ("Description", project.get("description") or "-"),
        ("Monitoring period", period),
        ("Fields reported", f"{len(items)} ({_n(area, 2)} ha)"),
        ("Net emission reductions", f"{_n(net, 4)} tCO2e (calculated estimate, not issued credits)"),
        ("Report status", "Final" if final else "Draft"),
        ("Generated by", ctx.get("generated_by") or "-"),
    ])

    pdf.section("1. Fields in this Monitoring Period")
    pdf.data_table(["Field", "Area (ha)", "Monitoring period", "AWD events", "Net tCO2e", "Internal review"],
                   [[f"{field(i)['name']} ({i['calculation']['field_id']})", _n(field(i)["area_ha"], 2),
                     f"{i['calculation']['monitoring_period_start']} to {i['calculation']['monitoring_period_end']}",
                     i["calculation"]["snapshot"]["engine_inputs"].get("awd_events"),
                     _n(i["calculation"]["result"].get("final_issuance"), 4), _label(i["review_status"])] for i in items]
                   + [["Total", _n(area, 2), " ", " ", _n(net, 4), " "]],
                   (44, 18, 40, 16, 24, 28), align=("LEFT", "RIGHT", "LEFT", "RIGHT", "RIGHT", "LEFT"), emphasize_last=True)
    if ctx.get("excluded"):
        pdf.subsection("Project fields not included")
        pdf.data_table(["Field", "Reason"], [[f"{e['name']} ({e['field_id']})", e["reason"]] for e in ctx["excluded"]],
                       (70, 100))

    pdf.section("2. Quantification of Emission Reductions")
    pdf.data_table(["Item", "Value (sum of fields)", "Reference"], _quantification_rows({
        key: total(key) for key in ("e_baseline", "e_project", "delta_e_ch4", "delta_e_co2e", "unc_tco2e",
                                    "pe_n2o_tco2e", "final_issuance")}), (62, 48, 60),
        align=("LEFT", "RIGHT", "LEFT"), emphasize_last=True)
    pdf.facts([
        ("Gross reductions per year", f"{_n(gross_per_year, 2)} tCO2e/yr"
                                      + (f" (period of {days} days averaged over {years:.2f} years)" if years > 1 else "")),
        ("QA3 project-size limit", f"{_n(_QA3_PROJECT_GATE_TCO2E, 0)} tCO2e/yr (Section 8.6.3)"),
    ])
    if gross_per_year > _QA3_PROJECT_GATE_TCO2E:
        pdf.notice(f"Project gross reductions ({_n(gross_per_year, 0)} tCO2e/yr) exceed the QA3 "
                   f"{_n(_QA3_PROJECT_GATE_TCO2E, 0)} tCO2e/yr limit (Section 8.6.3): the flat 15% uncertainty "
                   "deduction is not valid at this size.", "red")
    else:
        pdf.notice("Within the QA3 project-size limit: the flat 15% uncertainty deduction applies.", "green")
    pdf.note("Per-field parameters, satellite evidence and equation detail are in each field's monitoring report "
             "(evidence package folder fields/<field_id>/).")

    pdf.section("3. Monitoring Approach")
    pdf.paragraph(_RICE_METHOD_TEXT)

    pdf.section("4. Internal Review (QA/QC)")
    pdf.data_table(["Field", "Version", "Reviewer", "Status", "Decided"],
                   [[field(i)["name"], f"v{i['calculation']['version']}",
                     _who(users, i["submission"].get("assigned_reviewer_id")) if i.get("submission") else "-",
                     _label(i["review_status"]),
                     _date(i["submission"].get("decided_at")) if i.get("submission") and i["submission"].get("decided_at") else "-"]
                    for i in items], (46, 16, 52, 32, 24))

    pdf.section("5. Methodology Requirements Across Fields")
    statuses: dict[str, dict[str, int]] = {}
    for i in items:
        for c in i["calculation"].get("readiness") or []:
            counts = statuses.setdefault(c["requirement_id"], {})
            counts[c["status"]] = counts.get(c["status"], 0) + 1
    pdf.data_table(["Requirement", "Status across fields"],
                   [[rid, ", ".join(f"{_label(k)}: {v}" for k, v in sorted(counts.items()))]
                    for rid, counts in sorted(statuses.items())], (85, 85), mono=(0,))
    pdf.note("Requirements marked 'Unsupported' are not quantified by this platform; address them in the project "
             "documentation (Section 6), e.g. the leakage assessment and other emission sources.")

    pdf.section("6. Project Documentation")
    categories, documents = ctx.get("document_categories") or {}, ctx.get("documents") or []
    if documents:
        pdf.data_table(["Document", "Title", "File", "SHA-256"],
                       [[categories.get(d["category"], _label(d["category"])), d["title"], d["filename"], d["sha256"]]
                        for d in documents], (34, 36, 34, 66), mono=(3,))
    expected = ["pdd", "monitoring_plan", "additionality", "land_tenure", "leakage"]
    missing = [categories.get(c, c) for c in expected if not any(d["category"] == c for d in documents)]
    if missing:
        pdf.notice("Not yet provided: " + ", ".join(missing) + ". A verifier will normally expect these.", "amber")
    pdf.note("Project documents are included in the evidence package (folder project-documents/).")

    pdf.section("7. Evidence Package and Data Integrity")
    pdf.data_table(["Field", "Calculation", "Snapshot SHA-256"],
                   [[field(i)["name"], i["calculation"]["calculation_id"][:12], i["snapshot_sha256"]] for i in items],
                   (34, 26, 110), mono=(1, 2))
    pdf.note("The evidence package (ZIP) holds this report, each field's monitoring report, each frozen calculation "
             "snapshot (JSON), the Sentinel-1 analysis results, the attached field documents, and manifest.json "
             "listing the SHA-256 of every file.")

    pdf.section("8. Assumptions and Limitations")
    sample = items[0]["calculation"]["result"] if items else {"ef_c_used": "-"}
    pdf.numbered(_rice_assumptions(sample) + _RICE_LIMITATIONS)
    pdf.section("9. Declaration")
    pdf.paragraph(_DECLARATION)
    return bytes(pdf.output())


def generate_pdf_alm(
    field_info: dict,
    meta: dict,
    practice_schedule: dict,
    carbon: dict,
    livestock_schedule: dict = None,
) -> bytes:
    """
    field_info : {field_id, name, district, area_ha}
    meta       : {verification_years, non_permanence_risk_pct}
    practice_schedule : {'baseline': {...}, 'project': {...}} — see
                 src.persistence.database.ALM_PRACTICE_COLUMNS for keys
    carbon     : return dict of AlmCarbonEngine.calculate_credits()
    livestock_schedule : {'baseline': [...], 'project': [...]} of
                 {"livestock_type", "population_head", "productivity_system"}
                 dicts, or None if no livestock is tracked for this field
    """
    livestock_schedule = livestock_schedule or {"baseline": [], "project": []}
    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.methodology_label = "Verra VM0042 v2.2"
    pdf.set_margins(left=18, top=20, right=18)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(20, 40, 80)
    pdf.ln(2)
    pdf.cell(
        0, 10, "Verra VM0042 v2.2 - Improved ALM Monitoring Report",
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

    pdf.section("1. Field Information")
    pdf.kv("Field ID",   field_info["field_id"])
    pdf.kv("Field Name", field_info["name"])
    pdf.kv("District",   field_info["district"])
    pdf.kv("Area",       f"{field_info['area_ha']:.4f} ha")
    pdf.kv("Verification Period", f"{meta['verification_years']:.0f} year(s)")
    pdf.kv("Non-Permanence Risk Rating", f"{meta['non_permanence_risk_pct']:.0f}%  (user-supplied, not computed by this app)")
    if meta.get("calculation_id"):
        pdf.kv("Calculation", meta["calculation_id"])
        pdf.kv("Internal status", meta["status"])
        period = meta["monitoring_period"]
        pdf.kv("Monitoring dates", f"{period['start']} to {period['end']}")
        pdf.kv("Methodology bundle", (meta.get("methodology_bundle") or {}).get("bundle_id", "unknown"))
        pdf.banner("CALCULATION ESTIMATE - not external verification or registry issuance.", ok=False)
        for check in meta.get("readiness", []):
            if check.get("status") not in ("satisfied", "not_applicable"):
                pdf.kv(check["requirement_id"], check["status"] + ": " + check["explanation"])

    pdf.section("2. Practice Schedule (Table 4 subset)")
    for scenario_label, key in [("Baseline", "baseline"), ("Project", "project")]:
        p = practice_schedule.get(key) or {}
        pdf.kv(f"{scenario_label} — Crop type", p.get("crop_type") or "N/A")
        pdf.kv(f"{scenario_label} — Tillage / residue burned",
               f"{'Yes' if p.get('tillage') else 'No'} / {p.get('residue_burned_kg_ha') or 0:.0f} kg/ha")
        pdf.kv(f"{scenario_label} — Synthetic / organic N rate",
               f"{p.get('synthetic_n_rate_kg_ha') or 0:.1f} / {p.get('organic_n_rate_kg_ha') or 0:.1f} kg N/ha")
        pdf.kv(f"{scenario_label} — N-fixing cover crop",
               "Yes" if p.get("n_fixing_species") else "No")
        pdf.kv(f"{scenario_label} — Crop yield",
               f"{p['crop_yield_t_ha']:.2f} t/ha" if p.get("crop_yield_t_ha") is not None else "Not tracked")
        livestock = livestock_schedule.get(key) or []
        if livestock:
            summary = ", ".join(
                f"{e['population_head']:.0f} {e['livestock_type']} ({e['productivity_system']})"
                for e in livestock
            )
            pdf.kv(f"{scenario_label} — Livestock (pasture-based)", summary)
        pdf.ln(1)

    pdf.section("3. Carbon Estimation (Verra VM0042 v2.2)")

    if carbon.get("production_decline_leakage_blocked"):
        pdf.banner("ISSUANCE BLOCKED: " + carbon.get("leakage_block_reason", ""), ok=False)
        return bytes(pdf.output())

    pdf.kv("EF_Ndirect used (conservative, Eqs. 17-25)", f"{carbon['ef_ndirect_used']}")
    pdf.kv("N2O fertilizer (baseline -> project)", f"{carbon['n2o_fert_bsl']:.4f} -> {carbon['n2o_fert_wp']:.4f} tCO2e")
    pdf.kv("N2O N-fixing residues (baseline -> project)", f"{carbon['n2o_nfix_bsl']:.4f} -> {carbon['n2o_nfix_wp']:.4f} tCO2e")
    pdf.kv("CH4 / N2O biomass burning (baseline -> project)",
           f"{carbon['ch4_bb_bsl']:.4f}->{carbon['ch4_bb_wp']:.4f} / {carbon['n2o_bb_bsl']:.4f}->{carbon['n2o_bb_wp']:.4f} tCO2e")
    pdf.kv("CO2 fossil fuel (baseline -> project)", f"{carbon['co2_ff_bsl']:.4f} -> {carbon['co2_ff_wp']:.4f} tCO2e")
    if "co2_lime_bsl" in carbon:
        pdf.kv("CO2 liming (baseline -> project)",
               f"{carbon['co2_lime_bsl']:.4f} -> {carbon['co2_lime_wp']:.4f} tCO2e  (§8.2.4 Eq. 8/9, §8.5.3 Eq. 53)")
    pdf.kv("CH4 enteric fermentation (baseline -> project)", f"{carbon['ch4_ent_bsl']:.4f} -> {carbon['ch4_ent_wp']:.4f} tCO2e  (§8.2.6 Eq. 11)")
    pdf.kv("CH4 manure, pasture (baseline -> project)", f"{carbon['ch4_manure_bsl']:.4f} -> {carbon['ch4_manure_wp']:.4f} tCO2e  (§8.2.7 Eq. 12/13)")
    pdf.kv("N2O manure, pasture (baseline -> project)", f"{carbon['n2o_manure_bsl']:.4f} -> {carbon['n2o_manure_wp']:.4f} tCO2e  (Ch 11 Eq. 11.5, EF3PRP)")
    pdf.ln(2)
    pdf.kv("SOC stock change (baseline, Approach 2)", f"{carbon['delta_co2_soil_bsl']:.4f} tCO2e (Eqs. 46-47)")
    pdf.kv("SOC stock change (project, Approach 2)", f"{carbon['delta_co2_soil_wp']:.4f} tCO2e (Eqs. 46-47)")
    pdf.kv("SOC uncertainty deduction", f"{carbon['unc_co2_pct']:.1f}%  (Eqs. 70-71, 74)")
    pdf.ln(2)
    leakage = carbon.get("leakage") or {}
    if leakage.get("integrated"):
        pdf.kv("Leakage module", "VMD0054 v" + leakage.get("module_version", "unknown"))
        pdf.kv("Cumulative displacement leakage", f"{leakage['cumulative_leakage_tco2e']:.4f} tCO2e")
        pdf.kv("Prior verified cumulative leakage", f"{leakage['prior_cumulative_leakage_tco2e']:.4f} tCO2e")
        pdf.kv("Annual displacement deduction (Eq.36)", f"{carbon['lk_disp_t']:.4f} tCO2e/year")
        pdf.kv("Leakage allocation ER / CR (corrected Eqs.39/42)", f"{carbon['lk_er_t']:.4f} / {carbon['lk_cr_t']:.4f} tCO2e/year")
        pdf.kv("Step 2", "No mitigation claimed: " + leakage.get("step2", {}).get("reason", ""))
        pdf.kv("Step 4", leakage.get("step4_status", "unknown"))
        pdf.kv("Assessment reference", leakage.get("assessment_id", ""))
        pdf.kv("Source", leakage.get("source", ""))
    else:
        pdf.banner("Historical scalar leakage screen only; no integrated leakage evidence attached.", ok=False)
    pdf.banner("OTHER LEAKAGE NOT SCREENED: " + carbon.get("other_leakage_gap_note", ""), ok=False)
    pdf.kv("Net Emission Reductions (ER_t)", f"{carbon['er_t']:.4f} tCO2e  (Eq. 37, other-leakage unscreened)")
    pdf.kv("Net Removals (CR_t)", f"{carbon['cr_t']:.4f} tCO2e  (Eq. 40, other-leakage unscreened)")
    pdf.kv("Net Reductions + Removals (ERR_NET,t)", f"{carbon['err_net']:.4f} tCO2e  (Eq. 43)")
    pdf.kv("Cumulative project SOC change (I(dCO2wp) basis)", f"{carbon['cumulative_delta_co2_wp']:.4f} tCO2e  (Eq. 37/40)")
    pdf.kv("Buffer deduction (ER / CR)", f"{carbon['bu_er']:.4f} / {carbon['bu_cr']:.4f} tCO2e  (Eqs. 75-76)")
    pdf.kv("SOC remeasurement cadence", "Compliant (<=5 yr)" if carbon.get("cadence_compliant", True) else "NON-COMPLIANT (>5 yr)")
    pdf.ln(2)
    pdf.kv("ESTIMATED NET RESULT (VCU_t)", f"{carbon['final_issuance']:.4f} tCO2e  (Eqs. 77-79)")

    if carbon["final_issuance"] == 0.0:
        pdf.banner(
            "No positive calculated estimate after uncertainty and buffer deductions.",
            ok=False,
        )
    else:
        pdf.banner(
            f"ESTIMATE: {carbon['final_issuance']:.4f} tCO2e. Internal readiness and external verification are separate.",
            ok=True,
        )

    pdf.section("4. Methodology")
    pdf.body(
        "Terra-Audit implements a scoped subset of the Verra VM0042 v2.2 Improved "
        "Agricultural Land Management methodology, covering tillage/residue "
        "management, fertilizer management, crop planting/harvesting "
        "(rotations, cover crops), and pasture-based integrated crop-livestock "
        "practice changes. N2O from fertilizer and N-fixing residues, CH4/N2O "
        "from biomass burning, CO2 from fossil fuel combustion, and CH4/N2O "
        "from enteric fermentation and manure deposited on pasture (§8.2.6/"
        "§8.2.7, Ch 11 Eq. 11.5) are quantified via Quantification Approach 3 "
        "default emission factors (IPCC 2019 Refinement), using the most "
        "conservative EF within the cited uncertainty range per §8.6.3 where "
        "applicable. Soil organic carbon "
        "(SOC) - the mandatory, non-de-minimis carbon pool - is quantified via "
        "Quantification Approach 2 (measure and remeasure), from lab-measured "
        "paired samples at the project site and a baseline control site. Net "
        "reductions and removals follow Eqs. 37/40/43, with a buffer deduction "
        "against the user-supplied non-permanence risk rating per Eqs. 75-79."
    )

    pdf.section("5. Assumptions and Limitations")
    for i, a in enumerate([
        "Integrated crop-livestock is modeled for pasture-based grazing only "
        "(cattle, buffalo, sheep, goats). Feedlots and non-pasture manure "
        "systems (drylot/slurry/digester) are out of scope. Liming and "
        "Quantification Approach 1 (external biogeochemical model) are also "
        "out of scope - not modeled",
        "Production-decline leakage (§8.4.3, VMD0054) is screened when crop "
        "yield is entered for both scenarios (Steps 1-2: zero if yield is "
        "maintained/improved). A genuine decline blocks issuance rather than "
        "estimating it, since VMD0054's Steps 3-5 need regional forest-biomass "
        "and IPCC Tier 1 SOC change-factor defaults not sourced in this app. "
        "Leakage from organic amendment import and livestock/biomass "
        "displacement is NOT screened or computed at all.",
        "The entire field is treated as a single quantification unit / "
        "stratum (permitted per §8.1); no sub-field stratification",
        "SOC uncertainty (Eqs. 70-71) conservatively assumes zero covariance "
        "between start/end-of-period samples",
        "Approach-3 (default-factor) terms carry no separate uncertainty "
        "deduction per §8.6.3, contingent on full activity-data coverage",
        "VM0042 excludes wetlands (§4, condition 8) - this field type must "
        "not be used for flooded rice paddies",
        "This report is generated by an AI-assisted analytical platform and "
        "requires expert agronomist / soil scientist review before formal "
        "registry submission",
    ], 1):
        pdf.set_x(pdf.l_margin + 8)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, f"{i}. {_s(a)}", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def generate_audit_json_alm(
    field_info: dict,
    meta: dict,
    practice_schedule: dict,
    soc_measurements: dict,
    carbon: dict,
    livestock_schedule: dict = None,
) -> str:
    record = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "platform": "Terra-Audit v1.0",
        "methodology": "Verra VM0042 v2.2 (scoped subset)",
        "field": field_info,
        "verification_period_years": meta["verification_years"],
        "non_permanence_risk_pct": meta["non_permanence_risk_pct"],
        "practice_schedule": practice_schedule,
        "livestock_schedule": livestock_schedule or {"baseline": [], "project": []},
        "soc_measurements": {
            f"{site_type}_{timepoint}": values
            for (site_type, timepoint), values in soc_measurements.items()
        },
        "carbon_calculation": {k: v for k, v in carbon.items()},
    }
    return json.dumps(record, indent=2, default=str)


def generate_alm_data_csv(practice_schedule: dict, soc_measurements: dict) -> str:
    """Flat CSV of the practice schedule and SOC sample rows for auditors."""
    lines = ["section,scenario_or_site,field,value"]
    for scenario, practices in (practice_schedule or {}).items():
        for field, value in (practices or {}).items():
            lines.append(f"practice_schedule,{scenario},{field},{value}")
    for (site_type, timepoint), values in (soc_measurements or {}).items():
        for i, v in enumerate(values):
            lines.append(f"soc_measurement,{site_type}_{timepoint},sample_{i},{v}")
    return "\n".join(lines) + "\n"
