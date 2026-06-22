# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

**terra-audit** is a Streamlit dashboard for detecting Alternate Wetting and Drying (AWD) irrigation in rice paddies using Sentinel-1 SAR satellite data from Google Earth Engine, then converting those observations into verifiable carbon credits following the **Verra VM0051 Tier 2 methodology**. The primary geographic focus is Bangladesh/South Asia.

## Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Authenticate Earth Engine (one-time setup per machine)
earthengine authenticate
earthengine set_project <GCP_PROJECT_ID>

# Run the app
streamlit run app.py
# Opens at http://localhost:8501
```

There is no test suite. Validation is done by running the app and exercising the UI manually.

## Environment

Requires a `.env` file in the project root:
```
EE_PROJECT=your-gcp-project-id
```

This project ID must correspond to a Google Cloud project with the Earth Engine API enabled and billing configured.

## Architecture

Three-layer pipeline, each in its own module under `src/`:

**1. Data Layer — `src/data_engine.py` (`SpatialDataEngine`)**
- Queries Google Earth Engine for Sentinel-1 SAR backscatter (VV, VH bands) over a field's GeoJSON geometry
- Filters to DESCENDING orbital pass only (avoids orbit-mixing artefacts in time-series)
- Computes derived indices: `CROSS_RATIO` (VH/VV), `RVI` (Radar Vegetation Index)
- Applies Savitzky-Golay smoothing (window=5, polyorder=2) to reduce SAR speckle noise
- Key method: `extract_clean_timeseries(geojson_geometry, start_date, end_date) → DataFrame`

**2. Inference Layer — `src/threshold_gate.py` (`AdaptiveAWDGate`)**
- Z-score anomaly detection on VV backscatter to flag flooded states (threshold: z < -0.8)
- Detects "drydown events" as sharp positive VV jumps following flooded periods
- Phenology extraction: sowing = global VH minimum; harvest = sharpest post-peak VH drop
- Key methods: `analyze_irrigation_behavior(df)`, `extract_phenology(df)`

**3. Credit Calculation Layer — `src/carbon_calculator.py` (`CarbonAssetEngine`)**
- Implements VM0051 Tier 2: baseline CH₄ (continuous flooding) minus project CH₄ (AWD)
- Water scaling factors: SF = 1.0 (0 drydowns), 0.71 (1 drydown), 0.52 (≥2 drydowns)
- Converts CH₄ savings to tCO₂e using IPCC AR5 GWP₁₀₀ = 28; EF_c = 1.4 kg CH₄/ha/day (South Asia)
- Conservativeness discount: ≥100% confidence → no discount; ≥85% → 30% discount; <85% → 0 issuance
- Key method: `calculate_credits(awd_events, season_length_days, area_ha, ai_accuracy) → dict`

**Caching — `src/database.py`**
- SQLite3 at `data/project_store.db`
- Timeseries records keyed on `(field_id, observation_date, window_start, window_end)` — prevents cross-window collisions
- Cache check happens before every GEE query; misses trigger a live fetch and save
- Two seed fields auto-created on first run: `F-101` (Mymensingh) and `F-102` (Faridpur)

**UI — `app.py`**
- Single-file Streamlit app with three tabs: Spatial Asset Inspection | Signal Analytics | Carbon Asset Ledger
- Sidebar: field selector + crop season presets (Boro/Aman/Pre-Kharif or custom date range)
- Session state carries computed metrics between tabs
- GEE initialization is cached via `@st.cache_resource`

## Database Schema

```sql
CREATE TABLE fields (
    field_id         TEXT PRIMARY KEY,
    name             TEXT,
    district         TEXT,
    geojson_geometry TEXT,   -- Full GeoJSON FeatureCollection string
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE timeseries_cache (
    field_id         TEXT,
    observation_date TEXT,
    window_start     TEXT,
    window_end       TEXT,
    vv               REAL,
    vh               REAL,
    cross_ratio      REAL,
    rvi              REAL,
    PRIMARY KEY (field_id, observation_date, window_start, window_end)
);
```

## Key Design Constraints

- **South Asia constants are hard-coded**: `EF_c = 1.4 kg CH₄/ha/day` from IPCC defaults — do not generalize without updating the emission factor lookup.
- **DESCENDING-only SAR**: intentional; mixing ascending/descending passes corrupts the time-series signal.
- **Phenology detection requires signal quality**: the algorithm needs ≥3 post-sowing observations and a clear VH minimum; it can fail silently on low-observation windows.
- **No field geometry editing in UI**: new fields must be inserted directly into the database.
- **Results are UI-only**: there is no CSV export or API output layer yet.
