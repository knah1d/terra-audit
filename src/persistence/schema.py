"""Shared SQL schema and existing SQLite/Postgres migrations. No import-time DDL."""
from sqlalchemy import text


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
            limestone_applied_t_ha  REAL,
            dolomite_applied_t_ha   REAL,
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
    # Migration: liming fields added later (VM0042 §8.2.4/§8.5.3 Eq. 8/9/53
    # — see carbon_calculator_alm.py's _liming_co2) for DBs that predate them
    for _col in ("limestone_applied_t_ha", "dolomite_applied_t_ha"):
        try:
            conn.execute(text(f"ALTER TABLE alm_practice_schedule ADD COLUMN {_col} REAL"))
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
                limestone_applied_t_ha  REAL,
                dolomite_applied_t_ha   REAL,
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

    # Observed land use ("Field Type" in the UI), separate from field_type
    # (the methodology). Added after the PK rebuild above so that rebuild's
    # fixed column list can't drop them. Nullable: fields registered before
    # this existed have no land use recorded.
    for _col in ("land_use TEXT", "land_use_source TEXT", "land_use_evidence TEXT"):
        try:
            conn.execute(text(f"ALTER TABLE fields ADD COLUMN {_col}"))
        except Exception:
            pass

    # Safety net: a DB already past the org_id-in-PK rebuild above (so the
    # loop's `continue` skipped it) still needs the liming columns if it
    # predates them.
    for _col in ("limestone_applied_t_ha", "dolomite_applied_t_ha"):
        try:
            conn.execute(text(f"ALTER TABLE alm_practice_schedule ADD COLUMN {_col} REAL"))
        except Exception:
            pass

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
    # background_jobs' schema (including its indexes) is owned by
    # src.jobs.queue.initialize_tables now (Phase 4 durable queue rewrite),
    # called separately from initialize_database() since it needs real
    # migration logic (a pre-Phase-4 table rebuild/ALTER), not a plain
    # CREATE TABLE IF NOT EXISTS the way every other table here is.

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
            land_use         TEXT,
            land_use_source  TEXT,
            land_use_evidence TEXT,
            PRIMARY KEY (org_id, field_id)
        )
    """))
    # Migration: observed land use added later — IF NOT EXISTS makes this
    # safely re-runnable on DBs that predate it.
    for _col in ("land_use", "land_use_source", "land_use_evidence"):
        conn.execute(text(f"ALTER TABLE fields ADD COLUMN IF NOT EXISTS {_col} TEXT"))
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
            limestone_applied_t_ha  DOUBLE PRECISION,
            dolomite_applied_t_ha   DOUBLE PRECISION,
            updated_at              TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (org_id, field_id, scenario)
        )
    """))
    # Migration: liming fields added later (VM0042 §8.2.4/§8.5.3 Eq. 8/9/53)
    # for DBs that predate them — IF NOT EXISTS makes this safely re-runnable.
    conn.execute(text(
        "ALTER TABLE alm_practice_schedule ADD COLUMN IF NOT EXISTS limestone_applied_t_ha DOUBLE PRECISION"
    ))
    conn.execute(text(
        "ALTER TABLE alm_practice_schedule ADD COLUMN IF NOT EXISTS dolomite_applied_t_ha DOUBLE PRECISION"
    ))
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
