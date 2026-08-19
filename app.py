import os
os.environ["USE_FOLIUM"] = "1"

import datetime
import json

import pandas as pd
import streamlit as st
import folium
from folium.plugins import Draw
import plotly.graph_objects as go
from streamlit_folium import st_folium

from src.geo_utils import (
    compute_area_ha,
    parse_geojson_upload,
    parse_kml_upload,
    parse_coordinate_text,
)
from src.ui_theme import inject_theme, get_theme_mode, render_theme_toggle



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

from src.database import (
    get_db_connection, check_cache, save_cache, delete_field, update_field_info,
    save_alm_practice_schedule, get_alm_practice_schedule,
    save_soc_measurements, get_soc_measurements, ALM_PRACTICE_COLUMNS,
    get_alm_cumulative_delta, update_alm_cumulative_delta,
    save_alm_livestock_schedule, get_alm_livestock_schedule,
    save_credit_history, get_credit_history, get_portfolio_summary,
)
from src.data_engine import SpatialDataEngine
from src.field_types import build_detector, build_methodology, field_uses_sar
from src.report_generator import (
    generate_pdf, generate_audit_json, generate_timeseries_csv,
    generate_pdf_alm, generate_audit_json_alm, generate_alm_data_csv,
)
from src.ai.predictor import predict_awd_states
from src.ai.dataset_builder import build_dataset, save_dataset, load_dataset
from src.ai.feature_engineering import build_features
from src.ai.models import train_and_evaluate, save_model
from src.ai import evaluate as ai_evaluate
from src.auth import login_form, logout, require_role, create_org_user, list_org_users, VALID_ROLES

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Terra Audit Platform")

_theme_mode = get_theme_mode()
inject_theme(_theme_mode)

# ---------------------------------------------------------------------------
# Auth gate — must come before init_modules()/any DB read below, so no
# GEE/DB work happens for an unauthenticated session (Phase 1 of the
# multi-tenant plan; see .claude/plans/misty-growing-yao.md).
# ---------------------------------------------------------------------------
auth_user = login_form()
if auth_user is None:
    st.stop()
org_id = auth_user["org_id"]

# Every session_state key that's derived from a specific field's data — used
# both when a field is deleted (its cached results must not survive) and on
# logout (Phase 3 of the multi-tenant plan): without clearing these, a
# different user logging into the same browser tab could see the previous
# session's stale per-field figures rendered as if freshly computed for
# their own field, since several of these (carbon_ready et al.) are read
# back with only a soft "if present" check, not a hard field-id match.
def _can_write() -> bool:
    """Viewer role is read-only (Phase 4 of the multi-tenant plan) — every
    mutating action (field registration/edit/delete, practice/SOC/livestock
    saves, Calculate Carbon Credits) must check this before writing.
    Delegates to src.auth.require_role rather than re-implementing the
    check, and turns its PermissionError into a UI error instead of an
    uncaught exception."""
    try:
        require_role(auth_user, {"admin", "analyst"})
        return True
    except PermissionError as exc:
        st.error(f"🔒 {exc}")
        return False


def _can_delete() -> bool:
    """Deleting a field is irreversible (cascades across every table for
    that field_id) — restricted to admin only, not analysts."""
    try:
        require_role(auth_user, {"admin"})
        return True
    except PermissionError as exc:
        st.error(f"🔒 {exc}")
        return False


SESSION_KEYS_TO_CLEAR_ON_FIELD_CHANGE = [
    "signal_df", "signal_field_id", "signal_cache_source",
    "signal_total_awd", "signal_sowing_date", "signal_harvest_date",
    "signal_season_length", "signal_from_phenology",
    "signal_detector_used", "signal_model_fallback_msg", "signal_last_run_at",
    "carbon_ready", "carbon_field_id", "carbon_total_awd",
    "carbon_season_length", "carbon_area_ha", "season_from_phenology",
    "export_df", "export_cr", "export_sowing", "export_harvest",
    "export_window_start", "export_window_end", "export_season_label",
    "export_field_id", "export_field_name", "export_district",
    "export_area_ha", "export_n_obs", "export_vv_mean", "export_vv_std",
    "export_awd_dates", "export_from_phenology", "export_carbon_area",
    "export_carbon_awd", "export_carbon_season", "export_q_n",
    "alm_data_field_id", "alm_practice_schedule", "alm_soc_measurements",
    "alm_area_ha", "alm_livestock_schedule", "alm_carbon_ready",
    "validation_results",
]

# ---------------------------------------------------------------------------
# Module initialisation (cached for the lifetime of the Streamlit process,
# shared across every org — safe because SpatialDataEngine holds no
# per-request state and every GEE call takes the field geometry as an
# explicit per-call argument, not something cached on the engine itself).
# Moved above the hero so the hero can show real engine status on first paint.
# ---------------------------------------------------------------------------
@st.cache_resource
def init_modules():
    try:
        return SpatialDataEngine(), None
    except Exception as exc:
        return None, str(exc)

engine, init_error = init_modules()

# ---------------------------------------------------------------------------
# Load field list
# Moved above the hero so the hero can show a real field count on first paint.
# ---------------------------------------------------------------------------
with get_db_connection() as conn:
    fields = conn.execute(
        "SELECT field_id, name, district, field_type FROM fields "
        "WHERE org_id = ? ORDER BY field_id",
        (org_id,),
    ).fetchall()

field_display = {f["field_id"]: f for f in fields}

# ---------------------------------------------------------------------------
# Hero — real KPIs only, no fabricated placeholders
# ---------------------------------------------------------------------------
_engine_ok = init_error is None
_badge_class = "ta-hero-badge" if _engine_ok else "ta-hero-badge warn"
_badge_text = "🛰️ Engine Connected" if _engine_ok else "⚠️ Engine Offline"

