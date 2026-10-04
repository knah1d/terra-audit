import json
import os
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from src.paths import DATA_DIR

import pandas as pd
from sqlalchemy import create_engine, text

from src.persistence.schema import _init_sqlite, _init_postgres
from src.carbon.issuance import NonIssuableResultError, result_is_issuable

DB_PATH = DATA_DIR / "project_store.db"
_DB_INITIALIZED = False
_ENGINE = None
_READ_CONNECTION = ContextVar("terra_read_connection", default=None)


def _get_engine():
    """Lazily creates the module-level SQLAlchemy engine. DATABASE_URL unset
    (the default) targets the local SQLite file, exactly as before Phase 5
    of the multi-tenant plan (.claude/plans/misty-growing-yao.md) — set it
    to a postgresql://... URL to target Postgres instead. One engine per
    process, reused across every get_db_connection() call (SQLAlchemy pools
    connections internally; this is not "one new connection per call" the
    way the pre-Phase-5 sqlite3.connect() code was)."""
    global _ENGINE
    if _ENGINE is None:
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            _ENGINE = create_engine(database_url)
        else:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _ENGINE = create_engine(f"sqlite:///{DB_PATH}")
    return _ENGINE


def is_sqlite() -> bool:
    return _get_engine().dialect.name == "sqlite"


@contextmanager
def get_db_connection():
    """Context manager: opens a connection, yields it, then always closes it.
    Callers use conn.execute(text(...), {...}) with named params and
    conn.commit() exactly as before — SQLAlchemy's Connection supports both
    natively. Read paths that need dict-style row["col"] access should call
    .mappings() on the result (see every function below for the pattern)."""
    shared = _READ_CONNECTION.get()
    if shared is not None:
        yield shared
        return
    conn = _get_engine().connect()
    if is_sqlite():
        # WAL lets readers proceed while a writer holds the file, and the
        # busy timeout gives a second writer a chance to retry instead of
        # raising "database is locked" immediately — both matter once more
        # than one tenant's session can write concurrently. Meaningless on
        # Postgres, which has real MVCC instead.
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA busy_timeout=5000"))
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def read_connection_scope():
    """Reuse one connection for a synchronous, read-only operation.

    No result cache: repeated SELECTs still read current committed data, so
    end-of-packet fingerprint checks can detect changes. ContextVars isolate
    requests; heartbeat threads keep their independent write connections.
    """
    if _READ_CONNECTION.get() is not None:
        yield
        return
    with get_db_connection() as conn:
        sqlite = is_sqlite()
        if sqlite:
            prior = conn.execute(text("PRAGMA query_only")).scalar()
            conn.execute(text("PRAGMA query_only=ON"))
        else:
            # Apply before the first query. READ COMMITTED keeps each SELECT
            # fresh instead of hiding concurrent evidence changes in a snapshot.
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY"))
        token = _READ_CONNECTION.set(conn)
        try:
            yield
        finally:
            _READ_CONNECTION.reset(token)
            conn.rollback()
            if sqlite:
                conn.execute(text(f"PRAGMA query_only={int(prior)}"))
                conn.rollback()


def initialize_database():
    """Idempotently creates all tables and applies schema migrations.
    Branches on backend: SQLite replays its full ALTER-TABLE migration
    history (so an existing local dev DB keeps working unchanged), while
    Postgres gets the final-shape schema created fresh in one pass — a new
    Postgres deployment has no legacy rows to accommodate, since it's
    populated via scripts/migrate_sqlite_to_postgres.py, not by replaying
    SQLite's migration history against a different engine."""
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    with get_db_connection() as conn:
        if is_sqlite():
            _init_sqlite(conn)
        else:
            _init_postgres(conn)
        from src.evidence.monitoring import initialize_tables
        initialize_tables(conn)
        from src.projects.repository import initialize_tables as initialize_project_tables
        initialize_project_tables(conn)
        from src.carbon.calculations import initialize_tables as initialize_calculation_tables
        initialize_calculation_tables(conn)
        from src.projects.reviews import initialize_tables as initialize_review_tables
        initialize_review_tables(conn)
        from src.jobs.queue import initialize_tables as initialize_job_tables
        initialize_job_tables(conn)
        from src.evidence.operations import initialize_tables as initialize_monitoring_ops_tables
        initialize_monitoring_ops_tables(conn)
        from src.methodology.registry import initialize_tables as initialize_methodology_registry
        initialize_methodology_registry(conn)
        from src.methodology.quantification import initialize_tables as initialize_quantification_tables
        initialize_quantification_tables(conn)
        from src.evidence.soil import initialize_tables as initialize_soil_evidence_tables
        initialize_soil_evidence_tables(conn)
        from src.evidence.production import initialize_tables as initialize_production_records_tables
        initialize_production_records_tables(conn)
        from src.methodology.library import initialize_tables as initialize_methodology_library_tables
        initialize_methodology_library_tables(conn)
        from src.ai.workspace import initialize_tables as initialize_ai_tables
        initialize_ai_tables(conn)
        from src.accounts.account_access import initialize_tables as initialize_account_tables
        initialize_account_tables(conn)
        conn.execute(text("""CREATE TABLE IF NOT EXISTS timeseries_cache_versions (
            org_id TEXT NOT NULL, field_id TEXT NOT NULL, window_start TEXT NOT NULL,
            window_end TEXT NOT NULL, processing_version TEXT NOT NULL,
            PRIMARY KEY (org_id, field_id, window_start, window_end))"""))
        conn.commit()
    _DB_INITIALIZED = True


