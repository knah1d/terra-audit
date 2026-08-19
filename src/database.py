import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from src.issuance import NonIssuableResultError, result_is_issuable

DB_PATH = Path(__file__).parent.parent / "data" / "project_store.db"
_DB_INITIALIZED = False
_ENGINE = None


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
        conn.commit()
    _DB_INITIALIZED = True


def _init_sqlite(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS fields (
            field_id         TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            district         TEXT NOT NULL,
            geojson_geometry TEXT NOT NULL,
            area_ha          REAL,
            field_type       TEXT NOT NULL DEFAULT 'rice_awd',
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    # Migration: add area_ha/field_type to existing DBs that predate these columns
    for stmt in (
        "ALTER TABLE fields ADD COLUMN area_ha REAL",
        "ALTER TABLE fields ADD COLUMN field_type TEXT NOT NULL DEFAULT 'rice_awd'",
        # Cumulative ALM SOC indicator (VM0042 Eq. 37/40's I(deltaCO2wp) is
        # defined on the cumulative change since project start, not a single
        # verification period) — carbon_calculator_alm.AlmCarbonEngine.calculate_credits()
        "ALTER TABLE fields ADD COLUMN alm_cumulative_delta_co2_wp REAL DEFAULT 0.0",
    ):
        try:
            conn.execute(text(stmt))
        except Exception:
            pass

    # PK covers field + observation date + the exact analysis window.
    # This prevents a 2024-01-15 observation overwriting a 2025-01-15
    # observation that shares the same calendar date string.
    conn.execute(text("""
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
    """))
    # Migration: add window columns to old single-window schema if absent
    for col in ("window_start TEXT", "window_end TEXT"):
        try:
            conn.execute(text(f"ALTER TABLE timeseries_cache ADD COLUMN {col}"))
        except Exception:
            pass  # Column already exists

    # VM0042 ALM field type — baseline vs project practice schedule
    # (Table 4 subset: crop planting/harvesting, fertilizer, tillage/residue).
    # One row per (field_id, scenario); columns left NULL where not applicable.
    conn.execute(text("""
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
    """))
    # Migration: crop_yield_t_ha added later (VMD0054 production-decline
    # leakage screening — see carbon_calculator_alm.py) for DBs that predate it
    try:
        conn.execute(text("ALTER TABLE alm_practice_schedule ADD COLUMN crop_yield_t_ha REAL"))
    except Exception:
        pass

    # VM0042 ALM field type — integrated crop-livestock schedule (§8.2.6/
    # §8.2.7/§8.2.10, Pasture/Range/Paddock scope — see AlmCarbonEngine's
    # LIVESTOCK_TABLE docstring). One row per (field_id, scenario,
    # livestock_type); zero-population entries are never stored.
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS alm_livestock_schedule (
            field_id            TEXT NOT NULL,
            scenario            TEXT NOT NULL CHECK (scenario IN ('baseline', 'project')),
            livestock_type      TEXT NOT NULL,
            population_head     REAL NOT NULL,
            productivity_system TEXT NOT NULL CHECK (productivity_system IN ('high', 'low')),
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (field_id, scenario, livestock_type)
        )
    """))

    # VM0042 ALM field type — SOC lab measurements (Quantification Approach 2).
    # Paired project-site vs baseline-control-site samples at two timepoints,
    # feeding Eqs 3-5/46-47 (stock change) and Eqs 70-71/74 (uncertainty).
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS soc_measurements (
            field_id            TEXT NOT NULL,
            site_type           TEXT NOT NULL CHECK (site_type IN ('project', 'control')),
            timepoint           TEXT NOT NULL CHECK (timepoint IN ('t_start', 't_final')),
            sample_index        INTEGER NOT NULL,
            soc_value_tco2e_ha  REAL NOT NULL,
            measured_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (field_id, site_type, timepoint, sample_index)
        )
    """))

    # Persisted log of every "Calculate Carbon Credits" run — one row per
    # click, for either methodology path. inputs_json/result_json store
    # the full calculate_credits() call so a past run can be inspected in
    # detail, not just its headline final_issuance figure.
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS credit_history (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            field_id       TEXT NOT NULL,
            field_type     TEXT NOT NULL,
            calculated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            final_issuance REAL NOT NULL,
            inputs_json    TEXT NOT NULL,
            result_json    TEXT NOT NULL
        )
    """))

    # ---------------------------------------------------------------
    # Multi-tenancy foundation (Phase 0 of the multi-tenant plan).
    # ---------------------------------------------------------------
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS organizations (
            org_id     TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            plan       TEXT NOT NULL DEFAULT 'trial',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(text("""
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
    """))
    # Legacy/default org — gives every pre-existing row (and Phase 2's
    # org_id backfill) a home without forcing an immediate data migration.
    conn.execute(text(
        "INSERT OR IGNORE INTO organizations (org_id, name, plan) "
        "VALUES ('default', 'Legacy Operator', 'legacy')"
    ))

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
            conn.execute(text(
                f"ALTER TABLE {_table} ADD COLUMN org_id TEXT NOT NULL DEFAULT 'default'"
            ))
        except Exception:
            pass

    # A supplementary UNIQUE INDEX on (org_id, field_id) is NOT sufficient
    # on its own — SQLite still enforces each table's original PRIMARY KEY
    # (field_id alone, or field_id+scenario, etc.) independently, so a
    # second org registering the same field_id raised "UNIQUE constraint
    # failed" at the DB level regardless of any index added on top. ALTER
    # TABLE can't redefine a PRIMARY KEY in SQLite, so this rebuilds each
    # affected table (standard SQLite create-new/copy/drop-old/rename
    # pattern) with org_id folded into the real PK. Guarded by checking
    # whether org_id is already part of the PK, so this runs at most once.
    _pk_rebuilds = {
        "fields": (
            """
            CREATE TABLE fields (
                org_id           TEXT NOT NULL DEFAULT 'default',
                field_id         TEXT NOT NULL,
                name             TEXT NOT NULL,
                district         TEXT NOT NULL,
                geojson_geometry TEXT NOT NULL,
                area_ha          REAL,
                field_type       TEXT NOT NULL DEFAULT 'rice_awd',
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                alm_cumulative_delta_co2_wp REAL DEFAULT 0.0,
                PRIMARY KEY (org_id, field_id)
            )
            """,
            "org_id, field_id, name, district, geojson_geometry, area_ha, "
            "field_type, created_at, alm_cumulative_delta_co2_wp",
        ),
        "timeseries_cache": (
            """
            CREATE TABLE timeseries_cache (
                org_id           TEXT NOT NULL DEFAULT 'default',
                field_id         TEXT,
                observation_date TEXT,
                window_start     TEXT,
                window_end       TEXT,
                vv               REAL,
                vh               REAL,
                cross_ratio      REAL,
                rvi              REAL,
                PRIMARY KEY (org_id, field_id, observation_date, window_start, window_end)
            )
            """,
            "org_id, field_id, observation_date, window_start, window_end, "
            "vv, vh, cross_ratio, rvi",
        ),
        "alm_practice_schedule": (
            """
            CREATE TABLE alm_practice_schedule (
                org_id                  TEXT NOT NULL DEFAULT 'default',
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
                PRIMARY KEY (org_id, field_id, scenario)
            )
            """,
            "org_id, field_id, scenario, crop_type, crop_rotation, cover_crops, "
            "intercropping, tillage, tillage_depth_cm, residue_removed, "
            "residue_burned_kg_ha, synthetic_n_rate_kg_ha, organic_n_rate_kg_ha, "
            "n_fixing_species, n_fixing_dry_matter_kg_ha, fuel_use_l_ha, "
            "crop_yield_t_ha, updated_at",
        ),
        "alm_livestock_schedule": (
            """
            CREATE TABLE alm_livestock_schedule (
                org_id              TEXT NOT NULL DEFAULT 'default',
                field_id            TEXT NOT NULL,
                scenario            TEXT NOT NULL CHECK (scenario IN ('baseline', 'project')),
                livestock_type      TEXT NOT NULL,
                population_head     REAL NOT NULL,
                productivity_system TEXT NOT NULL CHECK (productivity_system IN ('high', 'low')),
                updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (org_id, field_id, scenario, livestock_type)
            )
            """,
            "org_id, field_id, scenario, livestock_type, population_head, "
            "productivity_system, updated_at",
        ),
        "soc_measurements": (
            """
            CREATE TABLE soc_measurements (
                org_id              TEXT NOT NULL DEFAULT 'default',
                field_id            TEXT NOT NULL,
                site_type           TEXT NOT NULL CHECK (site_type IN ('project', 'control')),
                timepoint           TEXT NOT NULL CHECK (timepoint IN ('t_start', 't_final')),
                sample_index        INTEGER NOT NULL,
                soc_value_tco2e_ha  REAL NOT NULL,
                measured_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (org_id, field_id, site_type, timepoint, sample_index)
            )
            """,
            "org_id, field_id, site_type, timepoint, sample_index, "
            "soc_value_tco2e_ha, measured_at",
        ),
    }
    for _table, (_create_sql, _cols) in _pk_rebuilds.items():
        _pk_cols = [
            r[1] for r in conn.execute(text(f"PRAGMA table_info({_table})")).fetchall()
            if r[5] > 0
        ]
        if "org_id" in _pk_cols:
            continue  # already migrated
        conn.execute(text(f"ALTER TABLE {_table} RENAME TO {_table}_old"))
        conn.execute(text(_create_sql))
        conn.execute(text(f"INSERT INTO {_table} ({_cols}) SELECT {_cols} FROM {_table}_old"))
        conn.execute(text(f"DROP TABLE {_table}_old"))

    # credit_history doesn't need this treatment — its PK is a plain
    # AUTOINCREMENT id, not a natural key built from field_id, so it was
    # never at risk of the cross-org collision the tables above had.
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_fields_org ON fields(org_id)"))
    for _table in (
        "timeseries_cache", "alm_practice_schedule",
        "alm_livestock_schedule", "soc_measurements", "credit_history",
    ):
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{_table}_org ON {_table}(org_id)"))

    _init_shared_extra_tables(conn)


def _init_shared_extra_tables(conn):
    """Tables added for the FastAPI backend (.claude/plans/misty-growing-yao.md
    Part A) — identical DDL on both backends since neither predates org_id
    or needs an ALTER-TABLE migration history, so this one function serves
    both _init_sqlite and _init_postgres rather than being duplicated."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS commit_idempotency_keys (
            org_id          TEXT NOT NULL,
            field_id        TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            credit_history_id INTEGER,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, field_id, idempotency_key)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS background_jobs (
            job_id      TEXT PRIMARY KEY,
            org_id      TEXT NOT NULL,
            job_type    TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'done', 'error')),
            result_json TEXT,
            error       TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_background_jobs_org ON background_jobs(org_id)"))

    # Self-serve org signup (OTP email verification) — no org_id column:
    # this table holds PRE-org state (a signup that hasn't become a real
    # org/user yet), so it deliberately sits outside the multi-tenancy
    # pattern every other table here follows.
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS pending_registrations (
            registration_id TEXT PRIMARY KEY,
            email           TEXT NOT NULL,
            org_name        TEXT NOT NULL,
            password_hash   TEXT NOT NULL,
            otp_hash        TEXT NOT NULL,
            attempt_count   INTEGER NOT NULL DEFAULT 0,
            max_attempts    INTEGER NOT NULL DEFAULT 5,
            expires_at      TIMESTAMP NOT NULL,
            last_sent_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            consumed_at     TIMESTAMP
        )
    """))
    conn.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_reg_email ON pending_registrations(email)"
    ))


def _init_postgres(conn):
    """Fresh, final-shape schema — no ALTER-TABLE migration history to
    replay, since a new Postgres deployment starts empty and is populated
    via scripts/migrate_sqlite_to_postgres.py, not by accumulating
    migrations the way the long-lived local SQLite file did."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS organizations (
            org_id     TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            plan       TEXT NOT NULL DEFAULT 'trial',
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       TEXT PRIMARY KEY,
            org_id        TEXT NOT NULL,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'analyst'
                          CHECK (role IN ('admin', 'analyst', 'viewer')),
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TIMESTAMPTZ DEFAULT now(),
            last_login_at TIMESTAMPTZ
        )
    """))
    conn.execute(text(
        "INSERT INTO organizations (org_id, name, plan) "
        "VALUES ('default', 'Legacy Operator', 'legacy') "
        "ON CONFLICT (org_id) DO NOTHING"
    ))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS fields (
            org_id           TEXT NOT NULL DEFAULT 'default',
            field_id         TEXT NOT NULL,
            name             TEXT NOT NULL,
            district         TEXT NOT NULL,
            geojson_geometry TEXT NOT NULL,
            area_ha          DOUBLE PRECISION,
            field_type       TEXT NOT NULL DEFAULT 'rice_awd',
            created_at       TIMESTAMPTZ DEFAULT now(),
            alm_cumulative_delta_co2_wp DOUBLE PRECISION DEFAULT 0.0,
            PRIMARY KEY (org_id, field_id)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS timeseries_cache (
            org_id           TEXT NOT NULL DEFAULT 'default',
            field_id         TEXT,
            observation_date TEXT,
            window_start     TEXT,
            window_end       TEXT,
            vv               DOUBLE PRECISION,
            vh               DOUBLE PRECISION,
            cross_ratio      DOUBLE PRECISION,
            rvi              DOUBLE PRECISION,
            PRIMARY KEY (org_id, field_id, observation_date, window_start, window_end)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS alm_practice_schedule (
            org_id                  TEXT NOT NULL DEFAULT 'default',
            field_id                TEXT NOT NULL,
            scenario                TEXT NOT NULL CHECK (scenario IN ('baseline', 'project')),
            crop_type               TEXT,
            crop_rotation           INTEGER,
            cover_crops             INTEGER,
            intercropping           INTEGER,
            tillage                 INTEGER,
            tillage_depth_cm        DOUBLE PRECISION,
            residue_removed         INTEGER,
            residue_burned_kg_ha    DOUBLE PRECISION,
            synthetic_n_rate_kg_ha  DOUBLE PRECISION,
            organic_n_rate_kg_ha    DOUBLE PRECISION,
            n_fixing_species        INTEGER,
            n_fixing_dry_matter_kg_ha DOUBLE PRECISION,
            fuel_use_l_ha           DOUBLE PRECISION,
            crop_yield_t_ha         DOUBLE PRECISION,
            updated_at              TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (org_id, field_id, scenario)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS alm_livestock_schedule (
            org_id              TEXT NOT NULL DEFAULT 'default',
            field_id            TEXT NOT NULL,
            scenario            TEXT NOT NULL CHECK (scenario IN ('baseline', 'project')),
            livestock_type      TEXT NOT NULL,
            population_head     DOUBLE PRECISION NOT NULL,
            productivity_system TEXT NOT NULL CHECK (productivity_system IN ('high', 'low')),
            updated_at          TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (org_id, field_id, scenario, livestock_type)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS soc_measurements (
            org_id              TEXT NOT NULL DEFAULT 'default',
            field_id            TEXT NOT NULL,
            site_type           TEXT NOT NULL CHECK (site_type IN ('project', 'control')),
            timepoint           TEXT NOT NULL CHECK (timepoint IN ('t_start', 't_final')),
            sample_index        INTEGER NOT NULL,
            soc_value_tco2e_ha  DOUBLE PRECISION NOT NULL,
            measured_at         TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (org_id, field_id, site_type, timepoint, sample_index)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS credit_history (
            id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            org_id         TEXT NOT NULL DEFAULT 'default',
            field_id       TEXT NOT NULL,
            field_type     TEXT NOT NULL,
            calculated_at  TIMESTAMPTZ DEFAULT now(),
            final_issuance DOUBLE PRECISION NOT NULL,
            inputs_json    TEXT NOT NULL,
            result_json    TEXT NOT NULL
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_fields_org ON fields(org_id)"))
    for _table in (
        "timeseries_cache", "alm_practice_schedule",
        "alm_livestock_schedule", "soc_measurements", "credit_history",
    ):
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{_table}_org ON {_table}(org_id)"))

    _init_shared_extra_tables(conn)


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
    with get_db_connection() as conn:
        df = pd.read_sql_query(
            text("""
                SELECT observation_date AS date, vv, vh, cross_ratio, rvi
                FROM   timeseries_cache
                WHERE  org_id       = :org_id
                  AND  field_id     = :field_id
                  AND  window_start = :window_start
                  AND  window_end   = :window_end
                ORDER  BY date ASC
            """),
            conn,
            params={"org_id": org_id, "field_id": field_id,
                    "window_start": window_start, "window_end": window_end},
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
            for _, row in df.iterrows()
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
        conn.execute(
            text(f"""
                {insert_stmt}
                    (org_id, field_id, observation_date, window_start, window_end,
                     vv, vh, cross_ratio, rvi)
                VALUES (:org_id, :field_id, :observation_date, :window_start, :window_end,
                        :vv, :vh, :cross_ratio, :rvi)
                {conflict_clause}
            """),
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
        for table in (
            "fields", "timeseries_cache", "alm_practice_schedule",
            "alm_livestock_schedule", "soc_measurements", "credit_history",
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
    first, each as {'calculated_at', 'final_issuance', 'inputs', 'result'}."""
    with get_db_connection() as conn:
        rows = conn.execute(
            text("""
                SELECT calculated_at, final_issuance, inputs_json, result_json
                FROM credit_history
                WHERE org_id = :org_id AND field_id = :field_id
                ORDER BY calculated_at DESC, id DESC
            """),
            {"org_id": org_id, "field_id": field_id},
        ).mappings().fetchall()
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
    issuance rows. See src/issuance.py.
    """
    issuable, block_reason = result_is_issuable(result)
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
            text("SELECT job_id, job_type, status, result_json, error, created_at, finished_at "
                 "FROM background_jobs WHERE org_id = :org_id AND job_id = :job_id"),
            {"org_id": org_id, "job_id": job_id},
        ).mappings().fetchone()
    if row is None:
        return None
    result = dict(row)
    result["result"] = json.loads(result.pop("result_json")) if result["result_json"] else None
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


initialize_database()
