"""
Builds a labeled dataset for AI baseline training from the existing
threshold-gate pipeline's own output.

IMPORTANT — label provenance: there is no independently verified AWD ground
truth anywhere in this project. The `label` column here is synthesized from
AdaptiveAWDGate's own z-score/diff threshold output (is_flooded /
drydown_event). Any model trained on this dataset is learning to reproduce
the threshold gate's decisions, not real-world irrigation truth — downstream
metrics should be read as model-vs-threshold-gate agreement, not accuracy.
"""

import datetime

import pandas as pd

from src.database import get_db_connection
from src.threshold_gate import AdaptiveAWDGate

DATASET_TABLE = "ai_dataset_rows"

_DATASET_COLUMNS = [
    "field_id", "district", "area_ha", "window_start", "window_end", "date",
    "vv", "vh", "cross_ratio", "rvi", "vv_smoothed", "vh_smoothed",
    "vv_zscore", "vv_diff", "is_flooded", "drydown_event",
    "is_sowing", "is_harvest", "vh_diff", "label", "built_at",
]


def _ensure_ai_tables(conn) -> None:
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {DATASET_TABLE} (
            field_id     TEXT,
            district     TEXT,
            area_ha      REAL,
            window_start TEXT,
            window_end   TEXT,
            date         TEXT,
            vv           REAL,
            vh           REAL,
            cross_ratio  REAL,
            rvi          REAL,
            vv_smoothed  REAL,
            vh_smoothed  REAL,
            vv_zscore    REAL,
            vv_diff      REAL,
            is_flooded   INTEGER,
            drydown_event INTEGER,
            is_sowing    INTEGER,
            is_harvest   INTEGER,
            vh_diff      REAL,
            label        TEXT,
            built_at     TEXT,
            PRIMARY KEY (field_id, window_start, window_end, date)
        )
    """)
    conn.commit()


def _fetch_cache_groups() -> pd.DataFrame:
    """All raw cached observations joined with their field's district/area."""
    with get_db_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT t.field_id, f.district, f.area_ha,
                   t.window_start, t.window_end,
                   t.observation_date AS date,
                   t.vv, t.vh, t.cross_ratio, t.rvi
            FROM   timeseries_cache t
            JOIN   fields f ON f.field_id = t.field_id
            ORDER  BY t.field_id, t.window_start, t.window_end, t.observation_date
            """,
            conn,
        )


def _label_row(row) -> str:
    if row["drydown_event"] == 1:
        return "drydown"
    if row["is_flooded"] == 1:
        return "flooded"
    return "dry"


def build_dataset(gate: AdaptiveAWDGate | None = None) -> pd.DataFrame:
    """
    Replays the same gate.extract_phenology(gate.analyze_irrigation_behavior(df))
    chain app.py uses, independently per (field_id, window_start, window_end)
    group — the z-score baseline is field/window-relative, matching how the
    app computes it for a single run. Returns the combined labeled frame;
    does not persist (see save_dataset).
    """
    gate = gate or AdaptiveAWDGate()
    raw = _fetch_cache_groups()
    if raw.empty:
        return pd.DataFrame(columns=_DATASET_COLUMNS)

    built_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    groups_out = []
    for (field_id, window_start, window_end), group in raw.groupby(
        ["field_id", "window_start", "window_end"], sort=False
    ):
        district = group["district"].iloc[0]
        area_ha = group["area_ha"].iloc[0]

        processed = gate.extract_phenology(
            gate.analyze_irrigation_behavior(
                group[["date", "vv", "vh", "cross_ratio", "rvi"]].reset_index(drop=True)
            )
        )
        processed["label"] = processed.apply(_label_row, axis=1)
        processed["field_id"] = field_id
        processed["district"] = district
        processed["area_ha"] = area_ha
        processed["window_start"] = window_start
        processed["window_end"] = window_end
        processed["built_at"] = built_at
        groups_out.append(processed)

    combined = pd.concat(groups_out, ignore_index=True)
    for col in _DATASET_COLUMNS:
        if col not in combined.columns:
            combined[col] = None
    return combined[_DATASET_COLUMNS]


def save_dataset(df: pd.DataFrame) -> None:
    """Full rebuild: the dataset is a pure function of timeseries_cache plus
    gate parameters, so replacing it wholesale avoids incremental-merge bugs
    if the gate's thresholds are ever recalibrated."""
    with get_db_connection() as conn:
        _ensure_ai_tables(conn)
        conn.execute(f"DELETE FROM {DATASET_TABLE}")
        if not df.empty:
            df[_DATASET_COLUMNS].to_sql(DATASET_TABLE, conn, if_exists="append", index=False)
        conn.commit()


def load_dataset() -> pd.DataFrame:
    with get_db_connection() as conn:
        _ensure_ai_tables(conn)
        return pd.read_sql_query(f"SELECT * FROM {DATASET_TABLE}", conn)


def main():
    df = build_dataset()
    save_dataset(df)
    n_groups = df[["field_id", "window_start", "window_end"]].drop_duplicates().shape[0] if not df.empty else 0
    print(f"Built dataset: {len(df)} rows across {n_groups} field/window group(s).")
    if not df.empty:
        print("Label distribution:")
        print(df["label"].value_counts().to_string())


if __name__ == "__main__":
    main()
