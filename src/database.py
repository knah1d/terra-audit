import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "project_store.db"
_DB_INITIALIZED = False


@contextmanager
def get_db_connection():
    """Context manager: opens a connection, yields it, then always closes it."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # WAL lets readers proceed while a writer holds the file, and the busy
    # timeout gives a second writer a chance to retry instead of raising
    # "database is locked" immediately — both matter once more than one
    # tenant's session can write concurrently (see multi-tenant auth plan).
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()


def initialize_database():
    """Idempotently creates all tables and applies schema migrations."""
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fields (
                field_id         TEXT PRIMARY KEY,
                name             TEXT NOT NULL,
                district         TEXT NOT NULL,
                geojson_geometry TEXT NOT NULL,
                area_ha          REAL,
                field_type       TEXT NOT NULL DEFAULT 'rice_awd',
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration: add area_ha/field_type to existing DBs that predate these columns
        try:
            conn.execute("ALTER TABLE fields ADD COLUMN area_ha REAL")
        except Exception:
            pass
        try:
            conn.execute(
                "ALTER TABLE fields ADD COLUMN field_type TEXT NOT NULL DEFAULT 'rice_awd'"
            )
        except Exception:
            pass
        # Migration: cumulative ALM SOC indicator (VM0042 Eq. 37/40's I(deltaCO2wp)
        # is defined on the cumulative change since project start, not a single
        # verification period) — carbon_calculator_alm.AlmCarbonEngine.calculate_credits()
        try:
            conn.execute(
                "ALTER TABLE fields ADD COLUMN alm_cumulative_delta_co2_wp REAL DEFAULT 0.0"
            )
        except Exception:
            pass
        # PK covers field + observation date + the exact analysis window.
        # This prevents a 2024-01-15 observation overwriting a 2025-01-15
        # observation that shares the same calendar date string.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS timeseries_cache (
                field_id         TEXT,
                observation_date TEXT,
                window_start     TEXT,
                window_end       TEXT,
                vv               REAL,
                vh               REAL,
                cross_ratio      REAL,
                rvi              REAL,
                PRIMARY KEY (field_id, observation_date, window_start, window_end)
            )
        """)
        # Migration: add window columns to old single-window schema if absent
        for col in ("window_start TEXT", "window_end TEXT"):
            try:
                conn.execute(f"ALTER TABLE timeseries_cache ADD COLUMN {col}")
            except Exception:
                pass  # Column already exists

        # VM0042 ALM field type — baseline vs project practice schedule
        # (Table 4 subset: crop planting/harvesting, fertilizer, tillage/residue).
        # One row per (field_id, scenario); columns left NULL where not applicable.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alm_practice_schedule (
                field_id                TEXT NOT NULL,
                scenario                TEXT NOT NULL CHECK (scenario IN ('baseline', 'project')),
                crop_type               TEXT,
                crop_rotation           INTEGER,
                cover_crops             INTEGER,
                intercropping           INTEGER,
                tillage                 INTEGER,
                tillage_depth_cm        REAL,
                residue_removed         INTEGER,
                residue_burned_kg_ha    REAL,
                synthetic_n_rate_kg_ha  REAL,
                organic_n_rate_kg_ha    REAL,
                n_fixing_species        INTEGER,
                n_fixing_dry_matter_kg_ha REAL,
                fuel_use_l_ha           REAL,
                crop_yield_t_ha         REAL,
                updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (field_id, scenario)
            )
        """)
        # Migration: crop_yield_t_ha added later (VMD0054 production-decline
        # leakage screening — see carbon_calculator_alm.py) for DBs that predate it
        try:
            conn.execute("ALTER TABLE alm_practice_schedule ADD COLUMN crop_yield_t_ha REAL")
        except Exception:
            pass

        # VM0042 ALM field type — integrated crop-livestock schedule (§8.2.6/
        # §8.2.7/§8.2.10, Pasture/Range/Paddock scope — see AlmCarbonEngine's
        # LIVESTOCK_TABLE docstring). One row per (field_id, scenario,
        # livestock_type); zero-population entries are never stored.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alm_livestock_schedule (
                field_id            TEXT NOT NULL,
                scenario            TEXT NOT NULL CHECK (scenario IN ('baseline', 'project')),
                livestock_type      TEXT NOT NULL,
                population_head     REAL NOT NULL,
                productivity_system TEXT NOT NULL CHECK (productivity_system IN ('high', 'low')),
                updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (field_id, scenario, livestock_type)
            )
        """)

        # VM0042 ALM field type — SOC lab measurements (Quantification Approach 2).
        # Paired project-site vs baseline-control-site samples at two timepoints,
        # feeding Eqs 3-5/46-47 (stock change) and Eqs 70-71/74 (uncertainty).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS soc_measurements (
                field_id            TEXT NOT NULL,
                site_type           TEXT NOT NULL CHECK (site_type IN ('project', 'control')),
                timepoint           TEXT NOT NULL CHECK (timepoint IN ('t_start', 't_final')),
                sample_index        INTEGER NOT NULL,
                soc_value_tco2e_ha  REAL NOT NULL,
                measured_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (field_id, site_type, timepoint, sample_index)
            )
        """)

        # Persisted log of every "Calculate Carbon Credits" run — one row per
        # click, for either methodology path. inputs_json/result_json store
        # the full calculate_credits() call so a past run can be inspected in
        # detail, not just its headline final_issuance figure.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS credit_history (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                field_id       TEXT NOT NULL,
                field_type     TEXT NOT NULL,
                calculated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                final_issuance REAL NOT NULL,
                inputs_json    TEXT NOT NULL,
                result_json    TEXT NOT NULL
            )
        """)

        # ---------------------------------------------------------------
        # Multi-tenancy foundation (Phase 0 of the auth/multi-tenant plan).
        # These two tables are additive only in this phase — nothing else
        # reads/writes them yet, so this is a no-op for the existing
        # single-operator deployment. org_id columns land on the data
        # tables in Phase 2, once login (Phase 1) exists to supply one.
        # ---------------------------------------------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                org_id     TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                plan       TEXT NOT NULL DEFAULT 'trial',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       TEXT PRIMARY KEY,
                org_id        TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'analyst'
                              CHECK (role IN ('admin', 'analyst', 'viewer')),
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP
            )
        """)
        # Legacy/default org — gives every pre-existing row (and Phase 2's
        # org_id backfill) a home without forcing an immediate data migration.
        conn.execute(
            "INSERT OR IGNORE INTO organizations (org_id, name, plan) "
            "VALUES ('default', 'Legacy Operator', 'legacy')"
        )

        # ---------------------------------------------------------------
        # Phase 2 of the multi-tenant plan: org_id lands on every data
        # table, denormalized (no join) — consistent with this file's
        # existing style (credit_history already duplicates field_type
        # rather than joining fields; get_portfolio_summary() already
        # merges two queries in Python rather than a SQL JOIN). Every
        # pre-existing row backfills to 'default' so nothing breaks for
        # the existing single-operator deployment.
        # ---------------------------------------------------------------
        for _table in (
            "fields", "timeseries_cache", "alm_practice_schedule",
            "alm_livestock_schedule", "soc_measurements", "credit_history",
        ):
            try:
                conn.execute(
                    f"ALTER TABLE {_table} ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default'"
                )
            except Exception:
                pass

        # SQLite can't redefine a PRIMARY KEY via ALTER TABLE, so field_id
        # stays the legacy PK for backward compatibility, but this unique
        # index is the real going-forward invariant: field IDs only need
        # to be unique per org, not globally.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_fields_org_field "
            "ON fields(org_id, field_id)"
        )
        for _table in (
            "timeseries_cache", "alm_practice_schedule",
            "alm_livestock_schedule", "soc_measurements", "credit_history",
        ):
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{_table}_org ON {_table}(org_id)"
            )

        conn.commit()
    _DB_INITIALIZED = True


def update_field_info(org_id: str, field_id: str, name: str, district: str):
    """Updates a field's name/district in place. field_type and geometry are
    deliberately not editable here — changing methodology path or redrawing
    a boundary means the field's underlying data (SAR cache vs. practice/SOC
    rows) no longer matches, so those still require delete + re-register."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE fields SET name = ?, district = ? WHERE org_id = ? AND field_id = ?",
            (name, district, org_id, field_id),
        )
        conn.commit()