def update_field_info(org_id: str, field_id: str, name: str, district: str):
    """Updates a field's name/district in place. field_type and geometry are
    deliberately not editable here — changing methodology path or redrawing
    a boundary means the field's underlying data (SAR cache vs. practice/SOC
    rows) no longer matches, so those still require delete + re-register."""
    with get_db_connection() as conn:
        conn.execute(
            text("UPDATE fields SET name = :name, district = :district "
                 "WHERE org_id = :org_id AND field_id = :field_id"),
            {"name": name, "district": district, "org_id": org_id, "field_id": field_id},
        )
        conn.commit()


def check_cache(org_id: str, field_id: str, window_start: str, window_end: str) -> pd.DataFrame:
    """
    Retrieves cached time-series records keyed to a specific org+field AND
    analysis window. Returns an empty DataFrame on a cache miss.
    """
    from src.signals.processing import PROCESSING_VERSION
    with get_db_connection() as conn:
        df = pd.read_sql_query(
            text("""
                SELECT c.observation_date AS date, c.vv, c.vh, c.cross_ratio, c.rvi
                FROM timeseries_cache c
                JOIN timeseries_cache_versions v
                  ON v.org_id=c.org_id AND v.field_id=c.field_id
                 AND v.window_start=c.window_start AND v.window_end=c.window_end
                WHERE c.org_id=:org_id AND c.field_id=:field_id
                  AND c.window_start=:window_start AND c.window_end=:window_end
                  AND v.processing_version=:processing_version
                ORDER BY c.observation_date ASC
            """),
            conn,
            params={"org_id": org_id, "field_id": field_id,
                    "window_start": window_start, "window_end": window_end,
                    "processing_version": PROCESSING_VERSION},
        )
    return df


def save_cache(
    org_id: str, field_id: str, df: pd.DataFrame, window_start: str, window_end: str
):
    """Atomically replace a window and return the raw values committed.

    Returning the same ordered, raw columns as check_cache avoids a read-back
    round trip. Derived/smoothed columns are deliberately not returned.
    """
    if df.empty:
        return pd.DataFrame(columns=["date", "vv", "vh", "cross_ratio", "rvi"])
    from src.signals.processing import PROCESSING_VERSION
    stored = df[["date", "vv", "vh", "cross_ratio", "rvi"]].copy()
    stored["date"] = stored["date"].astype(str)
    for column in ("vv", "vh", "cross_ratio", "rvi"):
        stored[column] = stored[column].astype(float)
    stored = stored.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    with get_db_connection() as conn:
        params = dict(org_id=org_id, field_id=field_id, window_start=window_start, window_end=window_end,
                      processing_version=PROCESSING_VERSION)
        # Lock/upsert the window version before replacing its rows so two
        # writers of the same window cannot interleave their replacements.
        conn.execute(text("INSERT INTO timeseries_cache_versions "
                          "(org_id,field_id,window_start,window_end,processing_version) VALUES "
                          "(:org_id,:field_id,:window_start,:window_end,:processing_version) "
                          "ON CONFLICT (org_id,field_id,window_start,window_end) DO UPDATE SET "
                          "processing_version=excluded.processing_version"), params)
        # Replace the entire window: refreshed queries may return fewer scenes.
        conn.execute(text("DELETE FROM timeseries_cache WHERE org_id=:org_id AND field_id=:field_id "
                          "AND window_start=:window_start AND window_end=:window_end"), params)
        rows = [
            {
                "org_id": org_id,
                "field_id": field_id,
                "observation_date": row["date"],
                "window_start": window_start,
                "window_end": window_end,
                "vv": row["vv"],
                "vh": row["vh"],
                "cross_ratio": row["cross_ratio"],
                "rvi": row["rvi"],
            }
            for row in stored.to_dict(orient="records")
        ]
        insert_stmt = (
            "INSERT OR REPLACE INTO timeseries_cache" if is_sqlite()
            else "INSERT INTO timeseries_cache"
        )
        conflict_clause = "" if is_sqlite() else (
            " ON CONFLICT (org_id, field_id, observation_date, window_start, window_end) "
            "DO UPDATE SET vv=excluded.vv, vh=excluded.vh, "
            "cross_ratio=excluded.cross_ratio, rvi=excluded.rvi"
        )
        columns = ("org_id", "field_id", "observation_date", "window_start", "window_end",
                   "vv", "vh", "cross_ratio", "rvi")
        # SQLAlchemy text executemany may send one INSERT per observation on
        # Postgres. Explicit multi-row VALUES takes one round trip per batch.
        # 100 * 9 binds also fits SQLite's older 999-variable limit.
        for offset in range(0, len(rows), 100):
            batch = rows[offset:offset + 100]
            values = ", ".join("(" + ", ".join(f":{column}_{i}" for column in columns) + ")"
                               for i in range(len(batch)))
            bindings = {f"{column}_{i}": row[column] for i, row in enumerate(batch) for column in columns}
            conn.execute(text(f"{insert_stmt} ({', '.join(columns)}) VALUES {values}{conflict_clause}"), bindings)
        conn.commit()
    return stored


