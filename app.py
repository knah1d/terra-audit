import os
os.environ["USE_FOLIUM"] = "1"

import datetime
import json

import pandas as pd
import streamlit as st
import geemap.foliumap as geemap
import plotly.graph_objects as go

from src.database import get_db_connection, check_cache, save_cache
from src.data_engine import SpatialDataEngine
from src.threshold_gate import AdaptiveAWDGate
from src.carbon_calculator import CarbonAssetEngine

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="terra-audit Platform")

st.markdown("""
    <style>
    .metric-container {
        background-color: #1e222b;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #3e4451;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🛰️ terra-audit // High-Fidelity Processing Pipeline")
st.caption("Verra VM0051 Digital Compliance Sandbox // Phase 2 Engine Core")

# ---------------------------------------------------------------------------
# Module initialisation (cached for the lifetime of the Streamlit process)
# ---------------------------------------------------------------------------
@st.cache_resource
def init_modules():
    try:
        return SpatialDataEngine(), AdaptiveAWDGate(), CarbonAssetEngine(), None
    except Exception as exc:
        return None, None, None, str(exc)

engine, gate, carbon_engine, init_error = init_modules()

if init_error:
    st.error(f"Failed to start: {init_error}")
    st.info("💡 **How to fix this:** Link your Google Earth Engine account to a Cloud Project.")
    st.code("earthengine set_project YOUR_PROJECT_ID", language="bash")
    st.markdown(
        "If you don't know your Project ID, visit the "
        "[Google Cloud Console](https://console.cloud.google.com/) and create one."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Seed default fields (one atomic DB transaction)
# ---------------------------------------------------------------------------
DEFAULT_FIELDS = {
    "F-101": {
        "name": "Mymensingh Reference Parcel Alpha",
        "district": "Mymensingh",
        "geojson": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"name": "Mymensingh Reference Parcel Alpha"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[90.4100, 24.7500], [90.4150, 24.7500],
                                     [90.4150, 24.7550], [90.4100, 24.7550],
                                     [90.4100, 24.7500]]]
                }
            }]
        }
    },
    "F-102": {
        "name": "Faridpur Custom Zone Beta",
        "district": "Faridpur",
        "geojson": {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"name": "Faridpur Custom Zone Beta"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[89.5785, 23.0912], [89.5825, 23.0912],
                                     [89.5825, 23.0952], [89.5785, 23.0952],
                                     [89.5785, 23.0912]]]
                }
            }]
        }
    },
}

with get_db_connection() as conn:
    existing_ids = {
        r["field_id"]
        for r in conn.execute("SELECT field_id FROM fields").fetchall()
    }
    seeded = False
    for fid, meta in DEFAULT_FIELDS.items():
        if fid not in existing_ids:
            conn.execute(
                "INSERT OR IGNORE INTO fields "
                "(field_id, name, district, geojson_geometry) VALUES (?,?,?,?)",
                (fid, meta["name"], meta["district"], json.dumps(meta["geojson"])),
            )
            seeded = True
    if seeded:
        conn.commit()
        st.rerun()

# ---------------------------------------------------------------------------
# Load field list
# ---------------------------------------------------------------------------
with get_db_connection() as conn:
    fields = conn.execute(
        "SELECT field_id, name, district FROM fields ORDER BY field_id"
    ).fetchall()

field_display = {f["field_id"]: f for f in fields}

# ---------------------------------------------------------------------------
# Sidebar — Active Field Tracker
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🛰️ Active Field Tracker")
    st.markdown("---")

    selected_id = st.radio(
        "Select Monitoring Parcel",
        options=[f["field_id"] for f in fields],
        format_func=lambda fid: f"{fid}  —  {field_display[fid]['name']}",
        label_visibility="collapsed",
    )

    sf = field_display[selected_id]
    st.markdown("---")
    st.markdown(f"""
    <div style="background:#1e222b;border-radius:8px;padding:12px 14px;border:1px solid #3e4451;">
        <div style="color:#aaa;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Selected Parcel</div>
        <div style="color:#00ffcc;font-size:17px;font-weight:700;margin:4px 0">{sf['field_id']}</div>
        <div style="color:#eee;font-size:13px;">{sf['name']}</div>
        <div style="color:#888;font-size:12px;margin-top:6px;">📍 {sf['district']} District</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("")

# ---------------------------------------------------------------------------
# Load geometry for selected field
# ---------------------------------------------------------------------------
with get_db_connection() as conn:
    row = conn.execute(
        "SELECT geojson_geometry FROM fields WHERE field_id = ?", (selected_id,)
    ).fetchone()

geom = json.loads(row["geojson_geometry"])

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab_map, tab_signal, tab_carbon = st.tabs([
    "🌍 Spatial Asset Inspection",
    "📈 Statistical Signal Analytics",
    "💰 Carbon Asset Ledger",
])

# ===========================================================================
# TAB 1 — MAP
# ===========================================================================
with tab_map:
    if "features" in geom:
        coords = geom["features"][0]["geometry"]["coordinates"][0]
    elif "geometry" in geom:
        coords = geom["geometry"]["coordinates"][0]
    else:
        coords = geom["coordinates"][0]

    lats = [c[1] for c in coords]
    lons = [c[0] for c in coords]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    m = geemap.Map(center=[center_lat, center_lon], zoom=14)
    m.add_geojson(geom, layer_name="Target Polygon Boundary")
    m.to_streamlit(height=420)

# ===========================================================================
# TAB 2 — SIGNAL ANALYTICS
# ===========================================================================
with tab_signal:
    col_inputs, col_pipeline = st.columns([1, 2])

    # ---- Inputs panel -------------------------------------------------------
    with col_inputs:
        st.markdown("### Execution Scope")

        SEASON_PRESETS = {
            "🌾 Boro 2025  (Jan – May)":         ("2025-01-01", "2025-05-31"),
            "🌿 Aman 2024  (Jul – Nov)":          ("2024-07-01", "2024-11-30"),
            "☀️ Pre-Kharif 2024  (Mar – Jun)":   ("2024-03-01", "2024-06-30"),
            "🌾 Boro 2024  (Jan – May)":          ("2024-01-01", "2024-05-31"),
            "🗓️ Custom Range":                   None,
        }

        season_choice = st.selectbox(
            "Cropping Season Preset",
            options=list(SEASON_PRESETS.keys()),
            help="Select a rice season to auto-fill the analysis window, "
                 "or choose Custom Range for manual dates.",
        )

        preset_dates = SEASON_PRESETS[season_choice]
        if preset_dates:
            start_date = datetime.date.fromisoformat(preset_dates[0])
            end_date   = datetime.date.fromisoformat(preset_dates[1])
            st.caption(f"📅 Window: `{preset_dates[0]}` → `{preset_dates[1]}`")
        else:
            SENTINEL_START = datetime.date(2014, 10, 3)
            TODAY          = datetime.date.today()
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                start_date = st.date_input(
                    "Open",
                    value=datetime.date(2025, 1, 1),
                    min_value=SENTINEL_START,
                    max_value=TODAY,
                )
            with col_d2:
                end_date = st.date_input(
                    "Close",
                    value=datetime.date(2025, 5, 31),
                    min_value=SENTINEL_START,
                    max_value=TODAY,
                )
            if start_date >= end_date:
                st.warning("⚠️ Close date must be after Open date.")

        st.markdown("")
        field_area_ha = st.number_input(
            "Field Area (ha)",
            min_value=0.1,
            max_value=500.0,
            value=1.0,
            step=0.1,
            help="Measured area of the polygon in hectares — used in all carbon calculations.",
        )
        force_refresh = st.checkbox("Bypass Local Database Cache")
        date_valid    = (start_date < end_date) if preset_dates is None else True
        trigger       = st.button(
            "Run Analytics Engine", type="primary", disabled=not date_valid
        )

    # ---- Analytics execution ------------------------------------------------
    if trigger:
        sd_str = str(start_date)
        ed_str = str(end_date)

        df_processed  = pd.DataFrame()
        cache_source  = "Local relational data store"

        with st.spinner("Resolving spatial asset data timeline..."):
            if not force_refresh:
                df_processed = check_cache(selected_id, sd_str, ed_str)

            if df_processed.empty:
                cache_source = "Live Google Earth Engine Core API"
                df_raw = engine.extract_clean_timeseries(geom, sd_str, ed_str)
                if not df_raw.empty:
                    save_cache(selected_id, df_raw, sd_str, ed_str)
                    df_processed = check_cache(selected_id, sd_str, ed_str)

        if not df_processed.empty:
            df_final = gate.analyze_irrigation_behavior(df_processed)
            df_final = gate.extract_phenology(df_final)

            total_awd = int(df_final["drydown_event"].sum())

            sowing_row  = df_final[df_final["is_sowing"]  == 1]
            harvest_row = df_final[df_final["is_harvest"] == 1]

            sowing_date_str  = sowing_row["date"].iloc[0]  if not sowing_row.empty  else "N/A"
            harvest_date_str = harvest_row["date"].iloc[0] if not harvest_row.empty else "N/A"

            season_length_val       = 120          # safe fallback
            season_length_str       = "N/A"
            season_from_phenology   = False

            if not sowing_row.empty and not harvest_row.empty:
                s_dt = pd.to_datetime(sowing_date_str)
                h_dt = pd.to_datetime(harvest_date_str)
                season_length_val     = (h_dt - s_dt).days
                season_length_str     = f"{season_length_val} Days"
                season_from_phenology = True

            # ---- Key metrics ------------------------------------------------
            with col_pipeline:
                st.markdown(f"**Data Source Provenance:** `{cache_source}`")
                if not season_from_phenology:
                    st.warning(
                        "⚠️ Phenology markers could not be detected in this window. "
                        "Season length is **using the fallback of 120 days** in carbon "
                        "calculations — verify manually."
                    )
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("AWD Sequences",   total_awd)
                col2.metric("Sowing Date",     sowing_date_str)
                col3.metric("Harvest Date",    harvest_date_str)
                col4.metric("Season Length",   season_length_str or "120 Days (fallback)")

            # ---- Chart -------------------------------------------------------
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=df_final["date"], y=df_final["vv"],
                mode="markers", name="Raw VV Backscatter",
                marker=dict(color="rgba(255,255,255,0.3)", size=5),
            ))
            fig.add_trace(go.Scatter(
                x=df_final["date"], y=df_final["vv_smoothed"],
                mode="lines+markers", name="VV Filter Curve (Flooding)",
                line=dict(color="#00ffcc", width=2.5),
            ))

            if "vh_smoothed" in df_final.columns:
                fig.add_trace(go.Scatter(
                    x=df_final["date"], y=df_final["vh_smoothed"],
                    mode="lines", name="VH Filter Curve (Phenology)",
                    line=dict(color="#ff66cc", width=2, dash="dash"),
                ))

            events = df_final[df_final["drydown_event"] == 1]
            if not events.empty:
                fig.add_trace(go.Scatter(
                    x=events["date"], y=events["vv_smoothed"],
                    mode="markers", name="Drainage Marker",
                    marker=dict(color="#ffcc00", size=14, symbol="star"),
                ))

            if not sowing_row.empty and "vh_smoothed" in df_final.columns:
                fig.add_trace(go.Scatter(
                    x=sowing_row["date"], y=sowing_row["vh_smoothed"],
                    mode="markers", name="Sowing Date",
                    marker=dict(color="#00ff00", size=16, symbol="triangle-up",
                                line=dict(width=2, color="white")),
                ))

            if not harvest_row.empty and "vh_smoothed" in df_final.columns:
                fig.add_trace(go.Scatter(
                    x=harvest_row["date"], y=harvest_row["vh_smoothed"],
                    mode="markers", name="Harvest Date",
                    marker=dict(color="#ff4444", size=16, symbol="triangle-down",
                                line=dict(width=2, color="white")),
                ))

            fig.update_layout(
                template="plotly_dark",
                height=450,
                xaxis_title="Sentinel-1 Overpass Date",
                yaxis_title="Backscatter Energy (dB)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)

            # ---- Audit trail JSON -------------------------------------------
            audit_cols = ["date", "vv_smoothed", "vv_zscore",
                          "is_flooded", "drydown_event", "is_sowing", "is_harvest"]
            if "vh_smoothed" in df_final.columns:
                audit_cols.insert(2, "vh_smoothed")
            st.markdown("### Compliance Audit Trail Ledger")
            st.json(df_final[audit_cols].to_dict(orient="records")[:5])

            # ---- Pass values to Carbon tab via session state -----------------
            st.session_state["carbon_ready"]           = True
            st.session_state["carbon_total_awd"]       = total_awd
            st.session_state["carbon_season_length"]   = season_length_val
            st.session_state["carbon_area_ha"]         = field_area_ha
            st.session_state["season_from_phenology"]  = season_from_phenology

        else:
            with col_pipeline:
                st.error("No valid Sentinel-1 observations found for this field and window.")

# ===========================================================================
# TAB 3 — CARBON ASSET LEDGER
# ===========================================================================
with tab_carbon:
    st.markdown("### 💰 Carbon Compliance Ledger (VM0051)")
    st.write(
        "Parameters are auto-populated from the Signal Analytics engine after you run it. "
        "You can also override them manually and click **Calculate Carbon Credits**."
    )
    st.markdown("---")

    st.markdown("#### ⚙️ Calculation Parameters")
    st.caption("Auto-filled from signal engine. Override as needed.")

    default_season  = int(st.session_state.get("carbon_season_length", 120))
    default_awd     = int(st.session_state.get("carbon_total_awd", 0))
    default_area    = float(st.session_state.get("carbon_area_ha", 1.0))
    from_phenology  = st.session_state.get("season_from_phenology", False)

    if not from_phenology and st.session_state.get("carbon_ready"):
        st.warning(
            "⚠️ Season length was not detected from phenology — "
            f"the value **{default_season} days** is a fallback estimate. "
            "Adjust manually if you know the actual season length."
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        carbon_season   = st.number_input("Season Length (days)", 1, 365, default_season, step=1)
    with c2:
        carbon_area     = st.number_input("Field Area (ha)", 0.1, 500.0, default_area, step=0.1)
    with c3:
        carbon_awd      = st.number_input("AWD Events (verified)", 0, 20, default_awd, step=1)
    with c4:
        carbon_accuracy = st.slider("Model Confidence (%)", 70.0, 100.0, 92.0, step=0.5)

    run_carbon = st.button("⚡ Calculate Carbon Credits", type="primary")

    if run_carbon or st.session_state.get("carbon_ready"):
        cr = carbon_engine.calculate_credits(
            awd_events=carbon_awd,
            season_length_days=carbon_season,
            area_ha=carbon_area,
            ai_accuracy=carbon_accuracy,
        )

        st.markdown("---")

        # Summary metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Baseline Emissions",  f"{cr['e_baseline']:.2f} kg CH₄")
        m2.metric("Project Emissions",   f"{cr['e_project']:.2f} kg CH₄")
        m3.metric("Avoided (tCO₂e)",     f"{cr['delta_e_co2e']:.3f}")
        m4.metric("Final Credits Issued", f"{cr['final_issuance']:.3f}")

        st.markdown("---")
        st.markdown("#### 📐 Step-by-Step Audit Trail")

        # Step 1
        st.markdown("**Step 1: Baseline Scenario** — continuous flooding, $SF_w = 1.0$")
        st.latex(r"E_{\text{baseline}} = EF_c \times SF_{w,\text{baseline}} \times D \times A")
        st.latex(
            f"E_{{\\text{{baseline}}}} = 1.4 \\times 1.0 \\times {carbon_season}"
            f" \\times {carbon_area:.1f} = {cr['e_baseline']:.2f}\\text{{ kg CH}}_4"
        )

        # Step 2
        st.markdown(
            f"**Step 2: Project Scenario** — {carbon_awd} AWD event(s) "
            f"→ $SF_{{w,\\text{{project}}}} = {cr['sf_w_project']}$"
        )
        st.latex(r"E_{\text{project}} = EF_c \times SF_{w,\text{project}} \times D \times A")
        st.latex(
            f"E_{{\\text{{project}}}} = 1.4 \\times {cr['sf_w_project']}"
            f" \\times {carbon_season} \\times {carbon_area:.1f}"
            f" = {cr['e_project']:.2f}\\text{{ kg CH}}_4"
        )

        # Step 3
        st.markdown("**Step 3: Net Methane Avoided**")
        st.latex(r"\Delta E_{\text{CH}_4} = E_{\text{baseline}} - E_{\text{project}}")
        st.latex(
            f"\\Delta E_{{\\text{{CH}}_4}} = {cr['e_baseline']:.2f}"
            f" - {cr['e_project']:.2f} = {cr['delta_e_ch4']:.2f}\\text{{ kg CH}}_4"
        )

        # Step 4
        st.markdown("**Step 4: Convert to tCO₂e** — IPCC AR5 GWP₁₀₀ = 28 for CH₄")
        st.latex(
            r"\Delta E_{\text{CO}_2\text{e}} = "
            r"\frac{\Delta E_{\text{CH}_4} \times GWP_{\text{CH}_4}}{1000}"
        )
        st.latex(
            f"\\Delta E_{{\\text{{CO}}_2\\text{{e}}}} = "
            f"\\frac{{{cr['delta_e_ch4']:.2f} \\times 28}}{{1000}}"
            f" = {cr['delta_e_co2e']:.3f}\\text{{ tCO}}_2\\text{{e}}"
        )

        # Step 5
        st.markdown(f"**Step 5: Conservativeness Penalty** — Confidence: {carbon_accuracy:.1f}%")
        st.info(
            f"Penalty applied: **{int(cr['p_uncertainty'] * 100)}%** "
            f"→ retention multiplier = {1 - cr['p_uncertainty']:.2f}"
        )
        st.latex(
            r"\text{Final Credits} = \Delta E_{\text{CO}_2\text{e}} \times (1 - P_{\text{uncertainty}})"
        )
        st.latex(
            f"\\text{{Final Issuance}} = {cr['delta_e_co2e']:.3f}"
            f" \\times (1 - {cr['p_uncertainty']:.2f})"
            f" = \\mathbf{{{cr['final_issuance']:.3f}\\text{{ tCO}}_2\\text{{e}}}}"
        )

        # Outcome banner
        if cr["p_uncertainty"] == 1.0:
            st.error(
                "🚫 **Audit Failure** — Model confidence below 85 %. "
                "Zero credits issued. Requires manual field verification before resubmission."
            )
        elif cr["final_issuance"] == 0.0:
            st.info(
                "ℹ️ No AWD events verified — project emissions equal baseline. "
                "Zero carbon credits issued (no methane reduction demonstrated)."
            )
        else:
            st.success(
                f"🎉 **{cr['final_issuance']:.3f} tCO₂e** in Verified Carbon Credits — "
                "ready for registry submission."
            )
    else:
        st.info(
            "ℹ️ Run the **Analytics Engine** (Signal tab) to auto-populate fields, "
            "or enter parameters manually above and click **Calculate Carbon Credits**."
        )
