# Software Requirements Specification (SRS)

**Project:** Terra-Audit — AI-Assisted Digital MRV Platform for AWD Rice Irrigation Carbon Credits
**Version:** 0.1 (as-built, reflects codebase state on branch `development`)
**Status legend used throughout this document:**

| Tag | Meaning |
|---|---|
| `[Implemented]` | Present and working in the current codebase; file/module cited. |
| `[Partially Implemented]` | Exists but narrower in scope than the requirement text implies. |
| `[Planned]` | Not present in the codebase today; carried here as a target requirement and cross-referenced to §11 Future Enhancements. |

---

## 1. Introduction

### 1.1 Purpose

This document specifies the requirements for **Terra-Audit**, a Streamlit-based
dashboard that detects Alternate Wetting and Drying (AWD) irrigation events in
rice paddies from Sentinel-1 SAR satellite data (via Google Earth Engine), and
converts those observations into estimated carbon credits under the
**Verra VM0051 Tier 2, QA3 (Default Emission Factors)** methodology. It
documents both what is implemented today and what is planned, so the
document can serve as both an as-built record and a forward-looking spec.

### 1.2 Project Scope

Terra-Audit covers, end to end: field boundary registration → satellite
signal extraction and caching → AWD event detection (rule-based and/or
AI-assisted) → VM0051-aligned carbon credit estimation → exportable
audit/evidence packages (PDF, JSON, CSV). It does **not** currently issue or
register credits with any registry — outputs are estimates for internal
review and evidence, downloaded from the browser session.

Geographic focus: Bangladesh / South Asia, driven by hard-coded regional
emission factors (see §12.2).

### 1.3 Objectives

- Replace manual, self-reported AWD irrigation logs with satellite-derived,
  auditable evidence.
- Apply the VM0051 QA3 methodology consistently and transparently, with every
  intermediate calculation exposed for audit.
- Explore whether a learned classifier can reproduce/augment the rule-based
  AWD detector, as a step toward more robust event detection.
- Produce evidence packages self-contained enough for a third-party auditor
  to reconstruct every number in the credit calculation.

### 1.4 Definitions, Acronyms & Abbreviations

| Term | Meaning |
|---|---|
| AWD | Alternate Wetting and Drying — an irrigation regime that periodically dries the paddy instead of continuous flooding |
| SAR | Synthetic Aperture Radar (Sentinel-1 VV/VH backscatter) |
| GEE | Google Earth Engine |
| VV, VH | Radar polarization channels (Vertical-Vertical, Vertical-Horizontal) |
| RVI | Radar Vegetation Index, derived from VV/VH |
| MRV | Measurement, Reporting, and Verification |
| VM0051 | Verra methodology for GHG emission reductions from rice cultivation via improved water management |
| SF_w | Water scaling factor (IPCC 2019 Refinement, Table 5.12) applied to baseline CH₄ emissions |
| GWP | Global Warming Potential |
| QA3 | VM0051's "Default Emission Factors" quantification approach (as opposed to site-measured factors) |
| tCO₂e | Tonnes of CO₂-equivalent |
| EF_c | CH₄ emission factor per hectare per day |

### 1.5 References

- Verra, *VM0051 v1.0 — Methodology for Improved Agricultural Land Management*, 27 Feb 2025 — checked into this repo at `docs/VM0051v1_27Feb25.pdf`.
- IPCC, *2019 Refinement to the 2006 IPCC Guidelines for National Greenhouse Gas Inventories*, Volume 4, Chapter 5, Table 5.12 (water regime scaling factors) and Chapter 11, Table 11.1 (N₂O correction factors).
- IPCC AR5, *Global Warming Potential values* (CH₄ = 28, N₂O = 265, 100-year horizon) — used directly in `src/carbon_calculator.py`.
- Copernicus / ESA, *Sentinel-1 Mission and SAR User Guide*.
- Google Earth Engine API documentation (`earthengine-api`).