ALM_PRACTICE_COLUMNS = [
    "crop_type", "crop_rotation", "cover_crops", "intercropping",
    "tillage", "tillage_depth_cm", "residue_removed", "residue_burned_kg_ha",
    "synthetic_n_rate_kg_ha", "organic_n_rate_kg_ha",
    "n_fixing_species", "n_fixing_dry_matter_kg_ha", "fuel_use_l_ha",
    "crop_yield_t_ha", "limestone_applied_t_ha", "dolomite_applied_t_ha",
]


def save_alm_practice_schedule(org_id: str, field_id: str, scenario: str, practices: dict):
    """Upserts one baseline/project practice-schedule row for a field."""
    cols = ALM_PRACTICE_COLUMNS
    params = {c: practices.get(c) for c in cols}
    params.update(org_id=org_id, field_id=field_id, scenario=scenario)
    with get_db_connection() as conn:
        conn.execute(
            text(f"""
                INSERT INTO alm_practice_schedule (org_id, field_id, scenario, {", ".join(cols)})
                VALUES (:org_id, :field_id, :scenario, {", ".join(f":{c}" for c in cols)})
                ON CONFLICT (org_id, field_id, scenario) DO UPDATE SET
                    {", ".join(f"{c} = excluded.{c}" for c in cols)},
                    updated_at = CURRENT_TIMESTAMP
            """),
            params,
        )
        conn.commit()


def get_alm_practice_schedule(org_id: str, field_id: str) -> dict:
    """Returns {'baseline': {...} | None, 'project': {...} | None} for a field."""
    with get_db_connection() as conn:
        rows = conn.execute(
            text("SELECT * FROM alm_practice_schedule WHERE org_id = :org_id AND field_id = :field_id"),
            {"org_id": org_id, "field_id": field_id},
        ).mappings().fetchall()
    result = {"baseline": None, "project": None}
    for row in rows:
        result[row["scenario"]] = {k: row[k] for k in ALM_PRACTICE_COLUMNS}
    return result


def save_alm_livestock_schedule(org_id: str, field_id: str, scenario: str, livestock: list):
    """Replaces all livestock rows for a (field, scenario) pair. `livestock`
    is a list of {"livestock_type", "population_head", "productivity_system"}
    dicts; entries with population_head <= 0 are dropped, not stored."""
    with get_db_connection() as conn:
        conn.execute(
            text("DELETE FROM alm_livestock_schedule "
                 "WHERE org_id = :org_id AND field_id = :field_id AND scenario = :scenario"),
            {"org_id": org_id, "field_id": field_id, "scenario": scenario},
        )
        rows = [
            {
                "org_id": org_id, "field_id": field_id, "scenario": scenario,
                "livestock_type": e["livestock_type"],
                "population_head": e["population_head"],
                "productivity_system": e["productivity_system"],
            }
            for e in livestock
            if (e.get("population_head") or 0) > 0
        ]
        if rows:
            conn.execute(
                text("""
                    INSERT INTO alm_livestock_schedule
                        (org_id, field_id, scenario, livestock_type, population_head, productivity_system)
                    VALUES (:org_id, :field_id, :scenario, :livestock_type, :population_head, :productivity_system)
                """),
                rows,
            )
        conn.commit()


def get_alm_livestock_schedule(org_id: str, field_id: str) -> dict:
    """Returns {'baseline': [...], 'project': [...]} of livestock entries
    for a field, each a {"livestock_type", "population_head",
    "productivity_system"} dict."""
    with get_db_connection() as conn:
        rows = conn.execute(
            text("""
                SELECT scenario, livestock_type, population_head, productivity_system
                FROM alm_livestock_schedule WHERE org_id = :org_id AND field_id = :field_id
            """),
            {"org_id": org_id, "field_id": field_id},
        ).mappings().fetchall()
    result = {"baseline": [], "project": []}
    for row in rows:
        result[row["scenario"]].append({
            "livestock_type": row["livestock_type"],
            "population_head": row["population_head"],
            "productivity_system": row["productivity_system"],
        })
    return result


def save_soc_measurements(org_id: str, field_id: str, site_type: str, timepoint: str, values: list):
    """Replaces all sample rows for a (field, site_type, timepoint) triple."""
    with get_db_connection() as conn:
        conn.execute(
            text("DELETE FROM soc_measurements WHERE org_id = :org_id AND field_id = :field_id "
                 "AND site_type = :site_type AND timepoint = :timepoint"),
            {"org_id": org_id, "field_id": field_id, "site_type": site_type, "timepoint": timepoint},
        )
        if values:
            conn.execute(
                text("""
                    INSERT INTO soc_measurements
                        (org_id, field_id, site_type, timepoint, sample_index, soc_value_tco2e_ha)
                    VALUES (:org_id, :field_id, :site_type, :timepoint, :sample_index, :soc_value_tco2e_ha)
                """),
                [
                    {"org_id": org_id, "field_id": field_id, "site_type": site_type,
                     "timepoint": timepoint, "sample_index": i, "soc_value_tco2e_ha": v}
                    for i, v in enumerate(values)
                ],
            )
        conn.commit()


