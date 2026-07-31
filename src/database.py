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
        conn.commit()
    _DB_INITIALIZED = True


def check_cache(field_id: str, window_start: str, window_end: str) -> pd.DataFrame:
    """
    Retrieves cached time-series records keyed to a specific field AND
    analysis window. Returns an empty DataFrame on a cache miss.
    """
    with get_db_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT observation_date AS date, vv, vh, cross_ratio, rvi
            FROM   timeseries_cache
            WHERE  field_id     = ?
              AND  window_start = ?
              AND  window_end   = ?
            ORDER  BY date ASC
            """,
            conn,
            params=(field_id, window_start, window_end),
        )
    return df


def save_cache(
    field_id: str, df: pd.DataFrame, window_start: str, window_end: str
):
    """Commits a batch of EE-fetched observations into the local cache."""
    if df.empty:
        return
    with get_db_connection() as conn:
        rows = [
            (
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
                (field_id, observation_date, window_start, window_end,
                 vv, vh, cross_ratio, rvi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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


def save_alm_practice_schedule(field_id: str, scenario: str, practices: dict):
    """Upserts one baseline/project practice-schedule row for a field."""
    cols = ALM_PRACTICE_COLUMNS
    values = [practices.get(c) for c in cols]
    with get_db_connection() as conn:
        conn.execute(
            f"""
            INSERT INTO alm_practice_schedule (field_id, scenario, {", ".join(cols)})
            VALUES (?, ?, {", ".join("?" for _ in cols)})
            ON CONFLICT (field_id, scenario) DO UPDATE SET
                {", ".join(f"{c} = excluded.{c}" for c in cols)},
                updated_at = CURRENT_TIMESTAMP
            """,
            (field_id, scenario, *values),
        )
        conn.commit()


def get_alm_practice_schedule(field_id: str) -> dict:
    """Returns {'baseline': {...} | None, 'project': {...} | None} for a field."""
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM alm_practice_schedule WHERE field_id = ?", (field_id,)
        ).fetchall()
    result = {"baseline": None, "project": None}
    for row in rows:
        result[row["scenario"]] = {k: row[k] for k in ALM_PRACTICE_COLUMNS}
    return result


def save_soc_measurements(field_id: str, site_type: str, timepoint: str, values: list):
    """Replaces all sample rows for a (field, site_type, timepoint) triple."""
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM soc_measurements WHERE field_id = ? AND site_type = ? AND timepoint = ?",
            (field_id, site_type, timepoint),
        )
        conn.executemany(
            """
            INSERT INTO soc_measurements
                (field_id, site_type, timepoint, sample_index, soc_value_tco2e_ha)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(field_id, site_type, timepoint, i, v) for i, v in enumerate(values)],
        )
        conn.commit()


def get_alm_cumulative_delta(field_id: str) -> float:
    """Cumulative project SOC change (t CO2) since project start, used by
    AlmCarbonEngine.calculate_credits()'s VM0042 Eq. 37/40 ER/CR classification
    indicator. Returns 0.0 for a field with no prior verification recorded."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT alm_cumulative_delta_co2_wp FROM fields WHERE field_id = ?", (field_id,)
        ).fetchone()
    return float(row["alm_cumulative_delta_co2_wp"]) if row and row["alm_cumulative_delta_co2_wp"] is not None else 0.0


def update_alm_cumulative_delta(field_id: str, value: float):
    """Persists the new cumulative total after a successful calculate_credits() call."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE fields SET alm_cumulative_delta_co2_wp = ? WHERE field_id = ?",
            (value, field_id),
        )
        conn.commit()


def get_soc_measurements(field_id: str) -> dict:
    """Returns {(site_type, timepoint): [values...]} for a field."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT site_type, timepoint, soc_value_tco2e_ha
            FROM soc_measurements
            WHERE field_id = ?
            ORDER BY site_type, timepoint, sample_index
            """,
            (field_id,),
        ).fetchall()
    result = {}
    for row in rows:
        key = (row["site_type"], row["timepoint"])
        result.setdefault(key, []).append(row["soc_value_tco2e_ha"])
    return result


initialize_database()
