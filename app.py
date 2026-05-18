import os
os.environ["USE_FOLIUM"] = "1"
import streamlit as st
import geemap.foliumap as geemap
import plotly.graph_objects as go
import json
import pandas as pd
from src.database import get_db_connection, check_cache, save_cache
from src.data_engine import SpatialDataEngine
from src.threshold_gate import AdaptiveAWDGate
from src.carbon_calculator import CarbonAssetEngine

st.set_page_config(layout="wide", page_title="terra-audit Platform")

# Custom dark-theme auditing stylesheet injection
st.markdown("""
    <style>
    .metric-container { background-color: #1e222b; padding: 15px; border-radius: 8px; border: 1px solid #3e4451; }
    </style>
""", unsafe_allow_html=True)

st.title("🛰️ terra-audit // High-Fidelity Processing Pipeline")
st.caption("Verra VM0051 Digital Compliance Sandbox // Phase 2 Engine Core")

@st.cache_resource
def init_modules():
    try:
        return SpatialDataEngine(), AdaptiveAWDGate(), CarbonAssetEngine(), None
    except Exception as e:
        return None, None, None, str(e)

engine, gate, carbon_engine, init_error = init_modules()

if init_error:
    st.error(f"Failed to start: {init_error}")
    st.info("💡 **How to fix this:** You need to link your Google Earth Engine account to a Cloud Project.")
    st.code("earthengine set_project YOUR_PROJECT_ID", language="bash")
    st.markdown("If you don't know your Project ID, go to [Google Cloud Console](https://console.cloud.google.com/) and create one, then use its ID in the command above.")
    st.stop()

with get_db_connection() as conn:
    fields = conn.execute("SELECT field_id, name FROM fields").fetchall()

existing_ids = [f['field_id'] for f in fields]

with get_db_connection() as conn:
    if "F-101" not in existing_ids:
        mock_polygon = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"name": "Mymensingh Reference Parcel Alpha"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[90.4100, 24.7500], [90.4150, 24.7500], [90.4150, 24.7550], [90.4100, 24.7550], [90.4100, 24.7500]]]
                }
            }]
        }
        conn.execute("INSERT OR REPLACE INTO fields (field_id, name, district, geojson_geometry) VALUES (?, ?, ?, ?)",
                     ("F-101", "Mymensingh Reference Parcel Alpha", "Mymensingh", json.dumps(mock_polygon)))
        conn.commit()

    if "F-102" not in existing_ids:
        mock_polygon_custom = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"name": "Faridpur Custom Zone Beta"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[89.5785, 23.0912], [89.5825, 23.0912], [89.5825, 23.0952], [89.5785, 23.0952], [89.5785, 23.0912]]]
                }
            }]
        }
        conn.execute("INSERT OR REPLACE INTO fields (field_id, name, district, geojson_geometry) VALUES (?, ?, ?, ?)",
                     ("F-102", "Faridpur Custom Zone Beta", "Faridpur", json.dumps(mock_polygon_custom)))
        conn.commit()

    if "F-101" not in existing_ids or "F-102" not in existing_ids:
        st.rerun()

selected_field = st.sidebar.selectbox("Active Field Tracker", [f"{f['field_id']} - {f['name']}" for f in fields])
current_id = selected_field.split(" - ")[0]

with get_db_connection() as conn:
    field_row = conn.execute("SELECT * FROM fields WHERE field_id = ?", (current_id,)).fetchone()

geom = json.loads(field_row['geojson_geometry'])

tab_map, tab_signal, tab_carbon = st.tabs(["🌍 Spatial Asset Inspection", "📈 Statistical Signal Analytics", "💰 Carbon Asset Ledger"])

# --- TAB 1: MAP ---
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
    m.to_streamlit(height=400)