def get_alm_cumulative_delta(org_id: str, field_id: str) -> float:
    """Cumulative project SOC change (t CO2) since project start, used by
    AlmCarbonEngine.calculate_credits()'s VM0042 Eq. 37/40 ER/CR classification
    indicator. Returns 0.0 for a field with no prior verification recorded."""
    with get_db_connection() as conn:
        row = conn.execute(
            text("SELECT alm_cumulative_delta_co2_wp FROM fields WHERE org_id = :org_id AND field_id = :field_id"),
            {"org_id": org_id, "field_id": field_id},
        ).mappings().fetchone()
    return float(row["alm_cumulative_delta_co2_wp"]) if row and row["alm_cumulative_delta_co2_wp"] is not None else 0.0


def update_alm_cumulative_delta(org_id: str, field_id: str, value: float):
    """Persists the new cumulative total after a successful calculate_credits() call."""
    with get_db_connection() as conn:
        conn.execute(
            text("UPDATE fields SET alm_cumulative_delta_co2_wp = :value "
                 "WHERE org_id = :org_id AND field_id = :field_id"),
            {"value": value, "org_id": org_id, "field_id": field_id},
        )
        conn.commit()


def delete_field(org_id: str, field_id: str):
    """Deletes a field and every row keyed to it across all tables — the
    registry entry, cached timeseries, (for cropland_alm_vm0042 fields) the
    practice schedule, livestock schedule, and SOC measurements, and the
    calculated-credit history log. Foreign keys aren't enforced here, so
    this cascade is done explicitly rather than relying on ON DELETE
    CASCADE."""
    params = {"org_id": org_id, "field_id": field_id}
    with get_db_connection() as conn:
        # calculation_attachment_refs has no field_id column of its own —
        # scoped via the calculations it belongs to instead.
        conn.execute(text("""
            DELETE FROM calculation_attachment_refs WHERE org_id = :org_id AND calculation_id IN (
                SELECT calculation_id FROM calculations WHERE org_id = :org_id AND field_id = :field_id
            )
        """), params)
        # soil_strata has no field_id column of its own — scoped via the
        # sampling plan it belongs to (soil_sampling_plans/soil_samples
        # both DO have field_id, so they're covered by the plain loop below).
        conn.execute(text("""
            DELETE FROM soil_strata WHERE org_id = :org_id AND plan_id IN (
                SELECT plan_id FROM soil_sampling_plans WHERE org_id = :org_id AND field_id = :field_id
            )
        """), params)
        # Same pattern for review_submissions' children — reachable only
        # when the field has no review history at all (the fields router
        # refuses deletion otherwise; see src.projects.reviews.field_has_submissions),
        # kept here purely as a defensive, correct cascade.
        for child_table, fk in (
            ("reviewer_assignments", "submission_id"), ("review_events", "submission_id"),
            ("findings", "submission_id"),
        ):
            conn.execute(text(f"""
                DELETE FROM {child_table} WHERE org_id = :org_id AND {fk} IN (
                    SELECT submission_id FROM review_submissions WHERE org_id = :org_id AND field_id = :field_id
                )
            """), params)
        conn.execute(text("""
            DELETE FROM finding_comments WHERE org_id = :org_id AND finding_id IN (
                SELECT finding_id FROM findings WHERE org_id = :org_id AND submission_id IN (
                    SELECT submission_id FROM review_submissions WHERE org_id = :org_id AND field_id = :field_id
                )
            )
        """), params)
        for table in (
            "fields", "timeseries_cache", "alm_practice_schedule",
            "alm_livestock_schedule", "soc_measurements", "credit_history",
            "crop_seasons", "field_observations", "observation_reviews", "monitoring_runs",
            "practice_events", "timeseries_cache_versions",
            "project_fields", "farm_fields", "attachments",
            "calculations", "calculation_idempotency_keys", "readiness_determinations",
            "review_submissions", "quantification_units",
            "soil_sampling_plans", "soil_samples",
        ):
            conn.execute(
                text(f"DELETE FROM {table} WHERE org_id = :org_id AND field_id = :field_id"),
                params,
            )
        conn.commit()


def save_credit_history(org_id: str, field_id: str, field_type: str, inputs: dict, result: dict):
    """Logs one calculate_credits() run so past calculations survive a
    session/page revisit — today only session_state holds this, so nothing
    persists once the user navigates away. Stores the full inputs/result
    dicts as JSON, not just final_issuance, so a past run can be inspected
    in detail rather than just its headline figure."""
    if field_type == "cropland_alm_vm0042":
        raise NonIssuableResultError("ALM results must use the evidence-linked Calculations workflow.")
    with get_db_connection() as conn:
        conn.execute(
            text("""
                INSERT INTO credit_history (org_id, field_id, field_type, final_issuance, inputs_json, result_json)
                VALUES (:org_id, :field_id, :field_type, :final_issuance, :inputs_json, :result_json)
            """),
            {
                "org_id": org_id, "field_id": field_id, "field_type": field_type,
                "final_issuance": float(result["final_issuance"]),
                "inputs_json": json.dumps(inputs), "result_json": json.dumps(result),
            },
        )
        conn.commit()