def check_cache(org_id: str, field_id: str, window_start: str, window_end: str) -> pd.DataFrame:
    """
    Retrieves cached time-series records keyed to a specific org+field AND
    analysis window. Returns an empty DataFrame on a cache miss.
    """
    with get_db_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT observation_date AS date, vv, vh, cross_ratio, rvi
            FROM   timeseries_cache
            WHERE  org_id       = ?
              AND  field_id     = ?
              AND  window_start = ?
              AND  window_end   = ?
            ORDER  BY date ASC
            """,
            conn,
            params=(org_id, field_id, window_start, window_end),
        )
    return df


def save_cache(
    org_id: str, field_id: str, df: pd.DataFrame, window_start: str, window_end: str
):
    """Commits a batch of EE-fetched observations into the local cache."""
    if df.empty:
        return
    with get_db_connection() as conn:
        rows = [
            (
                org_id,
                field_id,
                row["date"],
                window_start,
                window_end,
                row["vv"],
                row["vh"],
                row["cross_ratio"],
                row["rvi"],
            )
            for _, row in df.iterrows()
        ]
        conn.executemany(
            """
            INSERT OR REPLACE INTO timeseries_cache
                (org_id, field_id, observation_date, window_start, window_end,
                 vv, vh, cross_ratio, rvi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


ALM_PRACTICE_COLUMNS = [
    "crop_type", "crop_rotation", "cover_crops", "intercropping",
    "tillage", "tillage_depth_cm", "residue_removed", "residue_burned_kg_ha",
    "synthetic_n_rate_kg_ha", "organic_n_rate_kg_ha",
    "n_fixing_species", "n_fixing_dry_matter_kg_ha", "fuel_use_l_ha",
    "crop_yield_t_ha",
]


def save_alm_practice_schedule(org_id: str, field_id: str, scenario: str, practices: dict):
    """Upserts one baseline/project practice-schedule row for a field."""
    cols = ALM_PRACTICE_COLUMNS
    values = [practices.get(c) for c in cols]
    with get_db_connection() as conn:
        conn.execute(
            f"""
            INSERT INTO alm_practice_schedule (org_id, field_id, scenario, {", ".join(cols)})
            VALUES (?, ?, ?, {", ".join("?" for _ in cols)})
            ON CONFLICT (field_id, scenario) DO UPDATE SET
                {", ".join(f"{c} = excluded.{c}" for c in cols)},
                updated_at = CURRENT_TIMESTAMP
            """,
            (org_id, field_id, scenario, *values),
        )
        conn.commit()


def get_alm_practice_schedule(org_id: str, field_id: str) -> dict:
    """Returns {'baseline': {...} | None, 'project': {...} | None} for a field."""
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM alm_practice_schedule WHERE org_id = ? AND field_id = ?",
            (org_id, field_id),
        ).fetchall()
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
            "DELETE FROM alm_livestock_schedule WHERE org_id = ? AND field_id = ? AND scenario = ?",
            (org_id, field_id, scenario),
        )
        rows = [
            (org_id, field_id, scenario, e["livestock_type"], e["population_head"], e["productivity_system"])
            for e in livestock
            if (e.get("population_head") or 0) > 0
        ]
        if rows:
            conn.executemany(
                """
                INSERT INTO alm_livestock_schedule
                    (org_id, field_id, scenario, livestock_type, population_head, productivity_system)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        conn.commit()


def get_alm_livestock_schedule(org_id: str, field_id: str) -> dict:
    """Returns {'baseline': [...], 'project': [...]} of livestock entries
    for a field, each a {"livestock_type", "population_head",
    "productivity_system"} dict."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT scenario, livestock_type, population_head, productivity_system
            FROM alm_livestock_schedule WHERE org_id = ? AND field_id = ?
            """,
            (org_id, field_id),
        ).fetchall()
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
            "DELETE FROM soc_measurements WHERE org_id = ? AND field_id = ? AND site_type = ? AND timepoint = ?",
            (org_id, field_id, site_type, timepoint),
        )
        conn.executemany(
            """
            INSERT INTO soc_measurements
                (org_id, field_id, site_type, timepoint, sample_index, soc_value_tco2e_ha)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(org_id, field_id, site_type, timepoint, i, v) for i, v in enumerate(values)],
        )
        conn.commit()