### 1.6 Document Overview

§2 describes the product at a high level; §3 lists functional requirements
by subsystem; §4–§7 describe interfaces, architecture, database, and
methodology; §8–§9 cover non-functional requirements and validation; §10–§12
cover limitations, future work, and appendices.

---

## 2. Overall Description

### 2.1 Product Perspective

Terra-Audit is a standalone, single-process analytical tool — one Streamlit
application (`app.py`) that calls out to Google Earth Engine for satellite
data and reads/writes a local SQLite file for caching. It is **not** part of
a larger system today; it has no upstream/downstream integrations besides
GEE. `[Implemented — current architecture]`. A multi-service architecture
(separate API backend, hosted database, multi-tenant frontend) is
`[Planned]` — see §11.

### 2.2 Product Vision

To be a low-cost, satellite-only MRV layer that lets smallholder rice
farming programs in South Asia generate auditor-ready AWD carbon credit
evidence without on-the-ground water-level loggers, while being explicit
about where the pipeline's outputs are estimates versus verified fact
(notably: AI-based detection is currently validated only against the
rule-based detector, not independent ground truth — see §3.6 and §10).

### 2.3 Product Functions

At a high level, the product: registers field geometries; pulls and caches
Sentinel-1 time series over each field; detects flooded/dry states and AWD
drydown events either via a fixed statistical threshold gate or a trained
classifier; derives sowing/harvest phenology; computes VM0051-aligned CH₄
and N₂O-adjusted carbon credits; and exports a three-file evidence package
per field/season.

### 2.4 User Classes

| Class | Status | Notes |
|---|---|---|
| Administrator | `[Partially Implemented]` | No auth/role system exists; whoever runs the Streamlit process has full access to all functions. The "administrator" role is implicit, not enforced. |
| Carbon Project Developer | `[Implemented]` | The primary user today — registers fields, runs signal analytics, generates credit estimates and evidence packages, all through the same UI. |
| Researcher | `[Partially Implemented]` | The AI Validation tab (`app.py`, tab_validation) supports this use case — training/inspecting Random Forest and XGBoost baselines — but there's no separate research-only view or dataset export beyond what the main app exposes. |
| Auditor (external, read-only) | `[Planned]` | No dedicated auditor login or portal. Today, "auditing" happens by handing an auditor the downloaded PDF/JSON/CSV evidence package out-of-band. |

### 2.5 Operating Environment

Runs locally (or on a single host) as a Python 3 process: `streamlit run
app.py`, listening on `localhost:8501`. Requires network access to Google
Earth Engine (authenticated via `earthengine authenticate` and a `.env`
`EE_PROJECT` variable) and local disk access for the SQLite cache
(`data/project_store.db`) and AI model artifacts (`data/ai_models/`).
`[Implemented]`. No containerization or cloud deployment target is defined
in-repo today; cloud deployment is `[Planned]` (§11).

### 2.6 Assumptions & Constraints

- Assumes the target field's SAR history has enough DESCENDING-pass
  Sentinel-1 coverage over the monitoring window; ASCENDING passes are
  intentionally excluded to avoid orbit-mixing artefacts (`src/data_engine.py`).
- Assumes South Asian rice cultivation conditions (EF_c = 1.4 kg CH₄/ha/day)
  — not generalized to other regions or crops without code changes.
- Assumes a single operator/session model; there is no concurrency control
  beyond SQLite's own file-level locking.
- AI baseline models are constrained by label provenance: they are trained
  to reproduce the threshold gate's own decisions (see §3.6), not
  independently verified irrigation events.

---

## 3. Functional Requirements

### FR-1 Project Management `[Planned]`

The current system has no separate "Project" entity — work is organized
directly around individually registered **Fields** (§FR-2). A `Projects`
table/concept that groups multiple fields, tracks a project lifecycle, or
supports a project-level dashboard does not exist in `src/database.py` or
`app.py`. This FR is retained as a target requirement for a future
multi-field/multi-client rollout (§11).