def get_credit_history(org_id: str, field_id: str) -> list:
    """Returns this field's past calculate_credits() runs, most recent
    first, each as {'credit_history_id', 'calculated_at', 'final_issuance',
    'inputs', 'result'}. credit_history_id is the real, stable primary-key
    id of the row — the only thing safe to use to identify a specific
    committed verification later (never an array index/timestamp/field_id)."""
    with get_db_connection() as conn:
        rows = conn.execute(
            text("""
                SELECT id, calculated_at, final_issuance, inputs_json, result_json
                FROM credit_history
                WHERE org_id = :org_id AND field_id = :field_id
                ORDER BY calculated_at DESC, id DESC
            """),
            {"org_id": org_id, "field_id": field_id},
        ).mappings().fetchall()
    return [
        {
            "credit_history_id": row["id"],
            "calculated_at": row["calculated_at"],
            "final_issuance": row["final_issuance"],
            "inputs": json.loads(row["inputs_json"]),
            "result": json.loads(row["result_json"]),
        }
        for row in rows
    ]


def get_credit_history_entry(org_id: str, field_id: str, credit_history_id: int) -> dict | None:
    """Org+field-scoped lookup of ONE committed verification run by its
    stable id (see get_credit_history's credit_history_id). Returns None
    if the id doesn't exist, or belongs to a different org/field — callers
    should turn that into a 404, never leak which case it was."""
    with get_db_connection() as conn:
        row = conn.execute(
            text("""
                SELECT id, calculated_at, final_issuance, inputs_json, result_json
                FROM credit_history
                WHERE org_id = :org_id AND field_id = :field_id AND id = :id
            """),
            {"org_id": org_id, "field_id": field_id, "id": credit_history_id},
        ).mappings().fetchone()
    if row is None:
        return None
    return {
        "credit_history_id": row["id"],
        "calculated_at": row["calculated_at"],
        "final_issuance": row["final_issuance"],
        "inputs": json.loads(row["inputs_json"]),
        "result": json.loads(row["result_json"]),
    }


def get_latest_signal_result(org_id: str, field_id: str) -> dict | None:
    """Most recently completed signal_run job for this field. NOT tied to
    any specific credit_history row — there is no stored link between a
    committed verification and the signal_run job that produced its rice
    inputs, so this is a best-effort "current signal context" lookup, not
    provenance for a historical export. Callers must not present it as such."""
    for job in list_completed_jobs(org_id, "signal_run"):
        if job["result"] and job["result"].get("field_id") == field_id:
            return job["result"]
    return None


def get_portfolio_summary(org_id: str) -> list:
    """One row per registered field belonging to this org — identity/area
    plus its latest calculated credit (final_issuance/calculated_at are
    None if the field has never had Calculate Carbon Credits run) — for a
    cross-field aggregate view spanning both methodology paths."""
    with get_db_connection() as conn:
        field_rows = conn.execute(
            text("SELECT field_id, name, district, field_type, area_ha FROM fields "
                 "WHERE org_id = :org_id ORDER BY field_id"),
            {"org_id": org_id},
        ).mappings().fetchall()
        latest_rows = conn.execute(
            text("""
                SELECT field_id, final_issuance, calculated_at
                FROM credit_history
                WHERE org_id = :org_id AND id IN (
                    SELECT MAX(id) FROM credit_history WHERE org_id = :org_id GROUP BY field_id
                )
            """),
            {"org_id": org_id},
        ).mappings().fetchall()
    latest_by_field = {row["field_id"]: row for row in latest_rows}

    summary = []
    for f in field_rows:
        latest = latest_by_field.get(f["field_id"])
        summary.append({
            "field_id": f["field_id"],
            "name": f["name"],
            "district": f["district"],
            "field_type": f["field_type"],
            "area_ha": f["area_ha"],
            "final_issuance": latest["final_issuance"] if latest else None,
            "calculated_at": latest["calculated_at"] if latest else None,
        })
    return summary


def get_soc_measurements(org_id: str, field_id: str) -> dict:
    """Returns {(site_type, timepoint): [values...]} for a field."""
    with get_db_connection() as conn:
        rows = conn.execute(
            text("""
                SELECT site_type, timepoint, soc_value_tco2e_ha
                FROM soc_measurements
                WHERE org_id = :org_id AND field_id = :field_id
                ORDER BY site_type, timepoint, sample_index
            """),
            {"org_id": org_id, "field_id": field_id},
        ).mappings().fetchall()
    result = {}
    for row in rows:
        key = (row["site_type"], row["timepoint"])
        result.setdefault(key, []).append(row["soc_value_tco2e_ha"])
    return result


# ---------------------------------------------------------------------------
# Additive functions for the FastAPI backend (.claude/plans/misty-growing-yao.md
# Part A3) — app.py continues to do its own inline INSERT/SELECT for field
# registration unchanged; these exist so backend/routers/fields.py has a
# proper function to call instead of duplicating that SQL a second time.
# ---------------------------------------------------------------------------

