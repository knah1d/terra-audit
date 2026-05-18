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

existing_ids = [f['field_id'] for f in fields]

with get_db_connection() as conn:
    if "F-101" not in existing_ids:
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

tab_map, tab_signal = st.tabs(["🌍 Spatial Asset Inspection", "📈 Statistical Signal Analytics"])

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
                df_final = gate.extract_phenology(df_final)
                
                total_awd = int(df_final['drydown_event'].sum())
                
                sowing_row = df_final[df_final['is_sowing'] == 1]
                harvest_row = df_final[df_final['is_harvest'] == 1]
                
                sowing_date_str = sowing_row['date'].iloc[0] if not sowing_row.empty else "N/A"
                harvest_date_str = harvest_row['date'].iloc[0] if not harvest_row.empty else "N/A"
                
                season_length = "N/A"
                if not sowing_row.empty and not harvest_row.empty:
                    s_date = pd.to_datetime(sowing_date_str)
                    h_date = pd.to_datetime(harvest_date_str)
                    season_length = f"{(h_date - s_date).days} Days"
                
                with col_pipeline:
                    st.markdown(f"**Data Source Asset Provenance:** `{cache_source}`")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric(label="AWD Sequences", value=total_awd)
                    col2.metric(label="Sowing Date", value=sowing_date_str)
                    col3.metric(label="Harvest Date", value=harvest_date_str)
                    col4.metric(label="Season Length", value=season_length)
                
                # 2. Advanced Multi-Axis Data Plotting
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
                
                if not sowing_row.empty:
                    fig.add_trace(go.Scatter(
                        x=sowing_row['date'], y=sowing_row['vh_smoothed'],
                        mode='markers', name='Sowing Date',
                        marker=dict(color='#00ff00', size=16, symbol='triangle-up', line=dict(width=2, color='white'))
                    ))
                    
                if not harvest_row.empty:
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
                
                # 3. Open Audit Trail Preview Output Block
                st.markdown("### Compliance Audit Trail Ledger Payload")
                st.json(df_final[['date', 'vv_smoothed', 'vh_smoothed', 'is_flooded', 'drydown_event', 'is_sowing', 'is_harvest']].to_dict(orient="records")[:5])
            else:
                st.error("No valid radar tracking observations found within parameters.")
