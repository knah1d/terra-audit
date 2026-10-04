"""Traceable soil evidence — Phase 3, Part B.7 of
docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md, extended per the Phase 3
follow-up ("Complete soil evidence integration").

Adds sampling plans, strata, individual geolocated soil samples (dates,
depth intervals, bulk density), per-analyte laboratory results (method,
unit, value — supporting multiple lab runs/replicates per sample),
chain-of-custody events, and a REVIEWED EVIDENCE MAPPING
(`soc_evidence_reviews`) that is the actual, source-backed path from
specific sample rows to the calculation engine's `soc_measurements`
input.

The legacy `soc_measurements` table (src.persistence.database.get_soc_measurements/
save_soc_measurements) is UNCHANGED and still readable as a manually-
entered aggregate. It is no longer, however, presented as complete
sampling evidence: `resolved_soc_measurements()` below is now the
function callers (src/carbon/snapshot.py) use to decide the engine's actual
input, and it labels every (site_type, timepoint) cell with its real
source — "reviewed_evidence" (a reviewer explicitly approved a specific
set of sample rows to feed the engine, preserving each sample's raw
value so the engine's own Eq. 70/71 variance-from-replicates
calculation is not short-circuited by a pre-averaged number) or
"legacy_aggregate" (the old manually-entered list, honestly labeled as
not full sampling evidence) or "missing".

`aggregate_from_samples()` remains a naive cross-check/comparison view
ONLY (unchanged) — grouping every sample's value with no review, no
outlier/QA exclusion, and no chain-of-custody check. It is never read
by `resolved_soc_measurements()` or any calculation path; a reviewer
must explicitly adopt specific sample_ids via `record_soc_evidence_review`
for evidence to become an actual engine input.
"""
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from src.persistence.database import get_db_connection
from src.evidence.monitoring import digest

SITE_TYPES = {"project", "control"}
TIMEPOINTS = {"t_start", "t_final"}
MEASUREMENT_METHODS = {"dry_combustion", "wet_oxidation", "loss_on_ignition", "other"}
LAB_ANALYTES = {"soc_percent", "bulk_density_g_cm3", "soc_stock_tco2e_ha", "other"}
CUSTODY_EVENT_TYPES = {"collected", "packaged", "shipped", "received_by_lab", "analyzed", "disposed", "other"}
REVIEW_STATUSES = {"adopted", "rejected"}
MIN_REVIEWED_SAMPLES = 3  # mirrors AlmPracticeValidator.MIN_SOC_SAMPLES — see record_soc_evidence_review