# --- TAB 2: SIGNAL ANALYTICS ---
with tab_signal:
    col_inputs, col_pipeline = st.columns([1, 2])

    with col_inputs:
        st.markdown("### Execution Scope")
        start_date = st.date_input("Analysis Window Open", value=pd.to_datetime("2025-01-01"))
        end_date = st.date_input("Analysis Window Close", value=pd.to_datetime("2025-05-01"))
        force_refresh = st.checkbox("Bypass Local Database Cache")
        trigger = st.button("Run Analytics Engine", type="primary")

    if trigger:
        df_processed = pd.DataFrame()
        cache_source = "Local relational data store"

        with st.spinner("Resolving spatial asset data timeline..."):
            # 1. Read-Through Caching Architecture
            if not force_refresh:
                df_processed = check_cache(current_id)

            if df_processed.empty:
                cache_source = "Live Google Earth Engine Core API"
                df_raw = engine.extract_clean_timeseries(geom, str(start_date), str(end_date))
                if not df_raw.empty:
                    save_cache(current_id, df_raw)
                    df_processed = check_cache(current_id)

            if not df_processed.empty:
                # Run the adaptive statistical rule processor
                df_final = gate.analyze_irrigation_behavior(df_processed)
                df_final = gate.extract_phenology(df_final)

                total_awd = int(df_final['drydown_event'].sum())

                sowing_row = df_final[df_final['is_sowing'] == 1]
                harvest_row = df_final[df_final['is_harvest'] == 1]

                sowing_date_str = sowing_row['date'].iloc[0] if not sowing_row.empty else "N/A"
                harvest_date_str = harvest_row['date'].iloc[0] if not harvest_row.empty else "N/A"

                season_length_val = 120  # Fallback default
                season_length = "N/A"
                if not sowing_row.empty and not harvest_row.empty:
                    s_date = pd.to_datetime(sowing_date_str)
                    h_date = pd.to_datetime(harvest_date_str)
                    season_length_val = (h_date - s_date).days
                    season_length = f"{season_length_val} Days"

                with col_pipeline:
                    st.markdown(f"**Data Source Asset Provenance:** `{cache_source}`")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric(label="AWD Sequences", value=total_awd)
                    col2.metric(label="Sowing Date", value=sowing_date_str)
                    col3.metric(label="Harvest Date", value=harvest_date_str)
                    col4.metric(label="Season Length", value=season_length)

                # 2. Multi-Axis Data Plotting
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_final['date'], y=df_final['vv'],
                    mode='markers', name='Raw VV Backscatter',
                    marker=dict(color='rgba(255,255,255,0.3)', size=5)
                ))
                fig.add_trace(go.Scatter(
                    x=df_final['date'], y=df_final['vv_smoothed'],
                    mode='lines+markers', name='VV Filter Curve (Flooding)',
                    line=dict(color='#00ffcc', width=2.5)
                ))

                if 'vh_smoothed' in df_final.columns:
                    fig.add_trace(go.Scatter(
                        x=df_final['date'], y=df_final['vh_smoothed'],
                        mode='lines', name='VH Filter Curve (Phenology)',
                        line=dict(color='#ff66cc', width=2, dash='dash')
                    ))

                events = df_final[df_final['drydown_event'] == 1]
                fig.add_trace(go.Scatter(
                    x=events['date'], y=events['vv_smoothed'],
                    mode='markers', name='Drainage Marker',
                    marker=dict(color='#ffcc00', size=14, symbol='star')
                ))

                if not sowing_row.empty and 'vh_smoothed' in df_final.columns:
                    fig.add_trace(go.Scatter(
                        x=sowing_row['date'], y=sowing_row['vh_smoothed'],
                        mode='markers', name='Sowing Date',
                        marker=dict(color='#00ff00', size=16, symbol='triangle-up', line=dict(width=2, color='white'))
                    ))

                if not harvest_row.empty and 'vh_smoothed' in df_final.columns:
                    fig.add_trace(go.Scatter(
                        x=harvest_row['date'], y=harvest_row['vh_smoothed'],
                        mode='markers', name='Harvest Date',
                        marker=dict(color='#ff0000', size=16, symbol='triangle-down', line=dict(width=2, color='white'))
                    ))

                fig.update_layout(
                    template="plotly_dark", height=450,
                    xaxis_title="Timeline Calendar Passes", yaxis_title="Energy Signature (dB)"
                )
                st.plotly_chart(fig, use_container_width=True)

                # 3. Audit Trail — safe column selection only what exists
                audit_cols = ['date', 'vv_smoothed', 'is_flooded', 'drydown_event', 'is_sowing', 'is_harvest']
                if 'vh_smoothed' in df_final.columns:
                    audit_cols.insert(2, 'vh_smoothed')
                st.markdown("### Compliance Audit Trail Ledger Payload")
                st.json(df_final[audit_cols].to_dict(orient="records")[:5])

                # 4. Stash computed values in session state for Carbon tab
                st.session_state['carbon_ready'] = True
                st.session_state['carbon_total_awd'] = total_awd
                st.session_state['carbon_season_length_val'] = season_length_val

            else:
                st.error("No valid radar tracking observations found within parameters.")