def create_field(
    org_id: str, field_id: str, name: str, district: str,
    feature: dict, area_ha: float, field_type: str,
):
    """Registers a new field. `feature` is a single GeoJSON Feature (the
    parsed/drawn geometry) — wrapped in a FeatureCollection before storage,
    matching app.py's own `geojson_geometry` convention exactly, so rows
    written via this function and rows written via app.py's inline SQL are
    indistinguishable to every other reader (get_field, list_fields, the
    Streamlit sidebar's own SELECT)."""
    fc = {"type": "FeatureCollection", "features": [feature]}
    with get_db_connection() as conn:
        conn.execute(
            text("INSERT INTO fields "
                 "(org_id, field_id, name, district, geojson_geometry, area_ha, field_type) "
                 "VALUES (:org_id, :field_id, :name, :district, :geojson_geometry, :area_ha, :field_type)"),
            {"org_id": org_id, "field_id": field_id, "name": name, "district": district,
             "geojson_geometry": json.dumps(fc), "area_ha": area_ha, "field_type": field_type},
        )
        conn.commit()


def get_field(org_id: str, field_id: str) -> dict | None:
    """Returns one field's full record (including geojson_geometry, parsed
    back into a dict) or None if it doesn't exist / belongs to another org."""
    with get_db_connection() as conn:
        row = conn.execute(
            text("SELECT field_id, name, district, geojson_geometry, area_ha, "
                 "field_type, created_at, alm_cumulative_delta_co2_wp FROM fields "
                 "WHERE org_id = :org_id AND field_id = :field_id"),
            {"org_id": org_id, "field_id": field_id},
        ).mappings().fetchone()
    if row is None:
        return None
    result = dict(row)
    result["geojson_geometry"] = json.loads(result["geojson_geometry"])
    return result


def list_fields(org_id: str) -> list[dict]:
    """Returns every field belonging to this org (summary columns only —
    no geojson_geometry, matching the Streamlit sidebar's own listing query;
    callers needing geometry should follow up with get_field)."""
    with get_db_connection() as conn:
        rows = conn.execute(
            text("SELECT field_id, name, district, area_ha, field_type, created_at "
                 "FROM fields WHERE org_id = :org_id ORDER BY field_id"),
            {"org_id": org_id},
        ).mappings().fetchall()
    return [dict(r) for r in rows]


def commit_carbon_credit_result(
    org_id: str, field_id: str, idempotency_key: str, field_type: str,
    inputs: dict, result: dict, new_cumulative_delta: float | None = None,
) -> dict:
    """Atomically persists one Calculate-Carbon-Credits run: the
    credit_history row, the idempotency-key record, and (for ALM,
    when new_cumulative_delta is given) the cumulative SOC delta bump —
    all in ONE connection/ONE commit, unlike calling save_credit_history +
    update_alm_cumulative_delta back-to-back from a router (two separate
    connections, two separate commits), which would leave the two writes
    non-atomic under a crash or a concurrent duplicate request. A retried
    request with the same idempotency_key returns the original result
    instead of double-accruing the cumulative delta — the whole reason
    this function exists rather than just being save_credit_history called
    twice: a single browser tab (today's only client) never raced this;
    multiple people hitting the API concurrently can.

    Returns {"final_issuance": ..., "already_committed": bool}.

    Refuses to persist a result that its methodology has blocked from
    issuance (raises NonIssuableResultError). This guard lives here, at
    the single write path, rather than in each caller — the two clients
    previously each implemented "gate then persist" and app.py had them
    in the wrong order, so blocked calculations were still recorded as
    issuance rows. See src/carbon/issuance.py.
    """
    # Lazy import: src.carbon.calculations imports from this module at load time,
    # so importing it back at module level here would be circular.
    from src.carbon.calculations import PATHWAYS
    if field_type == "cropland_alm_vm0042":
        raise NonIssuableResultError(
            "New ALM records require the evidence-linked Calculations workflow and full readiness checks. "
            "Legacy credit history remains available for reading."
        )
    issuable, block_reason = result_is_issuable(result, PATHWAYS.get(field_type))
    if not issuable:
        raise NonIssuableResultError(
            f"refusing to persist a non-issuable calculation for field "
            f"{field_id!r}: {block_reason}"
        )

    with get_db_connection() as conn:
        existing = conn.execute(
            text("SELECT credit_history_id FROM commit_idempotency_keys "
                 "WHERE org_id = :org_id AND field_id = :field_id AND idempotency_key = :key"),
            {"org_id": org_id, "field_id": field_id, "key": idempotency_key},
        ).mappings().fetchone()
        if existing is not None:
            prior = conn.execute(
                text("SELECT final_issuance FROM credit_history WHERE id = :id"),
                {"id": existing["credit_history_id"]},
            ).mappings().fetchone()
            return {
                "final_issuance": prior["final_issuance"] if prior else None,
                "already_committed": True,
            }

        insert_result = conn.execute(
            text("""
                INSERT INTO credit_history (org_id, field_id, field_type, final_issuance, inputs_json, result_json)
                VALUES (:org_id, :field_id, :field_type, :final_issuance, :inputs_json, :result_json)
            """),
            {
                "org_id": org_id, "field_id": field_id, "field_type": field_type,
                "final_issuance": float(result["final_issuance"]),
                "inputs_json": json.dumps(inputs), "result_json": json.dumps(result),
            },
        )
        credit_history_id = insert_result.lastrowid if is_sqlite() else conn.execute(
            text("SELECT MAX(id) FROM credit_history WHERE org_id = :org_id AND field_id = :field_id"),
            {"org_id": org_id, "field_id": field_id},
        ).scalar()

        conn.execute(
            text("INSERT INTO commit_idempotency_keys (org_id, field_id, idempotency_key, credit_history_id) "
                 "VALUES (:org_id, :field_id, :key, :chid)"),
            {"org_id": org_id, "field_id": field_id, "key": idempotency_key, "chid": credit_history_id},
        )

        if new_cumulative_delta is not None:
            conn.execute(
                text("UPDATE fields SET alm_cumulative_delta_co2_wp = :value "
                     "WHERE org_id = :org_id AND field_id = :field_id"),
                {"value": new_cumulative_delta, "org_id": org_id, "field_id": field_id},
            )

        conn.commit()
    return {"final_issuance": float(result["final_issuance"]), "already_committed": False}


