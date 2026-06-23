import os
os.environ["USE_FOLIUM"] = "1"

import datetime
import json
import math
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st
import folium
from folium.plugins import Draw
import plotly.graph_objects as go
from streamlit_folium import st_folium


def compute_area_ha(geojson_feature: dict) -> float:
    coords = geojson_feature["geometry"]["coordinates"][0]
    lat_c = sum(c[1] for c in coords) / len(coords)
    m_per_lat = 111_320.0
    m_per_lon = 111_320.0 * math.cos(math.radians(lat_c))
    area_m2 = 0.0
    n = len(coords)
    for i in range(n - 1):
        x1, y1 = coords[i][0] * m_per_lon,   coords[i][1] * m_per_lat
        x2, y2 = coords[i+1][0] * m_per_lon, coords[i+1][1] * m_per_lat
        area_m2 += x1 * y2 - x2 * y1
    return round(abs(area_m2) / 2 / 10_000, 4)


def parse_geojson_upload(content: str):
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"
    t = data.get("type")
    if t == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            return None, "FeatureCollection contains no features."
        feat = features[0]
    elif t == "Feature":
        feat = data
    elif t in ("Polygon", "MultiPolygon"):
        feat = {"type": "Feature", "properties": {}, "geometry": data}
    else:
        return None, f"Unsupported GeoJSON type: '{t}'"
    geom_type = feat.get("geometry", {}).get("type", "")
    if geom_type not in ("Polygon", "MultiPolygon"):
        return None, f"Geometry must be Polygon or MultiPolygon, got '{geom_type}'."
    return feat, None


def parse_kml_upload(content: str):
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return None, f"Invalid KML: {e}"
    kml_ns = "http://www.opengis.net/kml/2.2"
    tags = [f"{{{kml_ns}}}coordinates", "coordinates"]
    for tag in tags:
        for elem in root.iter(tag):
            text = (elem.text or "").strip()
            coords = []
            for point in text.split():
                parts = point.split(",")
                if len(parts) >= 2:
                    try:
                        coords.append([float(parts[0]), float(parts[1])])
                    except ValueError:
                        continue
            if len(coords) >= 3:
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                return {
                    "type": "Feature", "properties": {},
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                }, None
    return None, "No valid polygon coordinates found in KML."


def parse_coordinate_text(text: str):
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    coords, bad = [], []
    for line in lines:
        parts = line.replace(",", " ").replace("\t", " ").split()
        if len(parts) < 2:
            continue
        try:
            lat, lon = float(parts[0]), float(parts[1])
        except ValueError:
            bad.append(line)
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            bad.append(f"{line}  ← out of range")
            continue
        coords.append([lon, lat])
    if len(coords) < 3:
        detail = f" Unparseable lines: {bad}" if bad else ""
        return None, f"Need at least 3 valid points, got {len(coords)}.{detail}"
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return {
        "type": "Feature", "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [coords]},
    }, None


def render_preview_map(feature: dict, key: str, height: int = 400):
    coords = feature["geometry"]["coordinates"][0]
    lats = [c[1] for c in coords]
    lons = [c[0] for c in coords]
    m = folium.Map(location=[sum(lats)/len(lats), sum(lons)/len(lons)], zoom_start=14)
    folium.GeoJson(
        feature,
        style_function=lambda _: {"color": "#ffcc00", "weight": 2.5, "fillOpacity": 0.2},
    ).add_to(m)
    st_folium(m, height=height, use_container_width=True, key=key, returned_objects=[])

from src.database import get_db_connection, check_cache, save_cache
from src.data_engine import SpatialDataEngine
from src.threshold_gate import AdaptiveAWDGate
from src.carbon_calculator import CarbonAssetEngine
from src.report_generator import generate_pdf, generate_audit_json, generate_timeseries_csv

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="terra-audit Platform")