def get_alm_cumulative_delta(org_id: str, field_id: str) -> float:
    """Cumulative project SOC change (t CO2) since project start, used by
    AlmCarbonEngine.calculate_credits()'s VM0042 Eq. 37/40 ER/CR classification
    indicator. Returns 0.0 for a field with no prior verification recorded."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT alm_cumulative_delta_co2_wp FROM fields WHERE org_id = ? AND field_id = ?",
            (org_id, field_id),
        ).fetchone()
    return float(row["alm_cumulative_delta_co2_wp"]) if row and row["alm_cumulative_delta_co2_wp"] is not None else 0.0


def update_alm_cumulative_delta(org_id: str, field_id: str, value: float):
    """Persists the new cumulative total after a successful calculate_credits() call."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE fields SET alm_cumulative_delta_co2_wp = ? WHERE org_id = ? AND field_id = ?",
            (value, org_id, field_id),
        )
        conn.commit()


def delete_field(org_id: str, field_id: str):
    """Deletes a field and every row keyed to it across all tables — the
    registry entry, cached timeseries, (for cropland_alm_vm0042 fields) the
    practice schedule, livestock schedule, and SOC measurements, and the
    calculated-credit history log. SQLite foreign keys aren't enforced here,
    so this cascade is done explicitly rather than relying on ON DELETE
    CASCADE."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM fields WHERE org_id = ? AND field_id = ?", (org_id, field_id))
        conn.execute("DELETE FROM timeseries_cache WHERE org_id = ? AND field_id = ?", (org_id, field_id))
        conn.execute("DELETE FROM alm_practice_schedule WHERE org_id = ? AND field_id = ?", (org_id, field_id))
        conn.execute("DELETE FROM alm_livestock_schedule WHERE org_id = ? AND field_id = ?", (org_id, field_id))
        conn.execute("DELETE FROM soc_measurements WHERE org_id = ? AND field_id = ?", (org_id, field_id))
        conn.execute("DELETE FROM credit_history WHERE org_id = ? AND field_id = ?", (org_id, field_id))
        conn.commit()


def save_credit_history(org_id: str, field_id: str, field_type: str, inputs: dict, result: dict):
    """Logs one calculate_credits() run so past calculations survive a
    session/page revisit — today only session_state holds this, so nothing
    persists once the user navigates away. Stores the full inputs/result
    dicts as JSON, not just final_issuance, so a past run can be inspected
    in detail rather than just its headline figure."""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO credit_history (org_id, field_id, field_type, final_issuance, inputs_json, result_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (org_id, field_id, field_type, float(result["final_issuance"]),
             json.dumps(inputs), json.dumps(result)),
        )
        conn.commit()


def get_credit_history(org_id: str, field_id: str) -> list:
    """Returns this field's past calculate_credits() runs, most recent
    first, each as {'calculated_at', 'final_issuance', 'inputs', 'result'}."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT calculated_at, final_issuance, inputs_json, result_json
            FROM credit_history
            WHERE org_id = ? AND field_id = ?
            ORDER BY calculated_at DESC, id DESC
            """,
            (org_id, field_id),
        ).fetchall()
    return [
        {
            "calculated_at": row["calculated_at"],
            "final_issuance": row["final_issuance"],
            "inputs": json.loads(row["inputs_json"]),
            "result": json.loads(row["result_json"]),
        }
        for row in rows
    ]


def get_portfolio_summary(org_id: str) -> list:
    """One row per registered field belonging to this org — identity/area
    plus its latest calculated credit (final_issuance/calculated_at are
    None if the field has never had Calculate Carbon Credits run) — for a
    cross-field aggregate view spanning both methodology paths."""
    with get_db_connection() as conn:
        field_rows = conn.execute(
            "SELECT field_id, name, district, field_type, area_ha FROM fields "
            "WHERE org_id = ? ORDER BY field_id",
            (org_id,),
        ).fetchall()
        latest_rows = conn.execute(
            """
            SELECT field_id, final_issuance, calculated_at
            FROM credit_history
            WHERE org_id = ? AND id IN (
                SELECT MAX(id) FROM credit_history WHERE org_id = ? GROUP BY field_id
            )
            """,
            (org_id, org_id),
        ).fetchall()
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
            """
            SELECT site_type, timepoint, soc_value_tco2e_ha
            FROM soc_measurements
            WHERE org_id = ? AND field_id = ?
            ORDER BY site_type, timepoint, sample_index
            """,
            (org_id, field_id),
        ).fetchall()
    result = {}
    for row in rows:
        key = (row["site_type"], row["timepoint"])
        result.setdefault(key, []).append(row["soc_value_tco2e_ha"])
    return result


initialize_database()
