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
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
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


initialize_database()