_last_run_at = st.session_state.get("signal_last_run_at")
if _last_run_at:
    _mins_ago = int((datetime.datetime.now() - _last_run_at).total_seconds() // 60)
    _last_run_label = "just now" if _mins_ago < 1 else f"{_mins_ago} min ago"
else:
    _last_run_label = "Not run yet"

_export_cr = st.session_state.get("export_cr")
_credits_label = f"{_export_cr['final_issuance']:.2f} tCO2e" if _export_cr else "—"

_col_hero, _col_theme_toggle = st.columns([12, 1], vertical_alignment="top")
with _col_hero:
    st.markdown(f"""
        <div class="ta-hero">
            <span class="{_badge_class}">{_badge_text}</span>
            <h1 class="ta-hero-title">Terra Audit</h1>
            <p class="ta-hero-subtitle">AWD irrigation detection via Sentinel-1 SAR and Verra VM0051 Tier 2 carbon verification for rice paddies in Bangladesh / South Asia</p>
            <div class="ta-hero-stats">
                <div class="ta-stat">
                    <div class="ta-stat-value">{len(fields)}</div>
                    <div class="ta-stat-label">Fields</div>
                </div>
                <div class="ta-stat">
                    <div class="ta-stat-value">{_last_run_label}</div>
                    <div class="ta-stat-label">Last Analysis</div>
                </div>
                <div class="ta-stat">
                    <div class="ta-stat-value accent">{_credits_label}</div>
                    <div class="ta-stat-label">Credits Issued</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with _col_theme_toggle:
    render_theme_toggle()

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
        "SELECT field_id, name, district, field_type FROM fields "
        "WHERE org_id = ? ORDER BY field_id",
        (org_id,),
    ).fetchall()

field_display = {f["field_id"]: f for f in fields}

# ---------------------------------------------------------------------------
# Sidebar — Field Selector or Registration Form
# ---------------------------------------------------------------------------
with st.sidebar:
    st.caption(f"Signed in as {auth_user['email']} ({auth_user['role']})")
    if st.button("Log out", use_container_width=True):
        logout()
        for _k in SESSION_KEYS_TO_CLEAR_ON_FIELD_CHANGE:
            st.session_state.pop(_k, None)
        st.rerun()
    st.markdown("---")

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
                for r in conn.execute(
                    "SELECT field_id FROM fields WHERE org_id = ?", (org_id,)
                ).fetchall()
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
        FIELD_TYPE_CHOICES = {
            "🌾 Rice — Alternate Wetting & Drying (VM0051)": "rice_awd",
            "🌱 Cropland — Improved Agricultural Land Management (VM0042)": "cropland_alm_vm0042",
        }
        new_ftype_label = st.selectbox(
            "Field Type / Methodology",
            options=list(FIELD_TYPE_CHOICES.keys()),
            key="nf_ftype",
            help="Determines which detector and carbon methodology this field "
                 "uses. VM0042 fields must be non-wetland cropland — not "
                 "applicable to flooded rice paddies.",
        )
        new_ftype = FIELD_TYPE_CHOICES[new_ftype_label]
        st.markdown("")

        if st.button("💾 Save Field", type="primary", use_container_width=True) and _can_write():
            if not new_fname.strip() or not new_district.strip():
                st.error("Name and district are required.")
            elif new_fid in existing_ids:
                st.error(f"ID '{new_fid}' already exists.")
            else:
                fc = {"type": "FeatureCollection", "features": [pending_sidebar]}
                with get_db_connection() as conn:
                    conn.execute(
                        "INSERT INTO fields "
                        "(org_id, field_id, name, district, geojson_geometry, area_ha, field_type) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (org_id, new_fid, new_fname.strip(), new_district.strip(),
                         json.dumps(fc), computed_ha, new_ftype),
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
        <div class="ta-card">
            <div class="ta-card-eyebrow">Selected Parcel</div>
            <div class="ta-card-title">{sf['field_id']}</div>
            <div class="ta-card-body">{sf['name']}</div>
            <div class="ta-card-meta">📍 {sf['district']} District</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("")

        # ---- Edit field (name/district only) -----------------------------
        _edit_key = f"editing_field_{selected_id}"
        if st.session_state.get(_edit_key):
            edit_name = st.text_input("Field Name", value=sf["name"], key=f"edit_name_{selected_id}")
            edit_district = st.text_input(
                "District", value=sf["district"], key=f"edit_district_{selected_id}"
            )
            st.caption(
                "Field type and boundary are not editable here — they determine "
                "which cached data belongs to this field. Remove and re-register "
                "to change either."
            )
            _col_save, _col_cancel = st.columns(2)
            if _col_save.button("💾 Save", type="primary", use_container_width=True, key=f"save_edit_{selected_id}") and _can_write():
                if not edit_name.strip() or not edit_district.strip():
                    st.error("Name and district are required.")
                else:
                    update_field_info(org_id, selected_id, edit_name.strip(), edit_district.strip())
                    st.session_state.pop(_edit_key, None)
                    st.rerun()
            if _col_cancel.button("Cancel", use_container_width=True, key=f"cancel_edit_{selected_id}"):
                st.session_state.pop(_edit_key, None)
                st.rerun()
        else:
            if st.button("✏️ Edit Name / District", use_container_width=True):
                st.session_state[_edit_key] = True
                st.rerun()

        # ---- Remove field -----------------------------------------------
        _confirm_key = f"confirm_delete_{selected_id}"
        if st.session_state.get(_confirm_key):
            st.warning(
                f"Delete **{sf['name']}** ({sf['field_id']})? "
                "This cannot be undone."
            )
            _col_yes, _col_no = st.columns(2)
            if _col_yes.button("Yes, delete", type="primary", use_container_width=True) and _can_delete():
                delete_field(org_id, selected_id)
                for _k in [*SESSION_KEYS_TO_CLEAR_ON_FIELD_CHANGE, _confirm_key]:
                    st.session_state.pop(_k, None)
                st.session_state["map_version"] = st.session_state.get("map_version", 0) + 1
                st.rerun()
            if _col_no.button("Cancel", use_container_width=True):
                st.session_state.pop(_confirm_key, None)
                st.rerun()
        else:
            if st.button(
                "🗑️ Remove this field",
                use_container_width=True,
                help="Permanently delete this field and all its data — cached "
                     "timeseries, and (for cropland fields) practice schedule, "
                     "livestock, and SOC measurements.",
            ):
                st.session_state[_confirm_key] = True
                st.rerun()

    if not pending_sidebar and selected_id:
        _sidebar_uses_sar = field_uses_sar(field_display[selected_id]["field_type"])
        if _sidebar_uses_sar:
            _s2 = st.session_state.get("signal_field_id") == selected_id
            _s2_label = "Analytics complete"
        else:
            _s2 = st.session_state.get("alm_data_field_id") == selected_id
            _s2_label = "Practice & soil data saved"
        _s3 = (st.session_state.get("export_cr") is not None) and _s2
        st.markdown("---")
        _steps = [
            (True, "Field registered"),
            (_s2, _s2_label),
            (_s3, "Credits calculated"),
        ]
        _items = "".join(
            f'<div class="ta-progress-item{" done" if done else ""}">'
            f'{"✅" if done else "⬜"}&nbsp; {label}</div>'
            for done, label in _steps
        )
        st.markdown(f'<div class="ta-progress-list">{_items}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load geometry for selected field
# ---------------------------------------------------------------------------

if selected_id:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT geojson_geometry, area_ha FROM fields WHERE org_id = ? AND field_id = ?",
            (org_id, selected_id),
        ).fetchone()
    geom       = json.loads(row["geojson_geometry"])
    field_area = float(row["area_ha"]) if row["area_ha"] else 1.0
else:
    geom       = None
    field_area = 1.0

# ---------------------------------------------------------------------------
# Resolve detector/methodology engine for the selected field's type.
# "rice_awd" (SAR-driven) and "cropland_alm_vm0042" (manual practice/soil
# data — no satellite signal) are registered in src/field_types/. uses_sar
# is what lets app.py branch the UI between the two without a big if/else
# sprawled through every section.
# ---------------------------------------------------------------------------
selected_field_type = field_display[selected_id]["field_type"] if selected_id else "rice_awd"
selected_uses_sar    = field_uses_sar(selected_field_type)
gate          = build_detector(selected_field_type)
carbon_engine = build_methodology(selected_field_type)

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------
tab_map, tab_2, tab_carbon, tab_validation, tab_portfolio = st.tabs([
    "🌍 Spatial Asset Inspection",
    "📈 Statistical Signal Analytics" if selected_uses_sar else "🧪 Practice & Soil Data",
    "💰 Carbon Asset Ledger",
    "🤖 AI Validation",
    "📊 Portfolio",
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
# TAB 2 — SIGNAL ANALYTICS (rice_awd) / PRACTICE & SOIL DATA (cropland_alm_vm0042)
# ===========================================================================
def render_signal_analytics_tab():
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

        DETECTOR_OPTIONS = {
            "Threshold Gate (rule-based)": "threshold",
            "Random Forest (AI baseline)": "random_forest",
            "XGBoost (AI baseline)": "xgboost",
        }
        detector_label = st.selectbox(
            "Detection Model",
            options=list(DETECTOR_OPTIONS.keys()),
            help="AI baselines are trained on the Threshold Gate's own output "
                 "(no independent ground truth exists yet) — treat them as "
                 "proof-of-concept, not a validated alternative.",
        )
        detector_key = DETECTOR_OPTIONS[detector_label]

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
                df_processed = check_cache(org_id, selected_id, sd_str, ed_str)
            if df_processed.empty:
                cache_source = "Live Google Earth Engine Core API"
                df_raw = engine.extract_clean_timeseries(geom, sd_str, ed_str)
                if not df_raw.empty:
                    save_cache(org_id, selected_id, df_raw, sd_str, ed_str)
                    df_processed = check_cache(org_id, selected_id, sd_str, ed_str)

        if not df_processed.empty:
            df_final             = gate.analyze_irrigation_behavior(df_processed)
            df_final             = gate.extract_phenology(df_final)

            model_fallback_msg = None
            if detector_key != "threshold":
                try:
                    district = field_display[selected_id]["district"]
                    df_final = predict_awd_states(
                        df_final, f"{org_id}_{detector_key}", selected_id, district,
                        field_area_ha, sd_str, ed_str,
                    )
                except FileNotFoundError:
                    model_fallback_msg = (
                        f"{detector_label} has not been trained yet — showing "
                        f"Threshold Gate results instead. Run "
                        f"`python -m src.ai.train_{detector_key}` to train it."
                    )
                    detector_label = "Threshold Gate (rule-based)"

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
            st.session_state["signal_last_run_at"]    = datetime.datetime.now()
            st.session_state["signal_df"]             = df_final
            st.session_state["signal_field_id"]       = selected_id
            st.session_state["signal_cache_source"]   = cache_source
            st.session_state["signal_total_awd"]      = total_awd
            st.session_state["signal_sowing_date"]    = sowing_date_str
            st.session_state["signal_harvest_date"]   = harvest_date_str
            st.session_state["signal_season_length"]  = season_length_val
            st.session_state["signal_from_phenology"] = season_from_phenology
            st.session_state["signal_detector_used"]  = detector_label
            st.session_state["signal_model_fallback_msg"] = model_fallback_msg

            st.session_state["carbon_ready"]          = True
            st.session_state["carbon_field_id"]       = selected_id
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
            st.rerun()

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
        def _fmt_ddmmyyyy(date_str):
            try:
                return datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%d-%m-%Y")
            except (ValueError, TypeError):
                return date_str

        _sowing_str      = _fmt_ddmmyyyy(st.session_state["signal_sowing_date"])
        _harvest_str     = _fmt_ddmmyyyy(st.session_state["signal_harvest_date"])
        _season_len      = st.session_state["signal_season_length"]
        _from_phenology  = st.session_state["signal_from_phenology"]
        _season_len_str  = f"{_season_len} days" if _from_phenology else "120 days (fallback)"
        _detector_used   = st.session_state.get("signal_detector_used", "Threshold Gate (rule-based)")
        _model_fallback  = st.session_state.get("signal_model_fallback_msg")
        _avg_confidence  = _sig_df["confidence"].mean() if "confidence" in _sig_df.columns else None
        # st.metric truncates with an ellipsis once the value overflows its
        # card — the full descriptive labels ("... (AI baseline)") are too
        # long for a 1/5-width column, so show a short form here only.
        _DETECTOR_SHORT_LABEL = {
            "Threshold Gate (rule-based)": "Threshold Gate",
            "Random Forest (AI baseline)": "Random Forest",
            "XGBoost (AI baseline)": "XGBoost",
        }

        with col_pipeline:
            st.caption(f"Data source: `{_cache_src}`")
            if not _from_phenology:
                st.warning(
                    "⚠️ Phenology markers not detected — season length uses the 120-day fallback. "
                    "Verify manually before carbon submission."
                )
            if _model_fallback:
                st.warning(f"⚠️ {_model_fallback}")
            _c1, _c2, _c3, _c4 = st.columns(4)
            _c1.metric("AWD Events",    _total_awd)
            _c2.metric("Sowing Date",   _sowing_str)
            _c3.metric("Harvest Date",  _harvest_str)
            _c4.metric("Season Length", _season_len_str)
            st.metric(
                "Detector Used", _DETECTOR_SHORT_LABEL.get(_detector_used, _detector_used),
                delta=f"{_avg_confidence:.0%} avg confidence" if _avg_confidence is not None else None,
                delta_color="off",
            )

        # Chart — full width
        _raw_marker_color = (
            "rgba(255,255,255,0.30)" if _theme_mode == "dark" else "rgba(20,20,20,0.30)"
        )
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=_sig_df["date"], y=_sig_df["vv"],
            mode="markers", name="Raw VV",
            marker=dict(color=_raw_marker_color, size=5),
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
            template="plotly_dark" if _theme_mode == "dark" else "plotly_white",
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
        if "predicted_label" in _sig_df.columns:
            _audit_cols.append("predicted_label")
        if "confidence" in _sig_df.columns:
            _audit_cols.append("confidence")
        st.markdown("#### Compliance Audit Trail Ledger")
        st.caption(f"{len(_sig_df)} observations · scroll to see all rows")
        st.dataframe(
            _sig_df[_audit_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "date":            st.column_config.TextColumn("Date"),
                "vv_smoothed":     st.column_config.NumberColumn("VV (dB)",  format="%.4f"),
                "vh_smoothed":     st.column_config.NumberColumn("VH (dB)",  format="%.4f"),
                "vv_zscore":       st.column_config.NumberColumn("Z-Score",  format="%.3f"),
                "is_flooded":      st.column_config.CheckboxColumn("Flooded"),
                "drydown_event":   st.column_config.CheckboxColumn("AWD Event"),
                "is_sowing":       st.column_config.CheckboxColumn("Sowing"),
                "is_harvest":      st.column_config.CheckboxColumn("Harvest"),
                "predicted_label": st.column_config.TextColumn("Model Label"),
                "confidence":      st.column_config.NumberColumn("Confidence", format="percent"),
            },
        )

    elif not trigger:
        with col_pipeline:
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.info(
                "Select a season and click **Run Analytics Engine** to fetch "
                "Sentinel-1 SAR data and detect AWD events for the selected field."
            )


_LIVESTOCK_TYPE_LABELS = {
    "cattle_dairy": "Dairy cattle", "cattle_nondairy": "Non-dairy cattle",
    "buffalo": "Buffalo", "sheep": "Sheep", "goat": "Goats",
}


def _alm_practice_form(scenario_label: str, existing: dict, existing_livestock: list, key_prefix: str):
    """Renders one baseline/project ALM practice-schedule form (Table 4 subset).
    Returns (practices_dict, livestock_list)."""
    existing = existing or {}
    existing_livestock = {e["livestock_type"]: e for e in (existing_livestock or [])}
    st.markdown(f"##### {scenario_label}")
    _CROP_TYPE_OPTIONS = ["Wheat", "Maize", "Rice", "Sugarcane", "Other Crops"]
    _existing_crop = existing.get("crop_type") or ""
    _crop_default_idx = (
        _CROP_TYPE_OPTIONS.index(_existing_crop) if _existing_crop in _CROP_TYPE_OPTIONS else 4
    )
    crop_type = st.selectbox(
        "Crop type",
        options=_CROP_TYPE_OPTIONS,
        index=_crop_default_idx,
        key=f"{key_prefix}_crop_type",
        help="Determines the biomass-burning combustion factor (IPCC 2019 "
             "Table 2.6). 'Other Crops' is the conservative default for any "
             "crop not in this list, and for pre-existing free-text entries.",
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        crop_rotation = st.checkbox(
            "Crop rotation", value=bool(existing.get("crop_rotation")), key=f"{key_prefix}_rotation"
        )
    with c2:
        cover_crops = st.checkbox(
            "Cover crops", value=bool(existing.get("cover_crops")), key=f"{key_prefix}_cover"
        )
    with c3:
        intercropping = st.checkbox(
            "Intercropping", value=bool(existing.get("intercropping")), key=f"{key_prefix}_intercrop"
        )

    t1, t2 = st.columns(2)
    with t1:
        tillage = st.checkbox(
            "Tillage practiced", value=bool(existing.get("tillage")), key=f"{key_prefix}_tillage"
        )
        tillage_depth_cm = st.number_input(
            "Tillage depth (cm)", min_value=0.0, max_value=60.0,
            value=float(existing.get("tillage_depth_cm") or 0.0), step=1.0,
            key=f"{key_prefix}_tillage_depth",
        )
    with t2:
        residue_removed = st.checkbox(
            "Crop residue removed", value=bool(existing.get("residue_removed")), key=f"{key_prefix}_residue_removed"
        )
        residue_burned_kg_ha = st.number_input(
            "Residue burned (kg/ha)", min_value=0.0, max_value=15000.0,
            value=float(existing.get("residue_burned_kg_ha") or 0.0), step=100.0,
            key=f"{key_prefix}_residue_burned",
            help="Mass of crop residue burned in-field per hectare — drives "
                 "Eqs. 14/32 (CH4/N2O from biomass burning).",
        )

    n1, n2 = st.columns(2)
    with n1:
        synthetic_n_rate_kg_ha = st.number_input(
            "Synthetic N fertilizer (kg N/ha)", min_value=0.0, max_value=400.0,
            value=float(existing.get("synthetic_n_rate_kg_ha") or 0.0), step=5.0,
            key=f"{key_prefix}_synthetic_n",
        )
    with n2:
        organic_n_rate_kg_ha = st.number_input(
            "Organic N fertilizer (kg N/ha)", min_value=0.0, max_value=400.0,
            value=float(existing.get("organic_n_rate_kg_ha") or 0.0), step=5.0,
            key=f"{key_prefix}_organic_n",
        )

    f1, f2 = st.columns(2)
    with f1:
        n_fixing_species = st.checkbox(
            "N-fixing cover crop (e.g. legume)", value=bool(existing.get("n_fixing_species")),
            key=f"{key_prefix}_nfix",
        )
        n_fixing_dry_matter_kg_ha = st.number_input(
            "N-fixing residue dry matter (kg/ha)", min_value=0.0, max_value=10000.0,
            value=float(existing.get("n_fixing_dry_matter_kg_ha") or 0.0), step=100.0,
            key=f"{key_prefix}_nfix_dm", disabled=not n_fixing_species,
        )
    with f2:
        fuel_use_l_ha = st.number_input(
            "Fossil fuel use (L/ha)", min_value=0.0, max_value=200.0,
            value=float(existing.get("fuel_use_l_ha") or 0.0), step=1.0,
            key=f"{key_prefix}_fuel",
            help="Diesel/gasoline consumed per hectare for this scenario's "
                 "field operations — drives Eqs. 6-7 (fossil fuel CO2).",
        )

    track_yield = st.checkbox(
        "Track crop yield (for VMD0054 production-decline leakage screening)",
        value=existing.get("crop_yield_t_ha") is not None, key=f"{key_prefix}_track_yield",
        help="VM0042 Table 4 lists crop yield as 'where applicable'. Entering it "
             "for both scenarios lets the engine screen for production-decline "
             "leakage (§8.4.3) instead of leaving it unscreened.",
    )
    crop_yield_t_ha = st.number_input(
        "Crop yield (t/ha)", min_value=0.0, max_value=50.0,
        value=float(existing.get("crop_yield_t_ha") or 0.0), step=0.1,
        key=f"{key_prefix}_crop_yield", disabled=not track_yield,
    ) if track_yield else None

    has_livestock = st.checkbox(
        "Integrated crop-livestock system (pasture-based grazing)",
        value=bool(existing_livestock), key=f"{key_prefix}_has_livestock",
        help="VM0042 §8.2.6/§8.2.7/§8.2.10 (Condition 1e/3a). Scoped to "
             "Pasture/Range/Paddock grazing only — feedlots and other manure "
             "management systems are not modeled.",
    )
    livestock = []
    if has_livestock:
        with st.expander("🐄 Livestock (enteric fermentation + manure CH4/N2O)", expanded=True):
            for ltype, label in _LIVESTOCK_TYPE_LABELS.items():
                lc1, lc2 = st.columns(2)
                existing_entry = existing_livestock.get(ltype, {})
                with lc1:
                    pop = st.number_input(
                        f"{label} — head count", min_value=0, max_value=500,
                        value=int(existing_entry.get("population_head") or 0), step=1,
                        key=f"{key_prefix}_livestock_{ltype}_pop",
                    )
                with lc2:
                    ps_options = ["low", "high"]
                    ps_default = existing_entry.get("productivity_system") or "low"
                    productivity_system = st.selectbox(
                        f"{label} — productivity system",
                        options=ps_options,
                        index=ps_options.index(ps_default) if ps_default in ps_options else 0,
                        format_func=lambda p: p.capitalize(),
                        key=f"{key_prefix}_livestock_{ltype}_ps",
                        disabled=pop <= 0,
                    )
                if pop > 0:
                    livestock.append({
                        "livestock_type": ltype, "population_head": pop,
                        "productivity_system": productivity_system,
                    })

    practices = {
        "crop_type": crop_type.strip() or None,
        "crop_rotation": crop_rotation,
        "cover_crops": cover_crops,
        "intercropping": intercropping,
        "tillage": tillage,
        "tillage_depth_cm": tillage_depth_cm,
        "residue_removed": residue_removed,
        "residue_burned_kg_ha": residue_burned_kg_ha,
        "synthetic_n_rate_kg_ha": synthetic_n_rate_kg_ha,
        "organic_n_rate_kg_ha": organic_n_rate_kg_ha,
        "n_fixing_species": n_fixing_species,
        "n_fixing_dry_matter_kg_ha": n_fixing_dry_matter_kg_ha,
        "fuel_use_l_ha": fuel_use_l_ha,
        "crop_yield_t_ha": crop_yield_t_ha,
    }
    return practices, livestock


def _parse_soc_values(text: str) -> list:
    values = []
    for token in text.replace(",", "\n").splitlines():
        token = token.strip()
        if token:
            try:
                values.append(float(token))
            except ValueError:
                pass
    return values


def render_practice_tab():
    if not selected_id:
        st.info("Draw and save a field in the **Spatial Asset Inspection** tab first.")
        st.stop()

    st.markdown("#### 🧪 Practice & Soil Data — VM0042 Improved Agricultural Land Management")
    st.caption(
        "VM0042 credits practice changes on non-wetland cropland/grassland — "
        "**not applicable to flooded rice paddies** (VM0042 §4, condition 8). "
        "Enter the baseline and project practice schedule (Table 4 subset) and "
        "lab-measured soil organic carbon (SOC) samples for this field."
    )
    st.markdown("---")

    existing_practices = get_alm_practice_schedule(org_id, selected_id)
    existing_livestock = get_alm_livestock_schedule(org_id, selected_id)

    st.markdown("### 📋 Practice Schedule")
    col_bsl, col_wp = st.columns(2)
    with col_bsl:
        bsl_practices, bsl_livestock = _alm_practice_form(
            "Baseline scenario", existing_practices.get("baseline"),
            existing_livestock.get("baseline"), key_prefix="bsl",
        )
    with col_wp:
        wp_practices, wp_livestock = _alm_practice_form(
            "Project scenario", existing_practices.get("project"),
            existing_livestock.get("project"), key_prefix="wp",
        )

    if st.button("💾 Save Practice Schedule", type="primary") and _can_write():
        save_alm_practice_schedule(org_id, selected_id, "baseline", bsl_practices)
        save_alm_practice_schedule(org_id, selected_id, "project", wp_practices)
        save_alm_livestock_schedule(org_id, selected_id, "baseline", bsl_livestock)
        save_alm_livestock_schedule(org_id, selected_id, "project", wp_livestock)
        st.success("Practice schedule saved.")
        st.rerun()

    st.markdown("---")
    st.markdown("### 🧫 Soil Organic Carbon Samples (Quantification Approach 2)")
    st.caption(
        "Paired lab measurements (tCO₂e/ha) at the project site and a linked "
        "baseline control site, at the start and end of the verification "
        "period. At least 3 samples per cell are required (Eqs. 46-47, 70-71)."
    )

    existing_soc = get_soc_measurements(org_id, selected_id)
    soc_inputs = {}
    soc_labels = {
        ("project", "t_start"): "Project site — start of period",
        ("project", "t_final"): "Project site — end of period",
        ("control", "t_start"): "Baseline control site — start of period",
        ("control", "t_final"): "Baseline control site — end of period",
    }
    soc_cols = st.columns(2)
    for i, (key, label) in enumerate(soc_labels.items()):
        with soc_cols[i % 2]:
            existing_values = existing_soc.get(key, [])
            default_text = "\n".join(str(v) for v in existing_values)
            text = st.text_area(
                label, value=default_text, height=100,
                placeholder="One value per line, e.g.\n40.2\n41.8\n39.5",
                key=f"soc_{key[0]}_{key[1]}",
            )
            values = _parse_soc_values(text)
            soc_inputs[key] = values
            st.caption(f"{len(values)} sample(s)" + (" — need ≥ 3" if len(values) < 3 else " ✓"))

    if st.button("💾 Save SOC Measurements", type="primary") and _can_write():
        for (site_type, timepoint), values in soc_inputs.items():
            save_soc_measurements(org_id, selected_id, site_type, timepoint, values)
        st.success("SOC measurements saved.")
        st.rerun()

    st.markdown("---")
    practice_schedule = {"baseline": bsl_practices, "project": wp_practices}
    problems = gate.check_completeness(practice_schedule, soc_inputs)
    if problems:
        st.warning(
            "Not ready for credit calculation yet:\n\n" + "\n".join(f"- {p}" for p in problems)
        )
    else:
        st.success("Practice schedule and SOC data are complete — proceed to the Carbon Asset Ledger tab.")
        st.session_state["alm_data_field_id"]     = selected_id
        st.session_state["alm_practice_schedule"] = practice_schedule
        st.session_state["alm_soc_measurements"]  = soc_inputs
        st.session_state["alm_area_ha"]           = field_area
        st.session_state["alm_livestock_schedule"] = {
            "baseline": bsl_livestock, "project": wp_livestock,
        }


# ===========================================================================
# TAB 2 dispatcher
# ===========================================================================
with tab_2:
    if selected_uses_sar:
        render_signal_analytics_tab()
    else:
        render_practice_tab()

# ===========================================================================
# TAB 3 — CARBON ASSET LEDGER
# ===========================================================================
def _render_credit_history_panel(field_id: str):
    """Every Calculate Carbon Credits click is logged to credit_history —
    this surfaces that log so past runs survive a session/page revisit
    instead of vanishing once export_cr falls out of session_state."""
    history = get_credit_history(org_id, field_id)
    if not history:
        return

    st.markdown("---")
    st.markdown("#### 🕘 Verification History")
    st.caption(
        f"{len(history)} prior calculation(s) recorded for this field — "
        "logged automatically each time Calculate Carbon Credits runs."
    )
    rows = []
    for h in history:
        row = {
            "Calculated At": h["calculated_at"],
            "Final Issuance (tCO₂e)": round(h["final_issuance"], 4),
        }
        cumulative = h["result"].get("cumulative_delta_co2_wp")
        if cumulative is not None:
            row["Cumulative SOC Δ (tCO₂e)"] = round(cumulative, 4)
        row["Inputs"] = ", ".join(f"{k}={v}" for k, v in h["inputs"].items())
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_carbon_tab_rice_awd():
    if not selected_id:
        st.info("Draw and save a field in the **Spatial Asset Inspection** tab first.")
        st.stop()
    st.markdown("#### 💰 Carbon Compliance Ledger — VM0051 Tier 2")
    st.caption(
        "Parameters auto-fill from Signal Analytics. Override as needed, "
        "then click **Calculate Carbon Credits**."
    )
    st.markdown("---")

    # Gate every carbon_* read behind carbon_field_id matching the currently
    # selected field — otherwise a stale result from a previously selected
    # field (or, once multiple tenants can share a browser tab, a previous
    # user's session) would silently render as this field's/this user's own
    # figures. Mirrors how signal_field_id already gates the Signal
    # Analytics tab's own session-state reads (see app.py:785-787).
    _carbon_valid   = st.session_state.get("carbon_field_id") == selected_id
    default_season  = int(st.session_state.get("carbon_season_length", 120)) if _carbon_valid else 120
    default_awd     = int(st.session_state.get("carbon_total_awd", 0)) if _carbon_valid else 0
    default_area    = float(st.session_state.get("carbon_area_ha", 1.0)) if _carbon_valid else 1.0
    from_phenology  = st.session_state.get("season_from_phenology", False) if _carbon_valid else False

    if not from_phenology and _carbon_valid and st.session_state.get("carbon_ready"):
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
        q_n_kg_per_ha   = st.number_input(
            "N Input (kg N/ha)",
            min_value=0.0, max_value=300.0, value=100.0, step=5.0,
            help="Nitrogen fertilizer applied in project scenario (kg N/ha). "
                 "Used in VM0051 §8.3.2 Eq. 25 N₂O correction. "
                 "Bangladesh boro rice default ≈ 100 kg N/ha.",
        )

    with st.expander("⚙️ Advanced VM0051 Eq. 6/7 parameters (pre-season & organic amendments)"):
        st.caption(
            "These scaling factors are mandatory parts of VM0051's baseline/project CH₄ "
            "formula (Eq. 6/7) — they are not optional extras. Defaults follow VM0051's "
            "own stated baseline assumption (§8.2.3 footnote 16: 5 t/ha straw)."
        )
        pc1, pc2 = st.columns(2)
        with pc1:
            preseason_label = st.selectbox(
                "Pre-season water regime (Table 5.13)",
                options=[
                    "Non-flooded pre-season < 180 days (double/multi-cropping)",
                    "Non-flooded pre-season > 180 days (single cropping)",
                ],
                help="VM0051 Eq. 6, SC_p — applies identically to baseline and project.",
            )
            preseason_category = "short" if preseason_label.startswith("Non-flooded pre-season <") else "long"
        with pc2:
            st.markdown("&nbsp;", unsafe_allow_html=True)
        oc1, oc2 = st.columns(2)
        _CFOA_LABELS = {
            "straw_shortly_before": "Straw, incorporated <30 days before cultivation",
            "straw_long_before":    "Straw, incorporated >30 days before cultivation",
            "compost":              "Compost",
            "farmyard_manure":      "Farmyard manure",
            "green_manure":         "Green manure",
        }
        with oc1:
            st.markdown("**Baseline organic amendment** (§8.2.3 footnote 16)")
            bsl_amendment_type = st.selectbox(
                "Type", options=list(_CFOA_LABELS.keys()),
                format_func=lambda k: _CFOA_LABELS[k], key="bsl_amendment_type",
            )
            bsl_amendment_rate = st.number_input(
                "Rate (t/ha)", min_value=0.0, max_value=50.0, value=5.0, step=0.5,
                key="bsl_amendment_rate",
            )
        with oc2:
            st.markdown("**Project organic amendment**")
            wp_amendment_type = st.selectbox(
                "Type", options=list(_CFOA_LABELS.keys()),
                format_func=lambda k: _CFOA_LABELS[k], key="wp_amendment_type",
            )
            wp_amendment_rate = st.number_input(
                "Rate (t/ha)", min_value=0.0, max_value=50.0, value=5.0, step=0.5,
                key="wp_amendment_rate",
                help="Defaults to matching the baseline (no assumed change in straw "
                     "management) — adjust if the project removes/burns straw instead.",
            )

    run_carbon = st.button("⚡ Calculate Carbon Credits", type="primary")

    if run_carbon or (_carbon_valid and st.session_state.get("carbon_ready")):
        cr = carbon_engine.calculate_credits(
            awd_events=carbon_awd,
            season_length_days=carbon_season,
            area_ha=carbon_area,
            q_n_kg_per_ha=q_n_kg_per_ha,
            preseason_category=preseason_category,
            baseline_amendments=((bsl_amendment_type, bsl_amendment_rate),),
            project_amendments=((wp_amendment_type, wp_amendment_rate),),
        )
        st.session_state["export_cr"]            = cr
        st.session_state["export_q_n"]           = q_n_kg_per_ha
        st.session_state["export_carbon_area"]   = carbon_area
        st.session_state["export_carbon_season"] = carbon_season
        st.session_state["export_carbon_awd"]    = carbon_awd

        # A viewer can still trigger the (read-only, no side effects)
        # calculation above and see the result — only persisting it to
        # credit_history is an actual write, so only that is role-gated.
        if run_carbon and _can_write():
            save_credit_history(org_id, selected_id, "rice_awd", {
                "season_length_days": carbon_season,
                "area_ha": carbon_area,
                "awd_events": carbon_awd,
                "q_n_kg_per_ha": q_n_kg_per_ha,
            }, cr)

        st.markdown("---")

        if not cr.get("qa3_pathway_valid", True):
            st.error(
                "🚫 **QA3 pathway not valid for this project.** " + cr["qa3_block_reason"]
            )
            st.stop()

        # Summary metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Baseline Emissions",  f"{cr['e_baseline']:.2f} kg CH₄")
        m2.metric("Project Emissions",   f"{cr['e_project']:.2f} kg CH₄")
        m3.metric("Avoided (tCO₂e)",     f"{cr['delta_e_co2e']:.3f}")
        m4.metric("Final Credits Issued", f"{cr['final_issuance']:.3f}")

        st.markdown("---")
        st.markdown("#### 📐 Step-by-Step Audit Trail")

        # Step 1
        st.markdown(
            "**Step 1: Baseline Scenario** — continuous flooding, "
            f"$SF_w = 1.0$, $SC_p = {cr['sc_preseason']}$, $SC_o = {cr['sc_organic_bsl']:.3f}$"
        )
        st.latex(r"E_{\text{baseline}} = EF_c \times SF_{w,\text{bsl}} \times SC_p \times SC_{o,\text{bsl}} \times D \times A")
        st.latex(
            f"E_{{\\text{{baseline}}}} = {cr['ef_c_used']} \\times 1.0 \\times {cr['sc_preseason']}"
            f" \\times {cr['sc_organic_bsl']:.3f} \\times {carbon_season}"
            f" \\times {carbon_area:.1f} = {cr['e_baseline']:.2f}\\text{{ kg CH}}_4"
        )

        # Step 2
        st.markdown(
            f"**Step 2: Project Scenario** — {carbon_awd} AWD event(s) "
            f"→ $SF_{{w,\\text{{project}}}} = {cr['sf_w_project']}$, "
            f"$SC_{{o,\\text{{wp}}}} = {cr['sc_organic_wp']:.3f}$"
        )
        st.latex(r"E_{\text{project}} = EF_c \times SF_{w,\text{project}} \times SC_p \times SC_{o,\text{wp}} \times D \times A")
        st.latex(
            f"E_{{\\text{{project}}}} = {cr['ef_c_used']} \\times {cr['sf_w_project']}"
            f" \\times {cr['sc_preseason']} \\times {cr['sc_organic_wp']:.3f}"
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

        # Step 5 — QA3 flat uncertainty deduction (VM0051 §8.6.3)
        st.markdown(
            "**Step 5: QA3 Uncertainty Deduction** — VM0051 §8.6.3, flat 15% for "
            "projects < 60,000 tCO₂e/yr"
        )
        st.latex(
            r"\Delta E_{\text{after UNC}} = \Delta E_{\text{CO}_2\text{e}} "
            r"\times (1 - UNC_{\text{QA3}})"
        )
        st.latex(
            f"\\Delta E_{{\\text{{after UNC}}}} = {cr['delta_e_co2e']:.4f}"
            f" \\times 0.85 = {cr['ch4_after_unc']:.4f}\\text{{ tCO}}_2\\text{{e}}"
        )

        # Step 6 — N2O irrigation correction (VM0051 §8.3.2, Eq. 25)
        st.markdown(
            "**Step 6: N₂O Irrigation Correction** — VM0051 §8.3.2, Eq. 25"
        )
        if carbon_awd == 0:
            st.info("No irrigation regime change — N₂O correction is zero (Eq. 25 not triggered).")
        else:
            st.latex(
                r"PE_{\text{Red-Irri}} = Q_N \times A \times CF_{N_2O} "
                r"\times 10^{-3} \times GWP_{N_2O}"
            )
            st.latex(
                f"PE_{{\\text{{Red-Irri}}}} = {q_n_kg_per_ha:.0f} \\times {carbon_area:.2f}"
                f" \\times 0.00314 \\times 10^{{-3}} \\times 265"
                f" = {cr['pe_n2o_tco2e']:.4f}\\text{{ tCO}}_2\\text{{e}}"
            )

        # Step 7 — N2O penalty context (NOT a §8.4 leakage screen — PE_Red-Irri is
        # a mandatory Eq. 29 project emission, always subtracted in full below;
        # §8.4 leakage sources are organic-amendment import/yield decline/biomass
        # diversion, none of which this engine computes)
        st.markdown("**Step 7: N₂O Penalty Context** — informational only")
        st.caption(
            f"N₂O correction (PE_Red-Irri) is **{cr['n2o_penalty_pct_of_gross']:.1f}%** of "
            "gross CH₄ reduction. This is a mandatory VM0051 Eq. 29 project emission, not "
            "a §8.4 leakage source — it is always subtracted in full below regardless of "
            "this percentage."
        )

        # Step 8 — Net reductions (VM0051 Eq. 29, simplified)
        st.markdown(
            "**Step 8: Net Reductions** — VM0051 Eq. 29 "
            "(CH₄ soil term, simplified: no straw burning, no fossil fuel change)"
        )
        st.latex(
            r"ER = \Delta CH4_{\text{soil}} \times (1 - UNC_{CH4}) - PE_{\text{Red-Irri}}"
        )
        st.latex(
            f"ER = {cr['ch4_after_unc']:.4f} - {cr['pe_n2o_tco2e']:.4f}"
            f" = \\mathbf{{{cr['final_issuance']:.4f}\\text{{ tCO}}_2\\text{{e}}}}"
        )

        # Outcome banner
        if cr["final_issuance"] == 0.0 and carbon_awd == 0:
            st.info(
                "ℹ️ No AWD events verified — project emissions equal baseline. "
                "Zero carbon credits issued (no methane reduction demonstrated)."
            )
        elif cr["final_issuance"] == 0.0:
            st.warning(
                "⚠️ N₂O correction fully offsets CH₄ reduction after uncertainty deduction. "
                "Zero net credits issued."
            )
        else:
            st.success(
                f"✅ **{cr['final_issuance']:.4f} tCO₂e** net verified credits — "
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
                "ef_c_used":                cr["ef_c_used"],
                "sf_w_project":             cr["sf_w_project"],
                "sc_preseason":             cr["sc_preseason"],
                "sc_organic_bsl":           cr["sc_organic_bsl"],
                "sc_organic_wp":            cr["sc_organic_wp"],
                "p_uncertainty":            cr["p_uncertainty"],
                "e_baseline":               cr["e_baseline"],
                "e_project":                cr["e_project"],
                "delta_e_ch4":              cr["delta_e_ch4"],
                "delta_e_co2e":             cr["delta_e_co2e"],
                "unc_tco2e":                cr["unc_tco2e"],
                "ch4_after_unc":            cr["ch4_after_unc"],
                "pe_n2o_tco2e":             cr["pe_n2o_tco2e"],
                "q_n_kg_per_ha":            cr["q_n_kg_per_ha"],
                "n2o_penalty_pct_of_gross": cr["n2o_penalty_pct_of_gross"],
                "final_issuance":           cr["final_issuance"],
                "confidence_pct":           None,
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

    _render_credit_history_panel(selected_id)


def render_carbon_tab_alm():
    if not selected_id:
        st.info("Draw and save a field in the **Spatial Asset Inspection** tab first.")
        st.stop()

    st.markdown("#### 💰 Carbon Compliance Ledger — VM0042 Improved ALM")
    st.caption(
        "Reads the practice schedule and SOC samples saved in the "
        "**Practice & Soil Data** tab. Covers tillage/residue, fertilizer, "
        "crop planting/harvesting, and pasture-based integrated crop-"
        "livestock practice changes — liming, non-pasture manure systems, "
        "and other leakage sources are out of scope (see Methodology in the "
        "exported report)."
    )
    st.markdown("---")

    practice_schedule = st.session_state.get("alm_practice_schedule")
    soc_measurements   = st.session_state.get("alm_soc_measurements")
    livestock_schedule = st.session_state.get("alm_livestock_schedule") or {"baseline": [], "project": []}
    default_area       = st.session_state.get("alm_area_ha", field_area)

    if practice_schedule is None or soc_measurements is None or \
            st.session_state.get("alm_data_field_id") != selected_id:
        st.info(
            "ℹ️ Complete the **Practice & Soil Data** tab for this field first "
            "— the practice schedule and SOC samples must be saved and complete "
            "before credits can be calculated."
        )
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        carbon_area = st.number_input(
            "Field Area (ha)", 0.1, 500.0, float(default_area), step=0.1, key="alm_area_input"
        )
    with c2:
        verification_years = st.number_input(
            "Verification period (years)", 1.0, 5.0, 1.0, step=1.0,
            help="Length of the verification period, x in Eqs. 46-47. Capped at "
                 "5 years — VM0042's mandatory SOC remeasurement cadence "
                 "(monitoring tables p.92/p.128; June 2026 Corrections Clarification 8) "
                 "requires remeasurement at least every 5 years.",
            key="alm_verif_years",
        )
    with c3:
        non_permanence_risk_pct = st.number_input(
            "Non-permanence risk rating (%)", 0.0, 100.0, 20.0, step=1.0,
            help="AFOLU buffer-pool risk rating from the VCS Standard's risk "
                 "tool — a project-specific value, not computed by this app.",
            key="alm_npr",
        )

    run_carbon = st.button("⚡ Calculate Carbon Credits", type="primary", key="alm_run_carbon")

    if run_carbon or st.session_state.get("alm_carbon_ready"):
        _prior_cumulative = get_alm_cumulative_delta(org_id, selected_id)
        cr = carbon_engine.calculate_credits(
            practice_schedule=practice_schedule,
            soc_measurements=soc_measurements,
            area_ha=carbon_area,
            verification_years=verification_years,
            non_permanence_risk_pct=non_permanence_risk_pct,
            prior_cumulative_delta_co2_wp_t=_prior_cumulative,
            baseline_livestock=livestock_schedule.get("baseline"),
            project_livestock=livestock_schedule.get("project"),
        )
        st.session_state["export_cr"] = cr

        st.markdown("---")

        if cr.get("production_decline_leakage_blocked"):
            st.error("🚫 **Issuance blocked.** " + cr["leakage_block_reason"])
            st.stop()

        # Same viewer carve-out as the rice path: viewing a live calculation
        # is read-only; persisting it (cumulative delta + credit_history) is
        # the actual write and is what gets role-gated.
        if run_carbon and _can_write():
            update_alm_cumulative_delta(org_id, selected_id, cr["cumulative_delta_co2_wp"])
            save_credit_history(org_id, selected_id, "cropland_alm_vm0042", {
                "area_ha": carbon_area,
                "verification_years": verification_years,
                "non_permanence_risk_pct": non_permanence_risk_pct,
            }, cr)
        st.session_state["alm_carbon_ready"] = True

        if cr["production_decline_leakage_data_available"]:
            st.success(
                "✅ **Production-decline leakage screened clean** — project yield "
                f"maintained or improved (foregone production: {cr['foregone_production_t']:.2f} t)."
            )
        else:
            st.warning(
                "⚠️ **Production-decline leakage not screened** — enter crop yield "
                "for both scenarios in the Practice & Soil Data tab to screen this "
                "(VM0042 §8.4.3, VMD0054)."
            )
        st.warning(
            "⚠️ **Other leakage sources not screened.** " + cr["other_leakage_gap_note"]
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Net Reductions (ER)",  f"{cr['er_t']:.3f} tCO₂e")
        m2.metric("Net Removals (CR)",    f"{cr['cr_t']:.3f} tCO₂e")
        m3.metric("SOC Uncertainty",      f"{cr['unc_co2_pct']:.1f}%")
        m4.metric("Final Credits Issued", f"{cr['final_issuance']:.3f} tCO₂e")

        st.markdown("---")
        st.markdown("#### 📐 Step-by-Step Audit Trail")

        st.markdown("**Step 1: N₂O from fertilizer** — Eqs. 17-23")
        st.caption(
            f"EF_Ndirect used: {cr['ef_ndirect_used']} (conservative direction "
            "per §8.6.3 — low value when the project reduces the N source, "
            "high value when it increases it)"
        )
        st.latex(
            f"N_2O_{{\\text{{fert,bsl}}}} = {cr['n2o_fert_bsl']:.4f}\\text{{ tCO}}_2\\text{{e}}"
            f" \\qquad N_2O_{{\\text{{fert,wp}}}} = {cr['n2o_fert_wp']:.4f}\\text{{ tCO}}_2\\text{{e}}"
        )

        st.markdown("**Step 2: N₂O from N-fixing cover-crop residues** — Eqs. 24-25")
        st.latex(
            f"N_2O_{{\\text{{Nfix,bsl}}}} = {cr['n2o_nfix_bsl']:.4f}\\text{{ tCO}}_2\\text{{e}}"
            f" \\qquad N_2O_{{\\text{{Nfix,wp}}}} = {cr['n2o_nfix_wp']:.4f}\\text{{ tCO}}_2\\text{{e}}"
        )

        st.markdown("**Step 3: CH₄ and N₂O from residue burning** — Eqs. 14, 32")
        st.latex(
            f"CH_{{4,bb}}: {cr['ch4_bb_bsl']:.4f} \\to {cr['ch4_bb_wp']:.4f}"
            f"\\qquad N_2O_{{bb}}: {cr['n2o_bb_bsl']:.4f} \\to {cr['n2o_bb_wp']:.4f}\\text{{ tCO}}_2\\text{{e}}"
        )

        st.markdown("**Step 3b: Livestock — enteric fermentation + manure CH₄/N₂O** — §8.2.6/§8.2.7/Ch 11 Eq. 11.5")
        st.caption("Pasture/Range/Paddock scope only (see caption above).")
        st.latex(
            f"CH_{{4,ent}}: {cr['ch4_ent_bsl']:.4f} \\to {cr['ch4_ent_wp']:.4f}"
            f"\\qquad CH_{{4,manure}}: {cr['ch4_manure_bsl']:.4f} \\to {cr['ch4_manure_wp']:.4f}\\text{{ tCO}}_2\\text{{e}}"
        )
        st.latex(
            f"N_2O_{{manure}}: {cr['n2o_manure_bsl']:.4f} \\to {cr['n2o_manure_wp']:.4f}\\text{{ tCO}}_2\\text{{e}}"
        )

        st.markdown("**Step 4: CO₂ from fossil fuel combustion** — Eqs. 6-7")
        st.latex(
            f"CO_{{2,ff}}: {cr['co2_ff_bsl']:.4f} \\to {cr['co2_ff_wp']:.4f}\\text{{ tCO}}_2\\text{{e}}"
        )

        st.markdown("**Step 5: SOC stock change (Quantification Approach 2)** — Eqs. 46-47")
        if not cr["soc_ready"]:
            st.warning(
                "Fewer than 3 SOC samples in one or more cells — SOC term "
                "treated as zero with a 100% uncertainty deduction."
            )
        st.latex(
            f"\\Delta CO_{{2,soil,bsl}} = {cr['delta_co2_soil_bsl']:.4f}\\text{{ tCO}}_2\\text{{e}}"
            f" \\qquad \\Delta CO_{{2,soil,wp}} = {cr['delta_co2_soil_wp']:.4f}\\text{{ tCO}}_2\\text{{e}}"
        )

        st.markdown("**Step 6: SOC uncertainty deduction** — Eqs. 70-71, 74 (probability of exceedance)")
        st.latex(f"UNC_{{CO_2}} = {cr['unc_co2_pct']:.1f}\\%")
        st.caption(
            "Approach-3 (default-factor) terms above carry no separate "
            "deduction, per §8.6.3, contingent on full activity-data coverage."
        )

        st.markdown("**Step 7: Net reductions and removals** — Eqs. 37, 40, 43")
        st.latex(
            f"ER_t = {cr['er_t']:.4f}\\text{{ tCO}}_2\\text{{e}} \\qquad"
            f" CR_t = {cr['cr_t']:.4f}\\text{{ tCO}}_2\\text{{e}} \\qquad"
            f" ERR_{{NET,t}} = {cr['err_net']:.4f}\\text{{ tCO}}_2\\text{{e}}"
        )
        st.caption("Other leakage sources (organic amendment import, livestock/biomass displacement) are out of scope — treated as zero (see warning above).")

        st.markdown(
            f"**Step 8: Buffer deduction & VCU issuance** — Eqs. 75-79, "
            f"non-permanence risk rating = {non_permanence_risk_pct:.0f}%"
        )
        st.latex(
            f"Bu_{{ER}} = {cr['bu_er']:.4f}\\text{{ tCO}}_2\\text{{e}} \\qquad"
            f" Bu_{{CR}} = {cr['bu_cr']:.4f}\\text{{ tCO}}_2\\text{{e}}"
        )
        st.latex(
            f"VCU_t = ({cr['err_net']:.4f} - {cr['bu_er']+cr['bu_cr']:.4f})"
            f" = \\mathbf{{{cr['final_issuance']:.4f}\\text{{ tCO}}_2\\text{{e}}}}"
        )

        if cr["final_issuance"] == 0.0:
            st.warning("⚠️ No net credits issued after uncertainty and buffer deductions.")
        else:
            st.success(
                f"✅ **{cr['final_issuance']:.4f} tCO₂e** net verified credits — "
                "ready for registry submission."
            )

        # ---- Export Evidence Package ----------------------------------------
        st.markdown("---")
        st.markdown("#### 📦 Export Evidence Package")

        _fi = {
            "field_id": selected_id,
            "name":     field_display[selected_id]["name"],
            "district": field_display[selected_id]["district"],
            "area_ha":  carbon_area,
        }
        _meta = {
            "verification_years": verification_years,
            "non_permanence_risk_pct": non_permanence_risk_pct,
        }
        _fid_slug = selected_id.replace("-", "").lower()

        col_pdf, col_json, col_csv = st.columns(3)
        with col_pdf:
            try:
                pdf_bytes = generate_pdf_alm(_fi, _meta, practice_schedule, cr, livestock_schedule)
                st.download_button(
                    "⬇️ Audit Report (PDF)", data=pdf_bytes,
                    file_name=f"terra_audit_alm_{_fid_slug}.pdf",
                    mime="application/pdf", use_container_width=True, type="primary",
                )
            except Exception as _err:
                st.error(f"PDF error: {_err}")
        with col_json:
            st.download_button(
                "⬇️ Audit Package (JSON)",
                data=generate_audit_json_alm(_fi, _meta, practice_schedule, soc_measurements, cr, livestock_schedule),
                file_name=f"audit_alm_{_fid_slug}.json",
                mime="application/json", use_container_width=True,
            )
        with col_csv:
            st.download_button(
                "⬇️ Practice & SOC Data (CSV)",
                data=generate_alm_data_csv(practice_schedule, soc_measurements),
                file_name=f"alm_data_{_fid_slug}.csv",
                mime="text/csv", use_container_width=True,
            )
    else:
        st.info("Click **Calculate Carbon Credits** to run the VM0042 quantification chain.")

    _render_credit_history_panel(selected_id)


# ===========================================================================
# TAB 3 dispatcher
# ===========================================================================
with tab_carbon:
    if selected_uses_sar:
        render_carbon_tab_rice_awd()
    else:
        render_carbon_tab_alm()

# ===========================================================================
# TAB 4 — AI VALIDATION
# ===========================================================================
with tab_validation:
    st.markdown("#### 🤖 AI Baseline Validation")
    st.caption(
        "Cross-validated performance of the Random Forest and XGBoost "
        "baselines trained in `src/ai/`."
    )
    st.info(
        "⚠️ **Labels come from the Threshold Gate itself** — there is no "
        "independently verified AWD ground truth in this project yet. The "
        "metrics below measure how well each ML model reproduces the "
        "Threshold Gate's own decisions on held-out folds, not accuracy "
        "against real-world irrigation truth. Threshold Gate is not listed "
        "as a row below for that reason — comparing it to the labels it "
        "defines would trivially score 100%."
    )

    st.markdown("##### 🛠️ Model Training Pipeline")
    st.caption(
        "Build the labeled dataset from cached field timeseries, then train "
        "and save a baseline model — no terminal required."
    )
    col_build, col_train = st.columns(2)

    with col_build:
        if st.button("📦 Build / Rebuild Dataset", use_container_width=True):
            _built_df = build_dataset(org_id)
            save_dataset(org_id, _built_df)
            if _built_df.empty:
                st.warning(
                    "No cached field timeseries found — run Signal Analytics "
                    "on at least one rice field first, then rebuild."
                )
            else:
                _n_groups = _built_df[
                    ["field_id", "window_start", "window_end"]
                ].drop_duplicates().shape[0]
                st.success(
                    f"Built dataset: {len(_built_df)} rows across "
                    f"{_n_groups} field/window group(s)."
                )
                st.dataframe(
                    _built_df["label"].value_counts().rename("count"),
                    use_container_width=True,
                )

    with col_train:
        _TRAIN_MODEL_CHOICES = {"Random Forest": "random_forest", "XGBoost": "xgboost"}
        _train_model_label = st.selectbox(
            "Model to train", options=list(_TRAIN_MODEL_CHOICES.keys()), key="train_model_choice"
        )
        _train_model_key = _TRAIN_MODEL_CHOICES[_train_model_label]
        if st.button(f"🎯 Train & Save {_train_model_label}", use_container_width=True):
            _train_df = load_dataset(org_id)
            if _train_df.empty:
                st.warning("No training dataset found. Click **Build / Rebuild Dataset** first.")
            else:
                _train_X, _train_y = build_features(_train_df)
                _train_result = train_and_evaluate(_train_model_key, _train_X, _train_y)
                # Namespace the saved artifact per org — otherwise one org's
                # classifier would be trained on/served to another's data
                # (see multi-tenant auth plan, Phase 2). MODEL_REGISTRY
                # lookups above still use the bare key; only the persisted
                # filename gets the org prefix.
                _train_result["model_name"] = f"{org_id}_{_train_model_key}"
                _saved_path = save_model(_train_result)
                st.success(f"Trained and saved to `data/ai_models/{_saved_path.name}`.")
                _existing_results = dict(st.session_state.get("validation_results") or {})
                _existing_results[_train_model_key] = {
                    "result": _train_result,
                    "summary": ai_evaluate.summarize_fold_predictions(_train_result),
                }
                st.session_state["validation_results"] = _existing_results

    st.markdown("---")
    run_validation = st.button("Run Validation", type="primary")

    if run_validation:
        _val_dataset = load_dataset(org_id)
        if _val_dataset.empty:
            st.warning(
                "No training dataset found. Run `python -m src.ai.dataset_builder` "
                "first, then return here."
            )
        else:
            _val_X, _val_y = build_features(_val_dataset)
            _val_results = {}
            for _mname in ["random_forest", "xgboost"]:
                _val_result = train_and_evaluate(_mname, _val_X, _val_y)
                _val_results[_mname] = {
                    "result": _val_result,
                    "summary": ai_evaluate.summarize_fold_predictions(_val_result),
                }
            st.session_state["validation_results"] = _val_results

    _val_results = st.session_state.get("validation_results")

    if _val_results:
        _MODEL_LABELS = {"random_forest": "Random Forest", "xgboost": "XGBoost"}

        _comparison_rows = {}
        _any_unstratified = False
        for _mname, _bundle in _val_results.items():
            _s = _bundle["summary"]
            _comparison_rows[_MODEL_LABELS[_mname]] = {
                "Threshold Agreement": f"{_s['threshold_agreement_score']:.1%}",
                "Precision (macro)": f"{_s['macro_avg']['precision']:.2f}",
                "Recall (macro)": f"{_s['macro_avg']['recall']:.2f}",
                "F1 (macro)": f"{_s['macro_avg']['f1']:.2f}",
                "CV Folds": _s["k_used"],
                "Stratified": "Yes" if _s["stratified"] else "No",
            }
            _any_unstratified = _any_unstratified or not _s["stratified"]

        st.markdown("##### Model Comparison")
        st.dataframe(pd.DataFrame(_comparison_rows).T, use_container_width=True)

        if _any_unstratified:
            st.warning(
                "⚠️ One or more models used unstratified CV folds (a class has "
                "too few samples to stratify) — minority-class metrics below "
                "are provisional until more labeled data accumulates."
            )

        for _mname, _bundle in _val_results.items():
            _result  = _bundle["result"]
            _summary = _bundle["summary"]
            _label   = _MODEL_LABELS[_mname]

            with st.expander(f"{_label} — Detailed Metrics", expanded=False):
                st.markdown("**Per-Class Metrics**")
                st.dataframe(
                    pd.DataFrame(_summary["per_class"]).T, use_container_width=True
                )

                _cm = _summary["confusion_matrix"]
                _fig_cm = go.Figure(data=go.Heatmap(
                    z=_cm["matrix"],
                    x=_cm["labels"],
                    y=_cm["labels"],
                    colorscale="Teal",
                    texttemplate="%{z}",
                    showscale=False,
                ))
                _fig_cm.update_layout(
                    template="plotly_dark" if _theme_mode == "dark" else "plotly_white",
                    title="Confusion Matrix (predicted vs. threshold-gate label)",
                    xaxis_title="Predicted",
                    yaxis_title="Threshold-Gate Label",
                    height=380,
                    margin=dict(t=50),
                )
                st.plotly_chart(_fig_cm, use_container_width=True)

                _fi = ai_evaluate.feature_importance(_result)
                _fig_fi = go.Figure(go.Bar(
                    x=list(_fi.values())[::-1],
                    y=list(_fi.keys())[::-1],
                    orientation="h",
                    marker=dict(color="#00ffcc"),
                ))
                _fig_fi.update_layout(
                    template="plotly_dark" if _theme_mode == "dark" else "plotly_white",
                    title="Feature Importance",
                    height=380,
                    margin=dict(t=50, l=140),
                )
                st.plotly_chart(_fig_fi, use_container_width=True)

                _roc = ai_evaluate.roc_curve_data(_result)
                _fig_roc = go.Figure()
                for _cls, _curve in _roc.items():
                    _auc_label = f"{_curve['auc']:.2f}" if _curve["auc"] is not None else "N/A"
                    _fig_roc.add_trace(go.Scatter(
                        x=_curve["fpr"], y=_curve["tpr"],
                        mode="lines", name=f"{_cls} (AUC={_auc_label})",
                    ))
                _fig_roc.add_trace(go.Scatter(
                    x=[0, 1], y=[0, 1], mode="lines", name="Chance",
                    line=dict(dash="dash", color="gray"),
                ))
                _fig_roc.update_layout(
                    template="plotly_dark" if _theme_mode == "dark" else "plotly_white",
                    title="ROC Curve (one-vs-rest)",
                    xaxis_title="False Positive Rate",
                    yaxis_title="True Positive Rate",
                    height=380,
                    margin=dict(t=50),
                )
                st.plotly_chart(_fig_roc, use_container_width=True)
                st.caption(
                    "⚠️ Curves for classes with very few samples today (e.g. "
                    "`drydown`) are numerically valid but not statistically "
                    "meaningful — read them as illustrative, not conclusive."
                )
    elif not run_validation:
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(
            "Click **Run Validation** to cross-validate the Random Forest and "
            "XGBoost baselines against the current AI training dataset."
        )


# ===========================================================================
# TAB 5 — PORTFOLIO
# ===========================================================================
with tab_portfolio:
    st.markdown("#### 📊 Portfolio Overview")
    st.caption(
        "Aggregate view across every registered field, spanning both the "
        "rice AWD (VM0051) and cropland ALM (VM0042) methodology paths."
    )
    st.markdown("---")

    _portfolio = get_portfolio_summary(org_id)

    if not _portfolio:
        st.info("No fields registered yet. Add one in the **Spatial Asset Inspection** tab.")
    else:
        _FIELD_TYPE_LABELS = {
            "rice_awd": "Rice — AWD (VM0051)",
            "cropland_alm_vm0042": "Cropland — ALM (VM0042)",
        }
        # Validated categorical palette (dataviz skill reference), slots 1/2 —
        # blue vs orange clears every CVD/contrast gate in both light and dark.
        _FIELD_TYPE_COLORS = {
            "rice_awd": "#3987e5" if _theme_mode == "dark" else "#2a78d6",
            "cropland_alm_vm0042": "#d95926" if _theme_mode == "dark" else "#eb6834",
        }

        _total_area = sum(p["area_ha"] or 0.0 for p in _portfolio)
        _rice_credits = sum(
            p["final_issuance"] for p in _portfolio
            if p["field_type"] == "rice_awd" and p["final_issuance"] is not None
        )
        _alm_credits = sum(
            p["final_issuance"] for p in _portfolio
            if p["field_type"] == "cropland_alm_vm0042" and p["final_issuance"] is not None
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Registered Fields", len(_portfolio))
        m2.metric("Total Area", f"{_total_area:.2f} ha")
        m3.metric("Rice AWD Credits", f"{_rice_credits:.3f} tCO₂e")
        m4.metric("Cropland ALM Credits", f"{_alm_credits:.3f} tCO₂e")

        _calculated = [p for p in _portfolio if p["final_issuance"] is not None]
        st.markdown("##### Latest Credits by Field")
        if _calculated:
            _fig_portfolio = go.Figure()
            for _ftype in ("rice_awd", "cropland_alm_vm0042"):
                _rows = [p for p in _calculated if p["field_type"] == _ftype]
                if not _rows:
                    continue
                _fig_portfolio.add_trace(go.Bar(
                    x=[p["final_issuance"] for p in _rows],
                    y=[f"{p['field_id']} — {p['name']}" for p in _rows],
                    orientation="h",
                    name=_FIELD_TYPE_LABELS[_ftype],
                    marker=dict(color=_FIELD_TYPE_COLORS[_ftype]),
                ))
            _fig_portfolio.update_layout(
                template="plotly_dark" if _theme_mode == "dark" else "plotly_white",
                xaxis_title="Final Issuance (tCO₂e)",
                height=max(280, 60 * len(_calculated)),
                margin=dict(t=30, l=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            st.plotly_chart(_fig_portfolio, use_container_width=True)
        else:
            st.info(
                "No field has calculated credits yet — this chart populates "
                "once **Calculate Carbon Credits** has run on at least one field."
            )

        st.markdown("##### All Registered Fields")
        _table_rows = [
            {
                "Field ID": p["field_id"],
                "Name": p["name"],
                "District": p["district"],
                "Type": _FIELD_TYPE_LABELS.get(p["field_type"], p["field_type"]),
                "Area (ha)": p["area_ha"],
                "Latest Credits (tCO₂e)": (
                    round(p["final_issuance"], 4) if p["final_issuance"] is not None else "Not calculated"
                ),
                "Last Calculated": p["calculated_at"] or "—",
            }
            for p in _portfolio
        ]
        st.dataframe(pd.DataFrame(_table_rows), use_container_width=True, hide_index=True)

    # -----------------------------------------------------------------
    # Team management — admin-only (Phase 4 of the multi-tenant plan).
    # Replaces CLI-only bootstrapping (scripts/create_user.py) for
    # everything beyond the very first admin per org: once that admin
    # exists and can log in, they invite the rest of their team here.
    # -----------------------------------------------------------------
    if auth_user["role"] == "admin":
        st.markdown("---")
        st.markdown("#### 👥 Team")
        st.caption(f"Everyone with a login in your organization ({org_id}).")

        _team = list_org_users(org_id)
        st.dataframe(
            pd.DataFrame([
                {
                    "Email": u["email"],
                    "Role": u["role"],
                    "Active": "Yes" if u["is_active"] else "No",
                    "Last Login": u["last_login_at"] or "Never",
                    "Created": u["created_at"],
                }
                for u in _team
            ]),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("➕ Invite a teammate"):
            with st.form("invite_form", clear_on_submit=True):
                _inv_email = st.text_input("Email")
                _inv_password = st.text_input(
                    "Temporary password", type="password",
                    help="Share this with them directly — there's no email "
                         "delivery yet. They can't change it in-app either; "
                         "that's a later addition.",
                )
                _inv_role = st.selectbox("Role", options=sorted(VALID_ROLES), index=1)
                _inv_submitted = st.form_submit_button("Create login", use_container_width=True)
            if _inv_submitted:
                if not _inv_email.strip() or not _inv_password:
                    st.error("Email and password are required.")
                else:
                    try:
                        create_org_user(org_id, _inv_email, _inv_password, _inv_role)
                        st.success(f"Created login for {_inv_email.strip().lower()}.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