def create_job(org_id: str, job_type: str) -> str:
    """Creates a pending background_jobs row, returns its job_id. Used by
    the GEE signal-run and AI-training background-task endpoints
    (Part A4) — a plain DB-backed table rather than Celery/RQ, since this
    app's whole operating model is 'one process + SQLite/Postgres' and a
    broker+worker is real new infra not justified at this scale."""
    job_id = uuid.uuid4().hex
    with get_db_connection() as conn:
        conn.execute(
            text("INSERT INTO background_jobs (job_id, org_id, job_type) VALUES (:j, :o, :t)"),
            {"j": job_id, "o": org_id, "t": job_type},
        )
        conn.commit()
    return job_id


def mark_job_running(job_id: str):
    with get_db_connection() as conn:
        conn.execute(
            text("UPDATE background_jobs SET status = 'running' WHERE job_id = :j"),
            {"j": job_id},
        )
        conn.commit()


def mark_job_done(job_id: str, result: dict):
    with get_db_connection() as conn:
        conn.execute(
            text("UPDATE background_jobs SET status = 'done', result_json = :r, "
                 "finished_at = CURRENT_TIMESTAMP WHERE job_id = :j"),
            {"r": json.dumps(result, default=str), "j": job_id},
        )
        conn.commit()


def mark_job_error(job_id: str, error: str):
    with get_db_connection() as conn:
        conn.execute(
            text("UPDATE background_jobs SET status = 'error', error = :e, "
                 "finished_at = CURRENT_TIMESTAMP WHERE job_id = :j"),
            {"e": error, "j": job_id},
        )
        conn.commit()


def get_job(org_id: str, job_id: str) -> dict | None:
    """Org-scoped lookup — a job_id from another org 404s rather than
    leaking its status/result, same tenant-isolation discipline as every
    other function in this file."""
    with get_db_connection() as conn:
        row = conn.execute(
            text("SELECT job_id, job_type, status, result_json, progress_json, error, created_at, finished_at "
                 "FROM background_jobs WHERE org_id = :org_id AND job_id = :job_id"),
            {"org_id": org_id, "job_id": job_id},
        ).mappings().fetchone()
    if row is None:
        return None
    result = dict(row)
    result["result"] = json.loads(result.pop("result_json")) if result["result_json"] else None
    result["progress"] = json.loads(result.pop("progress_json") or "null")
    return result


def list_completed_jobs(org_id: str, job_type: str) -> list[dict]:
    """Completed jobs of one type for this org, most recently finished
    first, each with its `result` already JSON-decoded.

    Exists because both backend/routers/export.py and backend/routers/ai.py
    had hand-written raw SQL for "latest completed job of type T" inside
    the router (one of them with function-local imports), which put a
    query in the HTTP layer and meant a third job type would be a third
    copy. Callers still post-filter in Python on something inside the
    result payload (field_id, model_name) — that stays caller-side because
    the predicate differs per job type and the payload is opaque JSON.
    """
    with get_db_connection() as conn:
        rows = conn.execute(
            text("SELECT job_id, result_json FROM background_jobs "
                 "WHERE org_id = :org_id AND job_type = :job_type AND status = 'done' "
                 "ORDER BY finished_at DESC"),
            {"org_id": org_id, "job_type": job_type},
        ).mappings().fetchall()
    return [
        {"job_id": r["job_id"],
         "result": json.loads(r["result_json"]) if r["result_json"] else None}
        for r in rows
    ]