def initialize_tables(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS soil_sampling_plans (
            org_id            TEXT NOT NULL,
            plan_id           TEXT NOT NULL,
            field_id          TEXT NOT NULL,
            name              TEXT NOT NULL,
            description       TEXT NOT NULL DEFAULT '',
            measurement_method TEXT NOT NULL CHECK (measurement_method IN
                               ('dry_combustion', 'wet_oxidation', 'loss_on_ignition', 'other')),
            remeasurement_interval_years REAL,
            created_by        TEXT NOT NULL,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, plan_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_soil_sampling_plans_field ON soil_sampling_plans(org_id, field_id)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS soil_strata (
            org_id      TEXT NOT NULL,
            stratum_id  TEXT NOT NULL,
            plan_id     TEXT NOT NULL,
            name        TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            area_ha     REAL,
            PRIMARY KEY (org_id, stratum_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_soil_strata_plan ON soil_strata(org_id, plan_id)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS soil_samples (
            org_id              TEXT NOT NULL,
            sample_id           TEXT NOT NULL,
            plan_id             TEXT NOT NULL,
            stratum_id          TEXT,
            field_id            TEXT NOT NULL,
            site_type           TEXT NOT NULL CHECK (site_type IN ('project', 'control')),
            timepoint           TEXT NOT NULL CHECK (timepoint IN ('t_start', 't_final')),
            sample_date         TEXT NOT NULL,
            latitude            REAL,
            longitude           REAL,
            depth_top_cm        REAL NOT NULL,
            depth_bottom_cm     REAL NOT NULL,
            bulk_density_g_cm3  REAL,
            soc_percent         REAL,
            soc_value_tco2e_ha  REAL,
            lab_name            TEXT NOT NULL DEFAULT '',
            lab_method          TEXT NOT NULL DEFAULT '',
            chain_of_custody_ref TEXT NOT NULL DEFAULT '',
            notes               TEXT NOT NULL DEFAULT '',
            created_by          TEXT NOT NULL,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, sample_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_soil_samples_plan ON soil_samples(org_id, plan_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_soil_samples_field ON soil_samples(org_id, field_id)"))

    # Per-analyte laboratory results — a sample's baked-in soc_percent/
    # soc_value_tco2e_ha/lab_name/lab_method fields (above) stay exactly
    # as they were (legacy-compatible, still the single "adopted" reading
    # for that sample), but a real lab workflow often produces MULTIPLE
    # dated results per sample (a redo, a QA replicate, a different
    # analyte) each with its own method/unit — this table is additive,
    # not a replacement.
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS soil_lab_results (
            org_id       TEXT NOT NULL,
            result_id    TEXT NOT NULL,
            sample_id    TEXT NOT NULL,
            analyte      TEXT NOT NULL CHECK (analyte IN
                         ('soc_percent', 'bulk_density_g_cm3', 'soc_stock_tco2e_ha', 'other')),
            method       TEXT NOT NULL,
            unit         TEXT NOT NULL,
            value        REAL NOT NULL,
            lab_name     TEXT NOT NULL DEFAULT '',
            analyzed_at  TEXT,
            notes        TEXT NOT NULL DEFAULT '',
            entered_by   TEXT NOT NULL,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, result_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_soil_lab_results_sample ON soil_lab_results(org_id, sample_id)"))

    # Chain-of-custody EVENT LOG — replaces the single free-text
    # chain_of_custody_ref field (kept, unchanged, as a legacy summary)
    # with a real append-only sequence of handling events per sample.
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS soil_custody_events (
            org_id      TEXT NOT NULL,
            event_id    TEXT NOT NULL,
            sample_id   TEXT NOT NULL,
            event_type  TEXT NOT NULL CHECK (event_type IN
                        ('collected', 'packaged', 'shipped', 'received_by_lab', 'analyzed', 'disposed', 'other')),
            event_at    TEXT NOT NULL,
            actor       TEXT NOT NULL DEFAULT '',
            location    TEXT NOT NULL DEFAULT '',
            notes       TEXT NOT NULL DEFAULT '',
            created_by  TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, event_id)
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_soil_custody_events_sample ON soil_custody_events(org_id, sample_id)"))

    # The reviewed evidence mapping: a reviewer's explicit, dated decision
    # that a specific SET of sample rows (by id, values preserved raw —
    # never pre-averaged, so the engine's own Eq. 70/71 variance-from-
    # replicates calculation stays intact) is the calculation input for
    # one (field, site_type, timepoint) cell. Append-only, mirroring
    # src.carbon.calculations.readiness_determinations' pattern exactly:
    # `evidence_fingerprint` scopes each row to the exact evidence state
    # it was decided against (see _samples_scope_fingerprint) so a
    # decision silently stops applying — never is deleted — once that
    # scope's evidence changes (a new sample is added, notably; existing
    # rows are immutable/create-only, so edits are not yet a real path).
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS soc_evidence_reviews (
            id                    TEXT NOT NULL,
            org_id                TEXT NOT NULL,
            field_id              TEXT NOT NULL,
            site_type             TEXT NOT NULL CHECK (site_type IN ('project', 'control')),
            timepoint             TEXT NOT NULL CHECK (timepoint IN ('t_start', 't_final')),
            sample_ids_json       TEXT NOT NULL,
            evidence_fingerprint  TEXT NOT NULL,
            status                TEXT NOT NULL CHECK (status IN ('adopted', 'rejected')),
            reason                TEXT NOT NULL,
            decided_by            TEXT NOT NULL,
            decided_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, id)
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_soc_evidence_reviews_scope "
        "ON soc_evidence_reviews(org_id, field_id, site_type, timepoint)"
    ))


def _uid():
    return uuid.uuid4().hex


# --------------------------------------------------------------------------
# Sampling plans
# --------------------------------------------------------------------------

def create_plan(org_id: str, field_id: str, name: str, description: str, measurement_method: str,
                remeasurement_interval_years: float | None, created_by: str) -> str:
    if measurement_method not in MEASUREMENT_METHODS:
        raise ValueError(f"measurement_method must be one of {sorted(MEASUREMENT_METHODS)}")
    plan_id = _uid()
    with get_db_connection() as conn:
        field_exists = conn.execute(text(
            "SELECT 1 FROM fields WHERE org_id = :org_id AND field_id = :field_id"
        ), {"org_id": org_id, "field_id": field_id}).first()
        if not field_exists:
            raise ValueError(f"Field {field_id!r} not found")
        conn.execute(text("""
            INSERT INTO soil_sampling_plans (org_id, plan_id, field_id, name, description, measurement_method,
                                              remeasurement_interval_years, created_by)
            VALUES (:org_id, :plan_id, :field_id, :name, :description, :measurement_method,
                    :remeasurement_interval_years, :created_by)
        """), {"org_id": org_id, "plan_id": plan_id, "field_id": field_id, "name": name,
               "description": description, "measurement_method": measurement_method,
               "remeasurement_interval_years": remeasurement_interval_years, "created_by": created_by})
        conn.commit()
    return plan_id


def get_plan(org_id: str, plan_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM soil_sampling_plans WHERE org_id = :org_id AND plan_id = :plan_id"
        ), {"org_id": org_id, "plan_id": plan_id}).mappings().fetchone()
    return dict(row) if row else None


def list_plans(org_id: str, field_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text(
            "SELECT * FROM soil_sampling_plans WHERE org_id = :org_id AND field_id = :field_id ORDER BY created_at"
        ), {"org_id": org_id, "field_id": field_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def sampling_evidence_for_field(org_id: str, field_id: str) -> list[dict]:
    """Full provenance in at most five SELECTs, independent of sample count.

    Used by explanation fingerprints only. No aggregate, adopted mapping or
    calculation input is substituted. Every join retains organization scope.
    """
    params = {"o": org_id, "f": field_id}
    with get_db_connection() as conn:
        plans = [dict(r) for r in conn.execute(text(
            "SELECT * FROM soil_sampling_plans WHERE org_id=:o AND field_id=:f"
        ), params).mappings().all()]
        if not plans:
            return []
        by_plan = {p["plan_id"]: p for p in plans}
        for plan in plans:
            plan.update(strata=[], samples=[])
        strata = conn.execute(text("""
            SELECT s.* FROM soil_strata s JOIN soil_sampling_plans p
              ON p.org_id=s.org_id AND p.plan_id=s.plan_id
            WHERE s.org_id=:o AND p.field_id=:f
        """), params).mappings().all()
        for row in strata:
            by_plan[row["plan_id"]]["strata"].append(dict(row))
        samples = conn.execute(text("""
            SELECT s.* FROM soil_samples s JOIN soil_sampling_plans p
              ON p.org_id=s.org_id AND p.plan_id=s.plan_id
            WHERE s.org_id=:o AND s.field_id=:f AND p.field_id=:f
        """), params).mappings().all()
        by_sample = {}
        for row in samples:
            sample = {**dict(row), "lab_results": [], "custody_events": []}
            by_sample[sample["sample_id"]] = sample
            by_plan[sample["plan_id"]]["samples"].append(sample)
        if by_sample:
            for table, key in (("soil_lab_results", "lab_results"), ("soil_custody_events", "custody_events")):
                rows = conn.execute(text(f"""
                    SELECT e.* FROM {table} e JOIN soil_samples s
                      ON s.org_id=e.org_id AND s.sample_id=e.sample_id
                    JOIN soil_sampling_plans p ON p.org_id=s.org_id AND p.plan_id=s.plan_id
                    WHERE e.org_id=:o AND s.field_id=:f AND p.field_id=:f
                """), params).mappings().all()
                for row in rows:
                    by_sample[row["sample_id"]][key].append(dict(row))
    return plans


# --------------------------------------------------------------------------
# Strata
# --------------------------------------------------------------------------

def create_stratum(org_id: str, plan_id: str, name: str, description: str, area_ha: float | None) -> str:
    if get_plan(org_id, plan_id) is None:
        raise ValueError(f"Sampling plan {plan_id!r} not found")
    stratum_id = _uid()
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO soil_strata (org_id, stratum_id, plan_id, name, description, area_ha)
            VALUES (:org_id, :stratum_id, :plan_id, :name, :description, :area_ha)
        """), {"org_id": org_id, "stratum_id": stratum_id, "plan_id": plan_id, "name": name,
               "description": description, "area_ha": area_ha})
        conn.commit()
    return stratum_id


def list_strata(org_id: str, plan_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text(
            "SELECT * FROM soil_strata WHERE org_id = :org_id AND plan_id = :plan_id ORDER BY name"
        ), {"org_id": org_id, "plan_id": plan_id}).mappings().fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Samples
# --------------------------------------------------------------------------

def create_sample(org_id: str, plan_id: str, field_id: str, stratum_id: str | None, site_type: str,
                   timepoint: str, sample_date: str, depth_top_cm: float, depth_bottom_cm: float,
                   latitude: float | None, longitude: float | None, bulk_density_g_cm3: float | None,
                   soc_percent: float | None, soc_value_tco2e_ha: float | None, lab_name: str,
                   lab_method: str, chain_of_custody_ref: str, notes: str, created_by: str) -> str:
    if site_type not in SITE_TYPES:
        raise ValueError(f"site_type must be one of {sorted(SITE_TYPES)}")
    if timepoint not in TIMEPOINTS:
        raise ValueError(f"timepoint must be one of {sorted(TIMEPOINTS)}")
    if depth_bottom_cm <= depth_top_cm:
        raise ValueError("depth_bottom_cm must be greater than depth_top_cm")
    if get_plan(org_id, plan_id) is None:
        raise ValueError(f"Sampling plan {plan_id!r} not found")
    if stratum_id is not None:
        with get_db_connection() as conn:
            exists = conn.execute(text(
                "SELECT 1 FROM soil_strata WHERE org_id = :org_id AND stratum_id = :stratum_id AND plan_id = :plan_id"
            ), {"org_id": org_id, "stratum_id": stratum_id, "plan_id": plan_id}).first()
        if not exists:
            raise ValueError(f"Stratum {stratum_id!r} not found under this plan")
    sample_id = _uid()
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO soil_samples (org_id, sample_id, plan_id, stratum_id, field_id, site_type, timepoint,
                                       sample_date, latitude, longitude, depth_top_cm, depth_bottom_cm,
                                       bulk_density_g_cm3, soc_percent, soc_value_tco2e_ha, lab_name,
                                       lab_method, chain_of_custody_ref, notes, created_by)
            VALUES (:org_id, :sample_id, :plan_id, :stratum_id, :field_id, :site_type, :timepoint,
                    :sample_date, :latitude, :longitude, :depth_top_cm, :depth_bottom_cm,
                    :bulk_density_g_cm3, :soc_percent, :soc_value_tco2e_ha, :lab_name,
                    :lab_method, :chain_of_custody_ref, :notes, :created_by)
        """), {"org_id": org_id, "sample_id": sample_id, "plan_id": plan_id, "stratum_id": stratum_id,
               "field_id": field_id, "site_type": site_type, "timepoint": timepoint, "sample_date": sample_date,
               "latitude": latitude, "longitude": longitude, "depth_top_cm": depth_top_cm,
               "depth_bottom_cm": depth_bottom_cm, "bulk_density_g_cm3": bulk_density_g_cm3,
               "soc_percent": soc_percent, "soc_value_tco2e_ha": soc_value_tco2e_ha, "lab_name": lab_name,
               "lab_method": lab_method, "chain_of_custody_ref": chain_of_custody_ref, "notes": notes,
               "created_by": created_by})
        conn.commit()
    return sample_id


def list_samples(org_id: str, plan_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text(
            "SELECT * FROM soil_samples WHERE org_id = :org_id AND plan_id = :plan_id ORDER BY sample_date"
        ), {"org_id": org_id, "plan_id": plan_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def field_samples(org_id: str, field_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text(
            "SELECT * FROM soil_samples WHERE org_id = :org_id AND field_id = :field_id ORDER BY sample_date"
        ), {"org_id": org_id, "field_id": field_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def aggregate_from_samples(org_id: str, field_id: str) -> dict:
    """A cross-check / comparison view ONLY — groups this field's
    granular samples into the same {(site_type, timepoint): [values]}
    shape src.persistence.database.get_soc_measurements returns, so a reviewer can
    compare the two side by side. NEVER substituted for the actual
    engine input automatically (see this module's docstring)."""
    result: dict = {}
    for s in field_samples(org_id, field_id):
        if s["soc_value_tco2e_ha"] is None:
            continue
        key = (s["site_type"], s["timepoint"])
        result.setdefault(key, []).append(s["soc_value_tco2e_ha"])
    return result


def _get_sample(org_id: str, sample_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM soil_samples WHERE org_id = :org_id AND sample_id = :sample_id"
        ), {"org_id": org_id, "sample_id": sample_id}).mappings().fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------
# Laboratory results (per-analyte, method/unit explicit)
# --------------------------------------------------------------------------

def create_lab_result(org_id: str, sample_id: str, analyte: str, method: str, unit: str, value: float,
                       lab_name: str, analyzed_at: str | None, notes: str, entered_by: str) -> str:
    if analyte not in LAB_ANALYTES:
        raise ValueError(f"analyte must be one of {sorted(LAB_ANALYTES)}")
    if _get_sample(org_id, sample_id) is None:
        raise ValueError(f"Sample {sample_id!r} not found")
    result_id = _uid()
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO soil_lab_results (org_id, result_id, sample_id, analyte, method, unit, value,
                                           lab_name, analyzed_at, notes, entered_by)
            VALUES (:org_id, :result_id, :sample_id, :analyte, :method, :unit, :value,
                    :lab_name, :analyzed_at, :notes, :entered_by)
        """), {"org_id": org_id, "result_id": result_id, "sample_id": sample_id, "analyte": analyte,
               "method": method, "unit": unit, "value": value, "lab_name": lab_name,
               "analyzed_at": analyzed_at, "notes": notes, "entered_by": entered_by})
        conn.commit()
    return result_id


def list_lab_results(org_id: str, sample_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text(
            "SELECT * FROM soil_lab_results WHERE org_id = :org_id AND sample_id = :sample_id ORDER BY created_at"
        ), {"org_id": org_id, "sample_id": sample_id}).mappings().fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Chain of custody
# --------------------------------------------------------------------------

def create_custody_event(org_id: str, sample_id: str, event_type: str, event_at: str, actor: str,
                          location: str, notes: str, created_by: str) -> str:
    if event_type not in CUSTODY_EVENT_TYPES:
        raise ValueError(f"event_type must be one of {sorted(CUSTODY_EVENT_TYPES)}")
    if _get_sample(org_id, sample_id) is None:
        raise ValueError(f"Sample {sample_id!r} not found")
    event_id = _uid()
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO soil_custody_events (org_id, event_id, sample_id, event_type, event_at,
                                              actor, location, notes, created_by)
            VALUES (:org_id, :event_id, :sample_id, :event_type, :event_at,
                    :actor, :location, :notes, :created_by)
        """), {"org_id": org_id, "event_id": event_id, "sample_id": sample_id, "event_type": event_type,
               "event_at": event_at, "actor": actor, "location": location, "notes": notes,
               "created_by": created_by})
        conn.commit()
    return event_id


def list_custody_events(org_id: str, sample_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text(
            "SELECT * FROM soil_custody_events WHERE org_id = :org_id AND sample_id = :sample_id ORDER BY event_at"
        ), {"org_id": org_id, "sample_id": sample_id}).mappings().fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Reviewed evidence mapping (sample rows -> engine soc_measurements input)
# --------------------------------------------------------------------------

def _eligible_sample_ids(org_id: str, field_id: str, site_type: str, timepoint: str) -> list[str]:
    """Every sample currently recorded for this exact (field, site_type,
    timepoint) scope with a usable SOC value — the universe a reviewer
    picks a subset (or all) of, and the set whose membership changing
    (a new sample recorded after a review) drives staleness below."""
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT sample_id FROM soil_samples
            WHERE org_id = :org_id AND field_id = :field_id AND site_type = :site_type
              AND timepoint = :timepoint AND soc_value_tco2e_ha IS NOT NULL
            ORDER BY sample_id
        """), {"org_id": org_id, "field_id": field_id, "site_type": site_type, "timepoint": timepoint}).fetchall()
    return [r[0] for r in rows]


def _samples_scope_fingerprint(org_id: str, field_id: str, site_type: str, timepoint: str,
                                sample_ids: list[str]) -> str:
    """Hashes BOTH the exact selected sample rows' current values (they
    are effectively immutable once created — no update/delete path
    exists yet — so this half is stable) AND the full set of sample ids
    currently eligible for this scope (this half changes the moment a
    NEW sample is recorded for the same field/site_type/timepoint after
    the review, forcing re-review — see record_soc_evidence_review's
    docstring for why deliberately-excluded samples do not, by
    themselves, invalidate a decision)."""
    selected = []
    for sid in sorted(sample_ids):
        s = _get_sample(org_id, sid)
        if s is not None:
            selected.append((s["sample_id"], s["soc_value_tco2e_ha"], s["depth_top_cm"], s["depth_bottom_cm"]))
    payload = {
        "selected": selected,
        "eligible_universe": sorted(_eligible_sample_ids(org_id, field_id, site_type, timepoint)),
    }
    return digest(payload)


def record_soc_evidence_review(org_id: str, field_id: str, site_type: str, timepoint: str,
                                sample_ids: list[str], status: str, reason: str, decided_by: str) -> dict:
    """A reviewer's explicit decision that these specific sample_ids (raw
    values preserved, not pre-averaged) are — or are explicitly NOT — the
    evidence backing this (site_type, timepoint) cell of the engine's
    soc_measurements input. Requires >= MIN_REVIEWED_SAMPLES ids for an
    'adopted' decision (mirrors AlmPracticeValidator/AlmCarbonEngine's own
    MIN_SOC_SAMPLES gate — approving fewer would create a reviewed cell
    the engine itself would reject anyway); a 'rejected' decision may
    reference any number (including zero) to explicitly record that this
    scope's current sample evidence is NOT usable, with a reason."""
    if site_type not in SITE_TYPES:
        raise ValueError(f"site_type must be one of {sorted(SITE_TYPES)}")
    if timepoint not in TIMEPOINTS:
        raise ValueError(f"timepoint must be one of {sorted(TIMEPOINTS)}")
    if status not in REVIEW_STATUSES:
        raise ValueError(f"status must be one of {sorted(REVIEW_STATUSES)}")
    if not reason.strip():
        raise ValueError("reason is required")
    sample_ids = sorted(set(sample_ids))
    for sid in sample_ids:
        s = _get_sample(org_id, sid)
        if s is None:
            raise ValueError(f"Sample {sid!r} not found")
        if s["field_id"] != field_id or s["site_type"] != site_type or s["timepoint"] != timepoint:
            raise ValueError(
                f"Sample {sid!r} does not belong to field {field_id!r}/{site_type}/{timepoint}"
            )
        if s["soc_value_tco2e_ha"] is None:
            raise ValueError(f"Sample {sid!r} has no soc_value_tco2e_ha recorded yet")
    if status == "adopted" and len(sample_ids) < MIN_REVIEWED_SAMPLES:
        raise ValueError(
            f"An adopted review needs at least {MIN_REVIEWED_SAMPLES} sample_ids "
            f"(got {len(sample_ids)}) — the engine itself requires this many replicates per cell."
        )
    fingerprint = _samples_scope_fingerprint(org_id, field_id, site_type, timepoint, sample_ids)
    row_id = _uid()
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO soc_evidence_reviews (id, org_id, field_id, site_type, timepoint, sample_ids_json,
                                               evidence_fingerprint, status, reason, decided_by)
            VALUES (:id, :org_id, :field_id, :site_type, :timepoint, :sample_ids_json,
                    :evidence_fingerprint, :status, :reason, :decided_by)
        """), {"id": row_id, "org_id": org_id, "field_id": field_id, "site_type": site_type,
               "timepoint": timepoint, "sample_ids_json": json.dumps(sample_ids),
               "evidence_fingerprint": fingerprint, "status": status, "reason": reason, "decided_by": decided_by})
        conn.commit()
    return {"id": row_id, "field_id": field_id, "site_type": site_type, "timepoint": timepoint,
            "sample_ids": sample_ids, "status": status, "reason": reason, "decided_by": decided_by}


def latest_soc_evidence_review(org_id: str, field_id: str, site_type: str, timepoint: str) -> dict | None:
    """The most recent review for this cell, annotated with `stale`
    (True when the evidence has moved on since it was decided — see
    _samples_scope_fingerprint) so a caller can tell an out-of-date
    'adopted' row apart from a currently-valid one without silently
    treating either as authoritative. Never deleted — append-only,
    exactly like src.carbon.calculations.readiness_determinations."""
    with get_db_connection() as conn:
        row = conn.execute(text("""
            SELECT * FROM soc_evidence_reviews
            WHERE org_id = :org_id AND field_id = :field_id AND site_type = :site_type AND timepoint = :timepoint
            ORDER BY decided_at DESC LIMIT 1
        """), {"org_id": org_id, "field_id": field_id, "site_type": site_type, "timepoint": timepoint}).mappings().fetchone()
    if row is None:
        return None
    review = dict(row)
    sample_ids = json.loads(review.pop("sample_ids_json"))
    review["sample_ids"] = sample_ids
    current_fingerprint = _samples_scope_fingerprint(org_id, field_id, site_type, timepoint, sample_ids)
    review["stale"] = current_fingerprint != review["evidence_fingerprint"]
    return review


def resolved_soc_measurements(org_id: str, field_id: str) -> dict:
    """THE function callers (src.carbon.snapshot.build_snapshot) use to decide
    the engine's actual soc_measurements input. For each of the 4
    (site_type, timepoint) cells:
      - a current (non-stale), 'adopted' review exists -> use its exact
        sample_ids' raw soc_value_tco2e_ha values, source
        'reviewed_evidence', with full provenance (review id, sample
        ids, decided_by/at, reason).
      - otherwise -> fall back to the legacy manually-entered aggregate
        (src.persistence.database.get_soc_measurements), source 'legacy_aggregate',
        explicitly NOT presented as complete sampling evidence.
      - neither present -> source 'missing', values [].
    """
    from src.persistence.database import get_soc_measurements
    legacy = get_soc_measurements(org_id, field_id)
    result = {}
    for site_type in sorted(SITE_TYPES):
        for timepoint in sorted(TIMEPOINTS):
            key = (site_type, timepoint)
            review = latest_soc_evidence_review(org_id, field_id, site_type, timepoint)
            if review is not None and review["status"] == "adopted" and not review["stale"]:
                values = [_get_sample(org_id, sid)["soc_value_tco2e_ha"] for sid in review["sample_ids"]]
                result[key] = {
                    "values": values, "source": "reviewed_evidence",
                    "review": {k: review[k] for k in
                               ("id", "sample_ids", "reason", "decided_by", "decided_at", "evidence_fingerprint")},
                }
            elif legacy.get(key):
                result[key] = {
                    "values": legacy[key], "source": "legacy_aggregate",
                    "note": "Manually-entered aggregate values — not full sampling-plan/chain-of-custody "
                            "evidence. See soil_evidence.record_soc_evidence_review to formally review and "
                            "adopt traceable sample evidence for this cell instead.",
                }
            else:
                result[key] = {"values": [], "source": "missing"}
    return result