st.markdown("""
    <style>
    .block-container { padding-top: 1.2rem !important; }
    [data-testid="metric-container"] {
        background-color: #1e222b;
        border: 1px solid #3e4451;
        border-radius: 8px;
        padding: 12px 16px !important;
    }
    .stTabs [data-baseweb="tab"] { font-size: 0.83rem; font-weight: 600; }
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
# DEFAULT_FIELDS = {
#     "F-101": {
#         "name": "Mymensingh Reference Parcel Alpha",
#         "district": "Mymensingh",
#         "geojson": {
#             "type": "FeatureCollection",
#             "features": [{
#                 "type": "Feature",
#                 "properties": {"name": "Mymensingh Reference Parcel Alpha"},
#                 "geometry": {
#                     "type": "Polygon",
#                     "coordinates": [[[90.4100, 24.7500], [90.4150, 24.7500],
#                                      [90.4150, 24.7550], [90.4100, 24.7550],
#                                      [90.4100, 24.7500]]]
#                 }
#             }]
#         }
#     },
#     "F-102": {
#         "name": "Faridpur Custom Zone Beta",
#         "district": "Faridpur",
#         "geojson": {
#             "type": "FeatureCollection",
#             "features": [{
#                 "type": "Feature",
#                 "properties": {"name": "Faridpur Custom Zone Beta"},
#                 "geometry": {
#                     "type": "Polygon",
#                     "coordinates": [[[89.5785, 23.0912], [89.5825, 23.0912],
#                                      [89.5825, 23.0952], [89.5785, 23.0952],
#                                      [89.5785, 23.0912]]]
#                 }
#             }]
#         }
#     },
# }

# with get_db_connection() as conn:
#     existing_ids = {
#         r["field_id"]
#         for r in conn.execute("SELECT field_id FROM fields").fetchall()
#     }
#     seeded = False
#     for fid, meta in DEFAULT_FIELDS.items():
#         if fid not in existing_ids:
#             conn.execute(
#                 "INSERT OR IGNORE INTO fields "
#                 "(field_id, name, district, geojson_geometry) VALUES (?,?,?,?)",
#                 (fid, meta["name"], meta["district"], json.dumps(meta["geojson"])),
#             )
#             seeded = True
#     if seeded:
#         conn.commit()
#         st.rerun()

# ---------------------------------------------------------------------------
# Load field list
# ---------------------------------------------------------------------------
with get_db_connection() as conn:
    fields = conn.execute(
        "SELECT field_id, name, district FROM fields ORDER BY field_id"
    ).fetchall()

field_display = {f["field_id"]: f for f in fields}

# ---------------------------------------------------------------------------
# Sidebar — Field Selector or Registration Form
# ---------------------------------------------------------------------------
with st.sidebar:
    pending_sidebar = st.session_state.get("pending_field_geom")

    if pending_sidebar:
        st.markdown("## ✏️ Register New Field")
        st.markdown("---")

        computed_ha = compute_area_ha(pending_sidebar)
        st.metric("Computed Area", f"{computed_ha} ha")
        st.markdown("")

        with get_db_connection() as conn:
            existing_ids = [
                r["field_id"]
                for r in conn.execute("SELECT field_id FROM fields").fetchall()
            ]
        nums = []
        for fid in existing_ids:
            parts = fid.split("-")
            if len(parts) == 2:
                try:
                    nums.append(int(parts[1]))
                except ValueError:
                    pass
        next_num = max(nums) + 1 if nums else 101

        new_fid      = st.text_input("Field ID",   value=f"F-{next_num}", key="nf_id")
        new_fname    = st.text_input("Field Name",                          key="nf_name")
        new_district = st.text_input("District",                            key="nf_district")
        st.markdown("")

        if st.button("💾 Save Field", type="primary", use_container_width=True):
            if not new_fname.strip() or not new_district.strip():
                st.error("Name and district are required.")
            elif new_fid in existing_ids:
                st.error(f"ID '{new_fid}' already exists.")
            else:
                fc = {"type": "FeatureCollection", "features": [pending_sidebar]}
                with get_db_connection() as conn:
                    conn.execute(
                        "INSERT INTO fields "
                        "(field_id, name, district, geojson_geometry, area_ha) "
                        "VALUES (?,?,?,?,?)",
                        (new_fid, new_fname.strip(), new_district.strip(),
                         json.dumps(fc), computed_ha),
                    )
                    conn.commit()
                st.session_state["map_version"] = st.session_state.get("map_version", 0) + 1
                st.session_state.pop("pending_field_geom", None)
                st.rerun()

        if st.button("🗑️ Discard", use_container_width=True):
            st.session_state["map_version"] = st.session_state.get("map_version", 0) + 1
            st.session_state.pop("pending_field_geom", None)
            st.rerun()

        selected_id = fields[0]["field_id"] if fields else None

    elif not fields:
        st.markdown("## 🛰️ Active Field Tracker")
        st.markdown("---")
        st.info(
            "No fields registered yet.\n\n"
            "Draw a polygon on the map in the **Spatial Asset Inspection** tab to add your first field."
        )
        selected_id = None

    else:
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

    if not pending_sidebar and selected_id:
        _s2 = st.session_state.get("signal_field_id") == selected_id
        _s3 = (st.session_state.get("export_cr") is not None) and _s2
        st.markdown("---")
        st.markdown(
            f"{'✅' if True else '⬜'}&nbsp; Field registered  \n"
            f"{'✅' if _s2 else '⬜'}&nbsp; Analytics complete  \n"
            f"{'✅' if _s3 else '⬜'}&nbsp; Credits calculated",
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Load geometry for selected field
# ---------------------------------------------------------------------------

if selected_id:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT geojson_geometry, area_ha FROM fields WHERE field_id = ?", (selected_id,)
        ).fetchone()
    geom       = json.loads(row["geojson_geometry"])
    field_area = float(row["area_ha"]) if row["area_ha"] else 1.0
else:
    geom       = None
    field_area = 1.0

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
    mode = st.radio(
        "boundary_input_mode",
        ["🖊️ Draw on Map", "📁 Upload GeoJSON / KML", "📍 Paste GPS Coordinates"],
        horizontal=True,
        label_visibility="collapsed",
        key="input_mode",
    )
    st.markdown("---")

    # ---- DRAW MODE --------------------------------------------------------
    if mode == "🖊️ Draw on Map":
        if geom:
            if "features" in geom:
                coords = geom["features"][0]["geometry"]["coordinates"][0]
            elif "geometry" in geom:
                coords = geom["geometry"]["coordinates"][0]
            else:
                coords = geom["coordinates"][0]
            lats = [c[1] for c in coords]
            lons = [c[0] for c in coords]
            center_lat, center_lon, zoom = sum(lats)/len(lats), sum(lons)/len(lons), 14
        else:
            center_lat, center_lon, zoom = 23.8, 90.4, 7

        m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom)
        if geom:
            folium.GeoJson(
                geom,
                style_function=lambda _: {"color": "#00ffcc", "weight": 2, "fillOpacity": 0.15},
            ).add_to(m)
        Draw(
            export=False,
            draw_options={
                "polygon": {"allowIntersection": False},
                "rectangle": True,
                "circle": False,
                "marker": False,
                "polyline": False,
                "circlemarker": False,
            },
        ).add_to(m)

        map_version = st.session_state.get("map_version", 0)
        map_out = st_folium(
            m, height=500, use_container_width=True,
            key=f"main_map_{map_version}",
            returned_objects=["all_drawings"],
        )

        if map_out:
            all_drawings = map_out.get("all_drawings") or []
            if all_drawings:
                latest = all_drawings[-1]
                if (latest and latest.get("geometry")
                        and latest != st.session_state.get("pending_field_geom")):
                    st.session_state["pending_field_geom"] = latest
                    st.rerun()

        if not st.session_state.get("pending_field_geom"):
            st.caption(
                "💡 Use the draw toolbar (top-left) to trace a polygon or rectangle — "
                "the registration form will appear in the sidebar."
            )

    # ---- UPLOAD MODE ------------------------------------------------------
    elif mode == "📁 Upload GeoJSON / KML":
        col_in, col_prev = st.columns([1, 1.5])

        with col_in:
            st.markdown("##### Upload Field Boundary File")
            st.caption("Accepted: `.geojson` `.json` `.kml`")
            uploaded = st.file_uploader(
                "file", type=["geojson", "json", "kml"], label_visibility="collapsed"
            )
            if uploaded:
                content = uploaded.read().decode("utf-8")
                if uploaded.name.lower().endswith(".kml"):
                    feat, err = parse_kml_upload(content)
                else:
                    feat, err = parse_geojson_upload(content)

                if err:
                    st.error(err)
                elif feat and feat != st.session_state.get("pending_field_geom"):
                    st.session_state["pending_field_geom"] = feat
                    st.rerun()

        with col_prev:
            pending = st.session_state.get("pending_field_geom")
            if pending:
                st.markdown("##### Boundary Preview")
                render_preview_map(pending, key="upload_preview_map")
            else:
                st.info("Upload a file to preview the boundary here.")

    # ---- PASTE MODE -------------------------------------------------------
    elif mode == "📍 Paste GPS Coordinates":
        col_in, col_prev = st.columns([1, 1.5])

        with col_in:
            st.markdown("##### Paste Boundary Coordinates")
            st.caption(
                "One point per line — `lat, lon` in decimal degrees. "
                "Minimum 3 points. First and last point do not need to match."
            )
            st.code("23.8541, 90.4120\n23.8541, 90.4180\n23.8580, 90.4180\n23.8580, 90.4120", language=None)
            coord_text = st.text_area(
                "coords", height=160,
                placeholder="23.8541, 90.4120\n23.8545, 90.4180\n...",
                label_visibility="collapsed",
            )
            if st.button("Parse Coordinates", type="primary", use_container_width=True):
                if coord_text.strip():
                    feat, err = parse_coordinate_text(coord_text)
                    if err:
                        st.error(err)
                    else:
                        st.session_state["pending_field_geom"] = feat
                        st.rerun()
                else:
                    st.warning("Paste some coordinates first.")

        with col_prev:
            pending = st.session_state.get("pending_field_geom")
            if pending:
                st.markdown("##### Boundary Preview")
                render_preview_map(pending, key="paste_preview_map")
            else:
                st.info("Parse coordinates to preview the boundary here.")

# ===========================================================================
# TAB 2 — SIGNAL ANALYTICS
# ===========================================================================
with tab_signal:
    if not selected_id:
        st.info("Draw and save a field in the **Spatial Asset Inspection** tab first.")
        st.stop()
    col_inputs, col_pipeline = st.columns([1, 2])

    # ---- Inputs panel -------------------------------------------------------
    with col_inputs:
        st.markdown("### Execution Scope")

        SEASON_PRESETS = {
            "🌾 Boro 2026  (Jan – May)":          ("2026-01-01", "2026-05-31"),
            "🌿 Aman 2025  (Jul – Nov)":           ("2025-07-01", "2025-11-30"),
            "☀️ Pre-Kharif 2025  (Mar – Jun)":    ("2025-03-01", "2025-06-30"),
            "🌾 Boro 2025  (Jan – May)":           ("2025-01-01", "2025-05-31"),
            "🗓️ Custom Range":                    None,
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
            value=field_area,
            step=0.1,
            help="Auto-computed from your drawn polygon. Override if needed.",
        )
        force_refresh = st.checkbox("Bypass Local Database Cache")
        date_valid    = (start_date < end_date) if preset_dates is None else True
        trigger       = st.button(
            "Run Analytics Engine", type="primary", disabled=not date_valid
        )

    # ---- Data fetch (runs only on button click) --------------------------------
    if trigger:
        sd_str       = str(start_date)
        ed_str       = str(end_date)
        df_processed = pd.DataFrame()
        cache_source = "Local relational data store"

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
            df_final             = gate.analyze_irrigation_behavior(df_processed)
            df_final             = gate.extract_phenology(df_final)
            total_awd            = int(df_final["drydown_event"].sum())
            sowing_row           = df_final[df_final["is_sowing"]  == 1]
            harvest_row          = df_final[df_final["is_harvest"] == 1]
            sowing_date_str      = sowing_row["date"].iloc[0]  if not sowing_row.empty  else "N/A"
            harvest_date_str     = harvest_row["date"].iloc[0] if not harvest_row.empty else "N/A"
            season_length_val    = 120
            season_from_phenology = False

            if not sowing_row.empty and not harvest_row.empty:
                season_length_val     = (
                    pd.to_datetime(harvest_date_str) - pd.to_datetime(sowing_date_str)
                ).days
                season_from_phenology = True

            # Persist signal results so the chart/table survive tab switches
            st.session_state["signal_df"]             = df_final
            st.session_state["signal_field_id"]       = selected_id
            st.session_state["signal_cache_source"]   = cache_source
            st.session_state["signal_total_awd"]      = total_awd
            st.session_state["signal_sowing_date"]    = sowing_date_str
            st.session_state["signal_harvest_date"]   = harvest_date_str
            st.session_state["signal_season_length"]  = season_length_val
            st.session_state["signal_from_phenology"] = season_from_phenology

            st.session_state["carbon_ready"]          = True
            st.session_state["carbon_total_awd"]      = total_awd
            st.session_state["carbon_season_length"]  = season_length_val
            st.session_state["carbon_area_ha"]        = field_area_ha
            st.session_state["season_from_phenology"] = season_from_phenology

            _export_cols = [c for c in [
                "date", "vv", "vh", "cross_ratio", "rvi",
                "vv_smoothed", "vh_smoothed", "vv_zscore",
                "is_flooded", "drydown_event", "is_sowing", "is_harvest",
            ] if c in df_final.columns]
            st.session_state["export_df"]             = df_final[_export_cols].copy()
            st.session_state["export_sowing"]         = sowing_date_str
            st.session_state["export_harvest"]        = harvest_date_str
            st.session_state["export_window_start"]   = sd_str
            st.session_state["export_window_end"]     = ed_str
            st.session_state["export_season_label"]   = season_choice
            st.session_state["export_field_id"]       = selected_id
            st.session_state["export_field_name"]     = field_display[selected_id]["name"]
            st.session_state["export_district"]       = field_display[selected_id]["district"]
            st.session_state["export_area_ha"]        = field_area_ha
            st.session_state["export_n_obs"]          = len(df_final)
            st.session_state["export_vv_mean"]        = float(df_final["vv_smoothed"].mean())
            st.session_state["export_vv_std"]         = float(df_final["vv_smoothed"].std())
            st.session_state["export_awd_dates"]      = (
                df_final[df_final["drydown_event"] == 1]["date"].tolist()
            )
            st.session_state["export_from_phenology"] = season_from_phenology

        else:
            st.session_state.pop("signal_df", None)
            st.session_state.pop("signal_field_id", None)
            with col_pipeline:
                st.error("No valid Sentinel-1 observations found for this field and window.")

    # ---- Result rendering — reads from session state, persists across tab switches ----
    _sig_df    = st.session_state.get("signal_df")
    _sig_field = st.session_state.get("signal_field_id")

    if _sig_df is not None and _sig_field == selected_id:
        _cache_src       = st.session_state["signal_cache_source"]
        _total_awd       = st.session_state["signal_total_awd"]
        _sowing_str      = st.session_state["signal_sowing_date"]
        _harvest_str     = st.session_state["signal_harvest_date"]
        _season_len      = st.session_state["signal_season_length"]
        _from_phenology  = st.session_state["signal_from_phenology"]
        _season_len_str  = f"{_season_len} days" if _from_phenology else "120 days (fallback)"

        with col_pipeline:
            st.caption(f"Data source: `{_cache_src}`")
            if not _from_phenology:
                st.warning(
                    "⚠️ Phenology markers not detected — season length uses the 120-day fallback. "
                    "Verify manually before carbon submission."
                )
            _c1, _c2, _c3, _c4 = st.columns(4)
            _c1.metric("AWD Events",    _total_awd)
            _c2.metric("Sowing Date",   _sowing_str)
            _c3.metric("Harvest Date",  _harvest_str)
            _c4.metric("Season Length", _season_len_str)

        # Chart — full width
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=_sig_df["date"], y=_sig_df["vv"],
            mode="markers", name="Raw VV",
            marker=dict(color="rgba(255,255,255,0.25)", size=5),
        ))
        fig.add_trace(go.Scatter(
            x=_sig_df["date"], y=_sig_df["vv_smoothed"],
            mode="lines+markers", name="VV Smoothed (flooding proxy)",
            line=dict(color="#00ffcc", width=2.5),
        ))
        if "vh_smoothed" in _sig_df.columns:
            fig.add_trace(go.Scatter(
                x=_sig_df["date"], y=_sig_df["vh_smoothed"],
                mode="lines", name="VH Smoothed (phenology proxy)",
                line=dict(color="#ff66cc", width=2, dash="dash"),
            ))

        _sowing_rows  = _sig_df[_sig_df["is_sowing"]  == 1]
        _harvest_rows = _sig_df[_sig_df["is_harvest"] == 1]
        if not _sowing_rows.empty and "vh_smoothed" in _sig_df.columns:
            fig.add_trace(go.Scatter(
                x=_sowing_rows["date"], y=_sowing_rows["vh_smoothed"],
                mode="markers", name="Sowing",
                marker=dict(color="#00ff00", size=14, symbol="triangle-up",
                            line=dict(width=2, color="white")),
            ))
        if not _harvest_rows.empty and "vh_smoothed" in _sig_df.columns:
            fig.add_trace(go.Scatter(
                x=_harvest_rows["date"], y=_harvest_rows["vh_smoothed"],
                mode="markers", name="Harvest",
                marker=dict(color="#ff4444", size=14, symbol="triangle-down",
                            line=dict(width=2, color="white")),
            ))

        # Vertical dashed lines for each AWD event — easier to read than point markers
        _events = _sig_df[_sig_df["drydown_event"] == 1]
        for _i, (_, _ev) in enumerate(_events.iterrows(), 1):
            fig.add_vline(
                x=_ev["date"],
                line_dash="dash",
                line_color="#ffcc00",
                line_width=1.5,
                annotation_text=f"AWD {_i}",
                annotation_position="top left",
                annotation_font_color="#ffcc00",
                annotation_font_size=10,
            )

        fig.update_layout(
            template="plotly_dark",
            height=450,
            xaxis_title="Sentinel-1 Overpass Date",
            yaxis_title="Backscatter (dB)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(t=60),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Audit trail table
        _audit_cols = ["date", "vv_smoothed", "vv_zscore",
                       "is_flooded", "drydown_event", "is_sowing", "is_harvest"]
        if "vh_smoothed" in _sig_df.columns:
            _audit_cols.insert(2, "vh_smoothed")
        st.markdown("#### Compliance Audit Trail Ledger")
        st.caption(f"{len(_sig_df)} observations · scroll to see all rows")
        st.dataframe(
            _sig_df[_audit_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "date":          st.column_config.TextColumn("Date"),
                "vv_smoothed":   st.column_config.NumberColumn("VV (dB)",  format="%.4f"),
                "vh_smoothed":   st.column_config.NumberColumn("VH (dB)",  format="%.4f"),
                "vv_zscore":     st.column_config.NumberColumn("Z-Score",  format="%.3f"),
                "is_flooded":    st.column_config.CheckboxColumn("Flooded"),
                "drydown_event": st.column_config.CheckboxColumn("AWD Event"),
                "is_sowing":     st.column_config.CheckboxColumn("Sowing"),
                "is_harvest":    st.column_config.CheckboxColumn("Harvest"),
            },
        )

    elif not trigger:
        with col_pipeline:
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.info(
                "Select a season and click **Run Analytics Engine** to fetch "
                "Sentinel-1 SAR data and detect AWD events for the selected field."
            )

# ===========================================================================
# TAB 3 — CARBON ASSET LEDGER
# ===========================================================================
with tab_carbon:
    if not selected_id:
        st.info("Draw and save a field in the **Spatial Asset Inspection** tab first.")
        st.stop()
    st.markdown("#### 💰 Carbon Compliance Ledger — VM0051 Tier 2")
    st.caption(
        "Parameters auto-fill from Signal Analytics. Override as needed, "
        "then click **Calculate Carbon Credits**."
    )
    st.markdown("---")

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
        st.session_state["export_cr"]           = cr
        st.session_state["export_confidence"]   = carbon_accuracy
        st.session_state["export_carbon_area"]  = carbon_area
        st.session_state["export_carbon_season"]= carbon_season
        st.session_state["export_carbon_awd"]   = carbon_awd

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
        st.markdown(
            f"Penalty: **{int(cr['p_uncertainty'] * 100)}%**"
            f"  →  retention multiplier = **{1 - cr['p_uncertainty']:.2f}**"
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

        # ---- Export Evidence Package ----------------------------------------
        if st.session_state.get("export_df") is not None:
            st.markdown("---")
            st.markdown("#### 📦 Export Evidence Package")
            st.caption(
                "All three files together form a complete, auditor-ready evidence package."
            )

            _fi = {
                "field_id": selected_id,
                "name":     field_display[selected_id]["name"],
                "district": field_display[selected_id]["district"],
                "area_ha":  carbon_area,
            }
            _win = {
                "season_label": st.session_state.get("export_season_label", "Custom"),
                "start":        st.session_state.get("export_window_start", "N/A"),
                "end":          st.session_state.get("export_window_end",   "N/A"),
            }
            _sig = {
                "n_observations":     st.session_state.get("export_n_obs", 0),
                "vv_mean":            st.session_state.get("export_vv_mean", 0.0),
                "vv_std":             st.session_state.get("export_vv_std",  0.0),
                "awd_events":         carbon_awd,
                "awd_dates":          st.session_state.get("export_awd_dates", []),
                "sowing_date":        st.session_state.get("export_sowing",  "N/A"),
                "harvest_date":       st.session_state.get("export_harvest", "N/A"),
                "season_length_days": carbon_season,
                "from_phenology":     st.session_state.get("export_from_phenology", False),
            }
            _car = {
                "sf_w_project":   cr["sf_w_project"],
                "p_uncertainty":  cr["p_uncertainty"],
                "e_baseline":     cr["e_baseline"],
                "e_project":      cr["e_project"],
                "delta_e_ch4":    cr["delta_e_ch4"],
                "delta_e_co2e":   cr["delta_e_co2e"],
                "final_issuance": cr["final_issuance"],
                "confidence_pct": carbon_accuracy,
            }
            _df_exp    = st.session_state["export_df"]
            _fid_slug  = selected_id.replace("-", "").lower()
            _win_slug  = _win["start"][:7] if _win["start"] != "N/A" else "custom"

            col_pdf, col_json, col_csv = st.columns(3)

            with col_pdf:
                try:
                    pdf_bytes = generate_pdf(_fi, _win, _sig, _car)
                    st.download_button(
                        "⬇️ Audit Report (PDF)",
                        data=pdf_bytes,
                        file_name=f"terra_audit_{_fid_slug}_{_win_slug}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        type="primary",
                    )
                except Exception as _err:
                    st.error(f"PDF error: {_err}")

            with col_json:
                st.download_button(
                    "⬇️ Audit Package (JSON)",
                    data=generate_audit_json(_fi, _win, _sig, _car, _df_exp),
                    file_name=f"audit_{_fid_slug}_{_win_slug}.json",
                    mime="application/json",
                    use_container_width=True,
                )

            with col_csv:
                st.download_button(
                    "⬇️ Timeseries (CSV)",
                    data=generate_timeseries_csv(_df_exp),
                    file_name=f"timeseries_{_fid_slug}_{_win_slug}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        else:
            st.markdown("---")
            st.info(
                "💡 Run the **Signal Analytics** engine first to unlock the full "
                "evidence export (PDF + JSON + CSV)."
            )

    else:
        st.info(
            "ℹ️ Run the **Analytics Engine** (Signal tab) to auto-populate fields, "
            "or enter parameters manually above and click **Calculate Carbon Credits**."
        )