def upsert_pending_registration(
    registration_id: str, email: str, org_name: str, password_hash: str, otp_hash: str,
    expires_at: str, resend_cooldown_seconds: int, max_attempts: int,
) -> dict:
    """Creates (or replaces, on resend) the single live OTP registration
    row for this email. `INSERT ... ON CONFLICT(email) DO UPDATE` is
    portable across SQLite 3.24+ and Postgres with identical syntax, so
    no dialect branch is needed here (unlike save_cache's INSERT OR
    REPLACE vs INSERT..ON CONFLICT split, which exists only because
    SQLite's UPSERT support arrived after this codebase's minimum
    version assumption elsewhere — not relevant here since this table
    is new and has no legacy callers to match).

    `registration_id` is generated by the caller (not here) because the
    caller must salt-hash the OTP with it *before* this call — the
    stored otp_hash and the id it was salted with have to match.

    The resend cooldown is enforced INSIDE this statement's transaction
    (checked against the existing row's last_sent_at before deciding
    whether to upsert), not as a separate pre-check in the caller, to
    avoid a race between checking and writing. Raises ValueError if a
    resend is attempted before the cooldown elapses.
    """
    with get_db_connection() as conn:
        existing = conn.execute(
            text("SELECT last_sent_at FROM pending_registrations "
                 "WHERE email = :email AND consumed_at IS NULL"),
            {"email": email},
        ).mappings().fetchone()
        if existing is not None:
            since_last = conn.execute(
                text("SELECT (CAST((julianday(CURRENT_TIMESTAMP) - julianday(:last)) * 86400 AS INTEGER))"
                     if is_sqlite() else
                     "SELECT EXTRACT(EPOCH FROM (now() - :last))"),
                {"last": existing["last_sent_at"]},
            ).scalar()
            if since_last is not None and since_last < resend_cooldown_seconds:
                raise ValueError(
                    f"A code was already sent recently; wait {resend_cooldown_seconds - int(since_last)}s before requesting another."
                )

        conn.execute(
            text("""
                INSERT INTO pending_registrations
                    (registration_id, email, org_name, password_hash, otp_hash,
                     attempt_count, max_attempts, expires_at, last_sent_at)
                VALUES
                    (:registration_id, :email, :org_name, :password_hash, :otp_hash,
                     0, :max_attempts, :expires_at, CURRENT_TIMESTAMP)
                ON CONFLICT (email) DO UPDATE SET
                    registration_id = excluded.registration_id,
                    org_name = excluded.org_name,
                    password_hash = excluded.password_hash,
                    otp_hash = excluded.otp_hash,
                    attempt_count = 0,
                    max_attempts = excluded.max_attempts,
                    expires_at = excluded.expires_at,
                    last_sent_at = CURRENT_TIMESTAMP,
                    consumed_at = NULL
            """),
            {
                "registration_id": registration_id, "email": email, "org_name": org_name,
                "password_hash": password_hash, "otp_hash": otp_hash,
                "max_attempts": max_attempts, "expires_at": expires_at,
            },
        )
        conn.commit()
    return {"registration_id": registration_id, "email": email}


def get_pending_registration(email: str) -> dict | None:
    """Returns the live (not yet consumed) pending_registrations row for
    this email, or None."""
    with get_db_connection() as conn:
        row = conn.execute(
            text("SELECT * FROM pending_registrations WHERE email = :email AND consumed_at IS NULL"),
            {"email": email},
        ).mappings().fetchone()
    return dict(row) if row else None


def record_otp_attempt_failure(registration_id: str) -> int:
    """Increments attempt_count on a wrong-OTP guess, returns the new
    count so the caller can compare it against max_attempts."""
    with get_db_connection() as conn:
        conn.execute(
            text("UPDATE pending_registrations SET attempt_count = attempt_count + 1 "
                 "WHERE registration_id = :id"),
            {"id": registration_id},
        )
        conn.commit()
        return conn.execute(
            text("SELECT attempt_count FROM pending_registrations WHERE registration_id = :id"),
            {"id": registration_id},
        ).scalar()


def verify_and_create_org(registration_id: str, org_id: str, user_id: str) -> dict | None:
    """Single-transaction completion of a signup: conditionally marks the
    pending_registrations row consumed, re-checks the email hasn't been
    claimed by a real user in the meantime, then creates the organization
    + its first admin user — all in ONE connection/ONE commit, mirroring
    commit_carbon_credit_result's check-then-write shape (Part A3.2).

    Returns the new user dict, or None if:
    - the row was already consumed or doesn't exist (a losing double-verify
      race, or a stale/garbage registration_id) — caller maps to 409/410
    - the email was claimed by a real user in the meantime — caller maps to 409

    The conditional UPDATE ... WHERE consumed_at IS NULL + checking
    rowcount is what actually resolves the double-verify race: only one
    of two concurrent calls with the correct OTP can flip consumed_at
    from NULL, so only one can proceed past this point.
    """
    with get_db_connection() as conn:
        row = conn.execute(
            text("SELECT * FROM pending_registrations WHERE registration_id = :id"),
            {"id": registration_id},
        ).mappings().fetchone()
        if row is None:
            return None

        result = conn.execute(
            text("UPDATE pending_registrations SET consumed_at = CURRENT_TIMESTAMP "
                 "WHERE registration_id = :id AND consumed_at IS NULL"),
            {"id": registration_id},
        )
        if result.rowcount == 0:
            return None  # already consumed by a concurrent/prior call

        already_real_user = conn.execute(
            text("SELECT 1 FROM users WHERE email = :email"),
            {"email": row["email"]},
        ).fetchone()
        if already_real_user is not None:
            return None

        conn.execute(
            text("INSERT INTO organizations (org_id, name, plan) VALUES (:org_id, :name, 'trial')"),
            {"org_id": org_id, "name": row["org_name"]},
        )
        conn.execute(
            text("INSERT INTO users (user_id, org_id, email, password_hash, role) "
                 "VALUES (:user_id, :org_id, :email, :password_hash, 'admin')"),
            {"user_id": user_id, "org_id": org_id, "email": row["email"],
             "password_hash": row["password_hash"]},
        )
        conn.commit()
    return {"user_id": user_id, "org_id": org_id, "email": row["email"], "role": "admin"}
