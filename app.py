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
    # Cache invalidation trigger
    try:
        return SpatialDataEngine(), AdaptiveAWDGate(), None
    except Exception as e:
        return None, None, str(e)

engine, gate, init_error = init_modules()

if init_error:
    st.error(f"Failed to start: {init_error}")
    st.info("💡 **How to fix this:** You need to link your Google Earth Engine account to a Cloud Project.")
    st.code("earthengine set_project YOUR_PROJECT_ID", language="bash")
    st.markdown("If you don't know your Project ID, go to [Google Cloud Console](https://console.cloud.google.com/) and create one, then use its ID in the command above.")
    st.stop()

with get_db_connection() as conn:
    fields = conn.execute("SELECT field_id, name FROM fields").fetchall()

if not fields:
    st.info("Initializing baseline system storage metadata...")
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
    with get_db_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO fields (field_id, name, district, geojson_geometry) VALUES (?, ?, ?, ?)",
                     ("F-101", "Mymensingh Reference Parcel Alpha", "Mymensingh", json.dumps(mock_polygon)))
        conn.commit()
    st.rerun()

selected_field = st.sidebar.selectbox("Active Field Tracker", [f"{f['field_id']} - {f['name']}" for f in fields])
current_id = selected_field.split(" - ")[0]

with get_db_connection() as conn:
    field_row = conn.execute("SELECT * FROM fields WHERE field_id = ?", (current_id,)).fetchone()

geom = json.loads(field_row['geojson_geometry'])

tab_map, tab_signal = st.tabs(["🌍 Spatial Asset Inspection", "📈 Statistical Signal Analytics"])

with tab_map:
    m = geemap.Map(center=[24.7525, 90.4125], zoom=14)
    m.add_geojson(geom, layer_name="Target Polygon Boundary")
    m.to_streamlit(height=400)

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
            # 1. Read-Through Caching Architecture Execution Check
            if not force_refresh:
                df_processed = check_cache(current_id)
                
            if df_processed.empty:
                cache_source = "Live Google Earth Engine Core API"
                # Cache miss -> Hit cloud servers
                df_raw = engine.extract_clean_timeseries(geom, str(start_date), str(end_date))
                if not df_raw.empty:
                    save_cache(current_id, df_raw)
                    df_processed = check_cache(current_id)
            
            if not df_processed.empty:
                # Run the adaptive statistical rule processor
                df_final = gate.analyze_irrigation_behavior(df_processed)
                total_awd = int(df_final['drydown_event'].sum())
                
                with col_pipeline:
                    st.markdown(f"**Data Source Asset Provenance:** `{cache_source}`")
                    st.metric(label="Verified Field Drainage (AWD) Sequences", value=total_awd)
                
                # 2. Advanced Multi-Axis Data Plotting
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_final['date'], y=df_final['vv'],
                    mode='markers', name='Raw Backscatter (Speckled)',
                    marker=dict(color='rgba(255,255,255,0.3)', size=5)
                ))
                fig.add_trace(go.Scatter(
                    x=df_final['date'], y=df_final['vv_smoothed'],
                    mode='lines+markers', name='Savitzky-Golay Filter Curve',
                    line=dict(color='#00ffcc', width=2.5)
                ))
                
                events = df_final[df_final['drydown_event'] == 1]
                fig.add_trace(go.Scatter(
                    x=events['date'], y=events['vv_smoothed'],
                    mode='markers', name='Statistical Drainage Marker',
                    marker=dict(color='#ffcc00', size=14, symbol='star')
                ))
                
                fig.update_layout(
                    template="plotly_dark", height=450,
                    xaxis_title="Timeline Calendar Passes", yaxis_title="VV Energy Signature (dB)"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # 3. Open Audit Trail Preview Output Block
                st.markdown("### Compliance Audit Trail Ledger Payload")
                st.json(df_final[['date', 'vv_smoothed', 'vv_zscore', 'is_flooded', 'drydown_event']].to_dict(orient="records")[:5])
            else:
                st.error("No valid radar tracking observations found within parameters.")
