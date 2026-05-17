import sqlite3
import json
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "project_store.db"

def get_db_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fields (
                field_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                district TEXT NOT NULL,
                geojson_geometry TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS timeseries_cache (
                field_id TEXT,
                observation_date TEXT,
                vv REAL,
                vh REAL,
                cross_ratio REAL,
                rvi REAL,
                PRIMARY KEY (field_id, observation_date)
            )
        """)
        conn.commit()

def check_cache(field_id: str) -> pd.DataFrame:
    """Retrieves cached records to prevent redundant cloud hits."""
    with get_db_connection() as conn:
        df = pd.read_sql_query(
            "SELECT observation_date as date, vv, vh, cross_ratio, rvi FROM timeseries_cache WHERE field_id = ? ORDER BY date ASC",
            conn, params=(field_id,)
        )
    return df

def save_cache(field_id: str, df: pd.DataFrame):
    """Commits fresh cloud fetches safely into the local cache repository."""
    if df.empty:
        return
    with get_db_connection() as conn:
        for _, row in df.iterrows():
            conn.execute("""
                INSERT OR REPLACE INTO timeseries_cache (field_id, observation_date, vv, vh, cross_ratio, rvi)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (field_id, row['date'], row['vv'], row['vh'], row['cross_ratio'], row['rvi']))
        conn.commit()

initialize_database()
