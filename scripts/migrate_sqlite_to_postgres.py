#!/usr/bin/env python3
"""
One-time migration: copies every table from the local SQLite file
(data/project_store.db) into a Postgres database — Phase 5 of the
multi-tenant plan (.claude/plans/misty-growing-yao.md).

Do NOT run this speculatively. Only run it once a real trigger has
occurred (see the plan's Phase 5 section) and you have a target Postgres
instance ready — this script does not provision infrastructure, only
moves data into an already-reachable database.

Usage:
    python scripts/migrate_sqlite_to_postgres.py \\
        --postgres-url postgresql+psycopg2://user:pass@host:5432/dbname

Safe to re-run: the target schema (via initialize_database()) is created
with CREATE TABLE IF NOT EXISTS, but re-running the copy step against a
non-empty target will duplicate rows — this script is meant for a single
clean cutover, not repeated syncing. If you need to retry, drop and
recreate the target database first.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from sqlalchemy import create_engine, text

# Every table src/database.py or src/ai/dataset_builder.py owns. Order
# matters only in that none of these have real FK constraints to violate,
# so any order is safe — listed in the same order the app's own schema
# functions create them.
TABLES = [
    "organizations", "users", "fields", "timeseries_cache",
    "alm_practice_schedule", "alm_livestock_schedule", "soc_measurements",
    "credit_history", "ai_dataset_rows",
]


def migrate(sqlite_path: Path, postgres_url: str):
    sqlite_engine = create_engine(f"sqlite:///{sqlite_path}")
    postgres_engine = create_engine(postgres_url)

    # Ensure the target schema exists (final shape, no ALTER-TABLE history
    # to replay — see src.database._init_postgres). Import here, not at
    # module level, so this script works even before DATABASE_URL is set
    # anywhere else in the process.
    os.environ["DATABASE_URL"] = postgres_url
    import src.database as db
    db._ENGINE = postgres_engine  # reuse the engine we already created
    db._DB_INITIALIZED = False
    db.initialize_database()

    # ai_dataset_rows isn't created by initialize_database() — it's owned
    # by src.ai.dataset_builder and created lazily on first use. Ensure it
    # exists in the target too, or the DELETE/copy loop below fails on it.
    from src.ai.dataset_builder import _ensure_ai_tables
    with db.get_db_connection() as conn:
        _ensure_ai_tables(conn)
        conn.commit()

    print(f"Source: {sqlite_path}")
    print(f"Target: {postgres_url.split('@')[-1] if '@' in postgres_url else postgres_url}")
    print()

    # initialize_database() seeds a 'default' organizations row into a
    # fresh Postgres target — which then collides with that same row
    # coming from the source SQLite file. Clear every target table first
    # so the copy below is the sole source of truth, matching this
    # script's "single clean cutover" contract (found by actually running
    # this against a live Postgres instance, not assumed).
    with postgres_engine.begin() as pconn:
        for table in reversed(TABLES):
            pconn.execute(text(f"DELETE FROM {table}"))

    results = []
    with sqlite_engine.connect() as sconn:
        for table in TABLES:
            exists = sconn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
                {"t": table},
            ).fetchone()
            if not exists:
                results.append((table, 0, 0, "source table absent, skipped"))
                continue

            # credit_history.id is GENERATED ALWAYS AS IDENTITY on the
            # Postgres side (see src.database._init_postgres) — unlike
            # SQLite's AUTOINCREMENT, Postgres rejects an explicit id value
            # on insert by default. Nothing else has a foreign key into
            # this column, so dropping it and letting Postgres assign fresh
            # ids is safe — insert in the original id order so relative
            # recency (used by ORDER BY id DESC / MAX(id) elsewhere) is
            # preserved under the new ids too.
            order_by = " ORDER BY id ASC" if table == "credit_history" else ""
            df = pd.read_sql_query(text(f"SELECT * FROM {table}{order_by}"), sconn)
            source_count = len(df)
            if table == "credit_history" and "id" in df.columns:
                df = df.drop(columns=["id"])

            if not df.empty:
                with postgres_engine.begin() as pconn:
                    df.to_sql(table, pconn, if_exists="append", index=False)

            with postgres_engine.connect() as pconn:
                dest_count = pconn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()

            status = "OK" if source_count == dest_count else "MISMATCH"
            results.append((table, source_count, dest_count, status))

    print(f"{'table':<28} {'source':>8} {'dest':>8}   status")
    print("-" * 60)
    any_mismatch = False
    for table, src_n, dst_n, status in results:
        print(f"{table:<28} {src_n:>8} {dst_n:>8}   {status}")
        if status not in ("OK", "source table absent, skipped"):
            any_mismatch = True

    print()
    if any_mismatch:
        print("MISMATCH detected — do not cut production over to this target "
              "until every row count matches. Investigate before proceeding.")
        sys.exit(1)
    else:
        print("All row counts match. Migration completed successfully.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path", default=str(Path(__file__).parent.parent / "data" / "project_store.db"),
        help="Path to the source SQLite file (default: data/project_store.db)",
    )
    parser.add_argument(
        "--postgres-url", required=True,
        help="Target Postgres URL, e.g. postgresql+psycopg2://user:pass@host:5432/dbname",
    )
    args = parser.parse_args()
    migrate(Path(args.sqlite_path), args.postgres_url)


if __name__ == "__main__":
    main()