# --- TAB 3: CARBON ASSET LEDGER ---
with tab_carbon:
    st.markdown("### 💰 Carbon Compliance Ledger (VM0051)")
    st.write("Configure parameters below, then click **Calculate Credits** to execute the full Verra VM0051 / IPCC Tier 2 methodology chain.")

    # --- Manual Overrides always visible ---
    st.markdown("---")
    st.markdown("#### ⚙️ Calculation Parameters")
    st.caption("Auto-filled from signal engine after running analytics. You can also set them manually.")

    # Pull auto-detected values from session state if available
    default_season = int(st.session_state.get('carbon_season_length_val', 120))
    default_awd = int(st.session_state.get('carbon_total_awd', 3))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        carbon_season = st.number_input("Season Length (days)", min_value=1, max_value=365, value=default_season, step=1)
    with c2:
        carbon_area = st.number_input("Field Area (ha)", min_value=0.1, max_value=500.0, value=1.0, step=0.1)
    with c3:
        carbon_awd = st.number_input("AWD Events (verified)", min_value=0, max_value=20, value=default_awd, step=1)
    with c4:
        carbon_accuracy = st.slider("Model Confidence (%)", min_value=70.0, max_value=100.0, value=92.0, step=0.5)

    run_carbon = st.button("⚡ Calculate Carbon Credits", type="primary")

    if run_carbon or st.session_state.get('carbon_ready'):
        carbon_results = carbon_engine.calculate_credits(
            awd_events=carbon_awd,
            season_length_days=carbon_season,
            area_ha=carbon_area,
            ai_accuracy=carbon_accuracy
        )

        st.markdown("---")

        # Summary metrics row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Baseline Emissions", f"{carbon_results['e_baseline']:.2f} kg CH₄")
        m2.metric("Project Emissions", f"{carbon_results['e_project']:.2f} kg CH₄")
        m3.metric("Avoided (tCO₂e)", f"{carbon_results['delta_e_co2e']:.3f}")
        m4.metric("Final Credits Issued", f"{carbon_results['final_issuance']:.3f}")

        st.markdown("---")
        st.markdown("#### 📐 Step-by-Step Audit Trail")

        st.markdown("**Step 1: Baseline Scenario** — continuous flooding, $SF_w = 1.0$")
        st.latex(r"E_{\text{baseline}} = EF_c \times SF_{w,\text{baseline}} \times D \times A")
        st.latex(
            f"E_{{\\text{{baseline}}}} = 1.4 \\times 1.0 \\times {carbon_season} \\times {carbon_area} = {carbon_results['e_baseline']:.2f}\\text{{ kg CH}}_4"
        )

        st.markdown(f"**Step 2: Project Scenario** — {carbon_awd} AWD event(s) detected → $SF_{{w,\\text{{project}}}} = {carbon_results['sf_w_project']}$")
        st.latex(r"E_{\text{project}} = EF_c \times SF_{w,\text{project}} \times D \times A")
        st.latex(
            f"E_{{\\text{{project}}}} = 1.4 \\times {carbon_results['sf_w_project']} \\times {carbon_season} \\times {carbon_area} = {carbon_results['e_project']:.2f}\\text{{ kg CH}}_4"
        )

        st.markdown("**Step 3: Net Methane Avoided**")
        st.latex(r"\Delta E_{\text{CH}_4} = E_{\text{baseline}} - E_{\text{project}}")
        st.latex(
            f"\\Delta E_{{\\text{{CH}}_4}} = {carbon_results['e_baseline']:.2f} - {carbon_results['e_project']:.2f} = {carbon_results['delta_e_ch4']:.2f}\\text{{ kg CH}}_4"
        )

        st.markdown("**Step 4: Convert to tCO₂e** — using GWP₂₅ = 28")
        st.latex(r"\Delta E_{\text{CO}_2\text{e}} = \frac{\Delta E_{\text{CH}_4} \times GWP_{\text{CH}_4}}{1000}")
        st.latex(
            f"\\Delta E_{{\\text{{CO}}_2\\text{{e}}}} = \\frac{{{carbon_results['delta_e_ch4']:.2f} \\times 28}}{{1000}} = {carbon_results['delta_e_co2e']:.3f}\\text{{ tCO}}_2\\text{{e}}"
        )

        st.markdown(f"**Step 5: Conservativeness Penalty** — Model Confidence: {carbon_accuracy}%")
        st.info(f"Penalty applied: **{int(carbon_results['p_uncertainty'] * 100)}%** → multiplier = {1 - carbon_results['p_uncertainty']:.2f}")
        st.latex(r"\text{Final Credits} = \Delta E_{\text{CO}_2\text{e}} \times (1 - P_{\text{uncertainty}})")
        st.latex(
            f"\\text{{Final Issuance}} = {carbon_results['delta_e_co2e']:.3f} \\times (1 - {carbon_results['p_uncertainty']:.2f}) = \\mathbf{{{carbon_results['final_issuance']:.3f}\\text{{ tCO}}_2\\text{{e}}}}"
        )

        if carbon_results['p_uncertainty'] == 1.0:
            st.error("🚫 Audit Failure: Model confidence below 85%. Zero credits issued. Requires manual field verification.")
        else:
            st.success(f"🎉 **{carbon_results['final_issuance']:.3f}** Verified Carbon Credits ready for registry submission.")
    else:
        st.info("ℹ️ Run the **Analytics Engine** first to auto-populate AWD and season data, or set the parameters manually above and click **Calculate Carbon Credits**.")