- Create Project — `[Planned]`
- Manage Projects — `[Planned]`
- Project Dashboard — `[Planned]`

### FR-2 Field Management

- GeoJSON/KML Upload — `[Implemented]` (`src/geo_utils.py`: `parse_geojson_upload()`, `parse_kml_upload()`)
- Paste GPS Coordinates — `[Implemented]` (`src/geo_utils.py`: `parse_coordinate_text()`, newline-separated `lat, lon` pairs)
- Draw on Map — `[Implemented]` (Leaflet Draw polygon/rectangle tool in the Spatial Asset Inspection tab, `app.py`)
- Automatic Area Calculation — `[Implemented]` (`src/geo_utils.py`: `compute_area_ha()`, Shoelace formula with spherical latitude correction)
- Field Validation — `[Implemented]` (all three parsers return `(None, error_message)` on malformed input instead of raising, surfaced directly in the UI)
- Field Database — `[Implemented]` (SQLite `fields` table, `src/database.py`)

### FR-3 Satellite Data Engine

- Google Earth Engine Connection — `[Implemented]` (`app.py`, `@st.cache_resource`-wrapped EE init)
- Sentinel-1 Retrieval — `[Implemented]` (`src/data_engine.py`, `SpatialDataEngine`, DESCENDING-pass-only VV/VH backscatter)
- Time-Series Generation — `[Implemented]` (`extract_clean_timeseries(geojson_geometry, start_date, end_date)`)
- Data Caching — `[Implemented]` (SQLite `timeseries_cache` table, keyed on `(field_id, observation_date, window_start, window_end)`; cache checked before every live GEE query)

### FR-4 Feature Engineering

- VV Extraction — `[Implemented]` (`src/data_engine.py`)
- VH Extraction — `[Implemented]` (`src/data_engine.py`)
- Ratio Calculation (Cross Ratio, VH−VV) — `[Implemented]`
- RVI Calculation — `[Implemented]` (Radar Vegetation Index)
- Temporal Processing — `[Implemented]` (Savitzky-Golay smoothing, window=5, polyorder=2; falls back to raw values under 5 observations)

### FR-5 MRV Processing Engine (Rule-Based)

- Threshold AWD Detection — `[Implemented]` (`src/threshold_gate.py`, `AdaptiveAWDGate`; Z-score anomaly detection on VV, threshold z < −0.8 for flooded state)
- Dry Cycle Identification — `[Implemented]` (drydown = sharp positive VV jump > 1.2σ immediately following a flooded state)
- Phenology (Sowing/Harvest) Detection — `[Implemented]` (`extract_phenology(df)`: sowing = global VH minimum, harvest = sharpest post-peak VH drop; requires ≥3 post-sowing observations, fails silently to a 120-day fallback season length with a UI warning on low-observation windows)
- Confidence Score (rule-based) — `[Partially Implemented]` — the threshold gate produces deterministic flags, not a probabilistic confidence value; confidence scoring in the probabilistic sense exists only on the AI path (FR-6).
- Event Detection — `[Implemented]` (AWD drydown event count feeds directly into §FR-7)

### FR-6 AI Engine

- Dataset Builder — `[Implemented]` (`src/ai/dataset_builder.py` — builds a labeled dataset from the threshold gate's own output, persisted to an `ai_dataset_rows` SQLite table)
- Feature Engineering (AI-specific) — `[Implemented]` (`src/ai/feature_engineering.py`, `build_features()`, `encode_labels()`)
- Random Forest — `[Implemented]` (`src/ai/train_random_forest.py`, `src/ai/models.py` — `RandomForestClassifier`, `n_estimators=200`, `class_weight="balanced"`)
- XGBoost — `[Implemented]` (`src/ai/train_xgboost.py`, `src/ai/models.py` — `XGBClassifier`, `n_estimators=200`, `max_depth=4`, lazily imported so the app doesn't hard-fail without `xgboost` installed)
- Model Selection — `[Implemented]` (UI dropdown in `app.py` — "Random Forest (AI baseline)" / "XGBoost (AI baseline)" — feeding `src/ai/predictor.py`)
- AI Prediction — `[Implemented]` (`src/ai/predictor.py`, `predict_awd_states()` — overwrites `is_flooded`/`drydown_event` with model output, adds `predicted_label`/`confidence` columns; raises `FileNotFoundError` if the selected model hasn't been trained, with the app expected to fall back to the threshold gate)
- AI Confidence — `[Partially Implemented]` — per-prediction confidence values are produced, but as documented directly in the code (`src/ai/dataset_builder.py`, `src/ai/evaluate.py`), **there is no independently verified AWD ground truth anywhere in this project**. Training labels are synthesized from `AdaptiveAWDGate`'s own z-score/diff threshold output, so both the trained models and their evaluation metrics measure *model-vs-threshold-gate agreement*, not accuracy against real-world irrigation truth. This is a foundational scope limitation, not a rounding caveat — carried forward to §10.

### FR-7 Carbon Estimation Engine

All items `[Implemented]` in `src/carbon_calculator.py` (`CarbonAssetEngine`), following VM0051 v1.0 QA3:

- VM0051 Calculation — full QA3 default-emission-factors pathway (`calculate_credits()`)
- IPCC Factors — Water scaling factors per IPCC 2019 Refinement Table 5.12: SF = 1.00 (0 drydowns), 0.71 (1 drydown), 0.52 (≥2 drydowns); N₂O correction factor CF_N2O = 0.00314 (IPCC 2019 Table 11.1, via VM0051 footnote 21)
- Methane Reduction — baseline vs. project CH₄ from soil methanogenesis (§8.2.3, Eqs. 6–8): `E_baseline = EF_c × 1.0 × season_days × area_ha`, `E_project = EF_c × SF_w × season_days × area_ha`
- CO₂e Estimation — CH₄ savings converted via IPCC AR5 GWP₁₀₀ = 28; N₂O project emission penalty (§8.3.2, Eq. 25): `PE_Red-Irri = Q_N × area_ha × CF_N2O × 1e-3 × GWP_N2O` (GWP_N2O = 265, AR5), applied only when `awd_events > 0`
- Carbon Credit Estimation — QA3 flat 15% uncertainty deduction (§8.6.3, for projects <60,000 tCO₂e/yr); leakage de-minimis screen (§8.4, N₂O penalty as % of gross CH₄ reduction, flagged de minimis below 5%, informational only — not currently subtracted separately); final issuance (Eq. 29, CH₄ soil term only) = CH₄ after uncertainty deduction − N₂O penalty, floored at 0

Explicitly out of scope / assumed de minimis per §8.4 of the methodology
(not modeled): CO₂ from fossil fuels/liming, biomass burning CH₄/N₂O,
baseline fertilizer N₂O, leakage from organic amendments/yield decline.

### FR-8 Audit & Evidence Engine

- Calculation Trace — `[Implemented]` — `generate_audit_json()` in `src/report_generator.py` embeds every calculation input and intermediate value returned by `CarbonAssetEngine.calculate_credits()`, plus the full timeseries.
- Satellite Evidence — `[Implemented]` — the raw timeseries (VV/VH/CROSS_RATIO/RVI per observation date) is embedded in both the JSON audit record and exported separately as CSV (`generate_timeseries_csv()`).
- Audit Package — `[Implemented]` — the combination of PDF + JSON + CSV constitutes the exportable evidence package, assembled from `export_*` Streamlit session-state keys written by the Signal Analytics tab.
- Evidence Timeline (dedicated UI view) — `[Planned]` — there is no interactive timeline widget separate from the time-series chart in the Signal Analytics tab.
- Event Log (persisted, queryable) — `[Planned]` — AWD/phenology events are computed per-run and surfaced in the UI/exports, but are not persisted to a queryable event-log table.

### FR-9 Reporting Module

- PDF Report — `[Implemented]` (`generate_pdf()`, `src/report_generator.py`, A4 via `fpdf2`; 8 sections: field info, monitoring period, satellite data, AWD events, carbon estimation, methodology, assumptions, limitations; `_s()` helper sanitizes Unicode to Latin-1 for core-font compatibility)
- JSON Export — `[Implemented]` (`generate_audit_json()`)
- CSV Export — `[Implemented]` (`generate_timeseries_csv()`)
- Summary Report (standalone, outside the 3 export files) — `[Planned]` — no additional summary format exists beyond the PDF's own summary sections.
- Server-side persistence / API delivery of reports — `[Planned]` — exports are download-only via `st.download_button`; there is no server-side storage or report API.

### FR-10 Visualization Dashboard

Implemented as four Streamlit tabs in `app.py`:

- Interactive Map — `[Implemented]` ("🌍 Spatial Asset Inspection" tab — Leaflet/folium map via `st_folium`, draw tools, field registration)
- Time-Series Charts — `[Implemented]` ("📈 Statistical Signal Analytics" tab — VV/VH/RVI/Cross Ratio plots, AWD event markers)
- Carbon Dashboard — `[Implemented]` ("💰 Carbon Asset Ledger" tab — credit calculation inputs/outputs, evidence package export)
- AI Dashboard — `[Implemented]` ("🤖 AI Validation" tab — model selection, per-class precision/recall/F1 metrics, confusion matrix, agreement rate against the threshold gate)
- Validation Dashboard (as a distinct concept from the AI tab) — `[Partially Implemented]` — the AI Validation tab covers AI-model validation; there is no separate dashboard for validating the rule-based threshold gate itself against any external source.

---

## 4. External Interface Requirements

### 4.1 User Interface

Single-page Streamlit web UI (`app.py`) with a sidebar (field selector /
registration form) and four main tabs (§FR-10). `[Implemented]`. No mobile
or native client exists or is planned.

### 4.2 Software Interfaces

| Interface | Status | Notes |
|---|---|---|
| Google Earth Engine (`earthengine-api`) | `[Implemented]` | Sole satellite data source; auth via `earthengine authenticate` + `.env` `EE_PROJECT`. |
| SQLite (`data/project_store.db`) | `[Implemented]` | Current persistence layer — file-based, single-writer assumptions. **Not** PostgreSQL. |
| PostgreSQL | `[Planned]` | Would replace SQLite for multi-user/concurrent-write scenarios (§11). |
| Streamlit | `[Implemented]` | Full UI framework — no separate frontend/backend split. |
| REST/GraphQL API | `[Planned]` | No API layer exists; all interaction is through the Streamlit UI (§FR-9's "no server-side persistence" note applies here too). |

### 4.3 Hardware Interface

None beyond a standard workstation/server capable of running Python 3 and a
web browser; no specialized hardware (e.g., IoT soil sensors) is integrated.

### 4.4 Communication Interface

Outbound HTTPS to Google Earth Engine's API endpoints. No inbound network
interface beyond the local Streamlit HTTP server (`localhost:8501`).

---

## 5. System Architecture

### 5.1 Overall Architecture

Terra-Audit is a monolithic, single-process pipeline with four logical
layers, all `[Implemented]`:

```
 ┌────────────────────┐
 │   UI Layer          │  app.py (Streamlit, 4 tabs)
 └─────────┬───────────┘
           │
 ┌─────────▼───────────┐     ┌───────────────────────┐
 │  Data Layer          │────▶│  Cache (SQLite)        │
 │  src/data_engine.py   │     │  src/database.py       │
 └─────────┬───────────┘     └───────────────────────┘
           │ clean timeseries (VV, VH, CROSS_RATIO, RVI)
           │
 ┌─────────▼───────────┐     ┌───────────────────────┐
 │  Inference Layer      │◀──▶│  AI Layer (optional)    │
 │  src/threshold_gate.py│     │  src/ai/*               │
 └─────────┬───────────┘     └───────────────────────┘
           │ AWD events, phenology
           │
 ┌─────────▼───────────┐
 │  Credit Calc Layer    │  src/carbon_calculator.py
 └─────────┬───────────┘
           │
 ┌─────────▼───────────┐
 │  Reporting Layer       │  src/report_generator.py
 └────────────────────┘
```

### 5.2 Frontend Layer

`app.py` — Streamlit UI, tab-based navigation, session-state driven
handoff between tabs (`carbon_*` and `export_*` keys). `[Implemented]`.

### 5.3 Backend Layer

There is no separate backend service — `app.py` calls into `src/*` modules
directly, in-process. A dedicated backend (e.g., FastAPI) is `[Planned]`
(§11), intended to eventually decouple computation from the UI for
multi-user or API-driven use.

### 5.4 Database Layer

SQLite, `src/database.py`. `[Implemented]` — see §6 for schema.

### 5.5 AI Layer

`src/ai/*`. `[Implemented]` as a parallel, opt-in inference path selectable
per-run in the Signal Analytics tab, with the important caveat documented in
§FR-6/§10 regarding label provenance.

### 5.6 MRV Layer

`src/threshold_gate.py` (rule-based) plus `src/ai/predictor.py`
(model-based) — both produce the same `is_flooded`/`drydown_event`
interface consumed downstream, so the credit calculation layer is agnostic
to which detector ran. `[Implemented]`.

### 5.7 Reporting Layer

`src/report_generator.py`. `[Implemented]` — see §FR-9.

---

## 6. Database Design

### 6.1 ER Diagram (textual)

```
fields (1) ──< timeseries_cache (many, keyed by field_id + date + window)
fields (1) ──< ai_dataset_rows (many, keyed by field_id + date + window)
ai_dataset_rows ──> [trained model artifacts on disk, data/ai_models/]
```

No foreign-key relationship exists to a `projects` table (none exists) or
to a persisted `carbon_results` / `audit_logs` table (none exist — audit
records are generated on demand, not stored).

### 6.2 Database Tables

**`fields`** — `[Implemented]`
```sql
CREATE TABLE fields (
    field_id         TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    district         TEXT NOT NULL,
    geojson_geometry TEXT NOT NULL,
    area_ha          REAL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**`timeseries_cache`** — `[Implemented]`
```sql
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

**`ai_dataset_rows`** — `[Implemented]` (`src/ai/dataset_builder.py`) —
stores the labeled feature rows used to train the AI baselines: field/window
identifiers, raw and smoothed VV/VH, cross ratio, RVI, z-score/diff derived
features, threshold-gate-derived labels (`is_flooded`, `drydown_event`,
`is_sowing`, `is_harvest`), and a `label`/`built_at` provenance column.

**AI model artifacts** — `[Implemented]` — persisted as files under
`data/ai_models/` via `joblib` (not a database table).

**`Projects`, `Satellite Data` (as a separate normalized table), `Features`
(as a separate table), `AI Models` (as a DB table rather than files),
`Carbon Results`, `Audit Logs`** — all `[Planned]`. None of these exist as
database tables today; see §11.

---

## 7. Methodology

### 7.1 Complete Workflow (as implemented)

```
Register field (draw/upload/paste)
        │
        ▼
compute_area_ha() → store in `fields`
        │
        ▼
Select monitoring window → check `timeseries_cache`
        │            │
        │ hit        │ miss
        ▼            ▼
  use cached    query GEE (Sentinel-1, DESCENDING only)
   rows              │
        │            ▼
        │      cache new rows
        │            │
        └─────┬──────┘
              ▼
   Savitzky-Golay smoothing (or raw if <5 obs)
              │
              ▼
   ┌─────────────────────┐
   │ choose detector       │
   └────┬─────────────┬──┘
        ▼             ▼
  Threshold Gate   AI Model (RF/XGBoost)
  (z-score, diff)  (predict_awd_states)
        └─────┬───────┘
              ▼
   AWD event count + phenology (sowing/harvest)
              │
              ▼
   CarbonAssetEngine.calculate_credits()
   (VM0051 QA3: CH4, N2O, uncertainty, leakage)
              │
              ▼
   Export: PDF + JSON + CSV (download-only)
```

### 7.2–7.6

Covered by the diagram above and by §5 (Architecture) and §FR-3–FR-9;
not duplicated here to avoid drift between multiple descriptions of the
same pipeline.

---

## 8. Non-Functional Requirements

**Performance** — `[Partially Implemented]`. SQLite caching avoids
redundant GEE calls for previously-fetched windows, which materially
reduces latency on repeat views. No performance SLA or load testing exists.

**Reliability** — `[Partially Implemented]`. Parsers fail soft (return
errors, don't raise) for user input (§FR-2). Phenology detection has a
documented silent-failure mode (falls back to a 120-day season with a UI
warning) rather than crashing. AI prediction raises `FileNotFoundError` for
an untrained model, which the app is expected to catch and fall back to the
threshold gate. There is, however, no automated resilience testing.

**Scalability** — `[Planned]` beyond current state. SQLite is file-based
and assumes low concurrency; multi-user concurrent writes are not supported
today. Moving to PostgreSQL and a decoupled backend (§11) would be required
for real horizontal scale.

**Availability** — `[Partially Implemented]`. Single-process availability
only — no redundancy, no health checks, no restart policy defined in-repo.

**Security** — `[Planned]`. No authentication, authorization, or
role-based access control exists. Anyone with network access to the
Streamlit port has full read/write access to all fields and exports. This
is an explicit current gap, not an oversight to be understated.

**Maintainability** — `[Implemented]` as a design property. The codebase is
modularized by concern (`data_engine`, `threshold_gate`, `carbon_calculator`,
`report_generator`, `geo_utils`, `database`, `ai/*`), each independently
testable in principle, and the CH₄/N₂O formulae are pinned to specific
VM0051 sections in code comments for traceability.

**Portability** — `[Implemented]`. Pure Python + SQLite, no OS-specific
dependencies beyond what `earthengine-api` and `fpdf2` require; runs
anywhere Python 3 and a browser are available.

**Usability** — `[Implemented]` — single-page tabbed UI, in-line error
messages on bad input, session-state auto-population of Carbon tab inputs
from Signal Analytics results.

---

## 9. Validation & Testing

**Functional Testing** — `[Planned]` as an automated suite. There is
currently **no automated test suite**; validation is performed by running
the app and exercising the UI manually (per project convention).

**AI Model Evaluation** — `[Implemented]`, with the scope caveat repeated
from §FR-6: `src/ai/evaluate.py` computes precision/recall/F1/confusion
matrix from pooled out-of-fold cross-validation predictions, explicitly
named as *agreement with the threshold gate*, not accuracy against
independently verified ground truth. `src/ai/models.py` handles small/
imbalanced classes (e.g., a single-sample "drydown" class) by falling back
from `StratifiedKFold` to plain `KFold` with a warning, rather than
crashing or silently dropping the class.

**Carbon Calculation Validation** — `[Partially Implemented]` — the
formulae are directly traceable to VM0051 section/equation numbers in code
comments (§FR-7), which supports manual/expert review, but there is no
automated regression test asserting expected outputs for known inputs.

**Integration Testing** — `[Planned]`.

**User Acceptance Testing** — `[Planned]` (informal, ad hoc via manual UI walkthroughs today).

---

## 10. Limitations

- **Rice AWD only** — no other crop or irrigation regime is modeled.
- **VM0051-aligned estimation, not certification** — outputs are estimates
  for evidence/review, not registry-issued credits.
- **Satellite-based technical verification only** — no ground-truth soil
  moisture or water-level sensor integration exists or is required by the
  current pipeline.
- **AI-based detection is validated against the rule-based detector, not
  independent ground truth.** This is the most important limitation to
  state plainly: because `AdaptiveAWDGate`'s own output is the label source
  for AI training (`src/ai/dataset_builder.py`), any AI Validation tab
  metric (precision, recall, F1, confidence) measures how closely a model
  reproduces the threshold gate's decisions — it cannot, by construction,
  demonstrate that either detector matches real-world irrigation behavior.
- **Carbon credits are estimated, not officially issued** — no registry
  integration exists.
- **South Asia constants are hard-coded** (EF_c = 1.4 kg CH₄/ha/day); not
  valid for other regions without an emission-factor lookup change.
- **No automated test suite** — correctness relies on manual UI validation
  and code-level traceability to methodology sections, not regression tests.
- **No multi-user support or access control** — single implicit operator.

---

## 11. Future Enhancements

Items below are **not implemented** and are the natural home for the
template's aspirational scope (Projects, PostgreSQL, FastAPI, multi-user):

- Multi-field **Project** entity with its own lifecycle and dashboard (§FR-1)
- Migration from SQLite to **PostgreSQL** for concurrent multi-user access
- Dedicated **FastAPI** backend, decoupling computation from the Streamlit UI and enabling a REST API
- **Multi-user support** with authentication, roles (Administrator / Developer / Researcher / Auditor as genuinely distinct accounts), and access control
- Independent ground-truth validation for AI models (e.g., field-verified water-level logger data) so AI metrics measure real accuracy, not gate-agreement
- BiLSTM / Temporal Convolutional Network (TCN) models as an alternative to Random Forest/XGBoost
- Explainable AI (e.g., SHAP) for per-prediction feature attribution
- Multi-methodology framework (beyond VM0051) and additional carbon standards
- Multi-crop support beyond rice AWD
- Cloud deployment (containerization, managed hosting)
- Persisted, queryable event log and evidence timeline (§FR-8)
- Server-side report storage / delivery API (§FR-9)

---

## 12. Appendices

### 12.1 Acronyms

See §1.4.

### 12.2 Key Formulae (from `src/carbon_calculator.py`)

- Baseline CH₄: `E_baseline = EF_c × 1.0 × season_days × area_ha`
- Project CH₄: `E_project = EF_c × SF_w × season_days × area_ha`
- Gross CH₄ avoided: `ΔE_CH4 = E_baseline − E_project`
- CO₂e conversion: `ΔE_CO2e = (ΔE_CH4 × GWP_CH4) / 1000`, GWP_CH4 = 28 (AR5)
- QA3 uncertainty deduction: `UNC = ΔE_CO2e × 0.15`
- N₂O irrigation penalty (Eq. 25, only if `awd_events > 0`):
  `PE_Red-Irri = Q_N × area_ha × CF_N2O × 1e-3 × GWP_N2O`, CF_N2O = 0.00314, GWP_N2O = 265 (AR5)
- Leakage %: `pe_n2o / ΔE_CO2e × 100`, de minimis if `< 5%`
- Final issuance (Eq. 29, CH₄ soil term only): `max(0, (ΔE_CO2e − UNC) − PE_Red-Irri)`
- Water scaling factor `SF_w`: 1.00 (0 drydowns) / 0.71 (1 drydown) / 0.52 (≥2 drydowns)

### 12.3 Technology Stack (from `requirements.txt`)

streamlit, pandas, numpy, plotly, folium, streamlit-folium, scikit-learn,
xgboost, joblib, earthengine-api, shapely, scipy, python-dotenv, fpdf2.

### 12.4 Glossary

See §1.4 for domain-specific terms.
