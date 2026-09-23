"""Traceable soil evidence — Phase 3, Part B.7 of
docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md.

Adds sampling plans, strata, and individual geolocated soil samples
(dates, depth intervals, bulk density, lab method/results, chain of
custody) ON TOP of the existing `soc_measurements` table — that table
is UNCHANGED and remains exactly what src/carbon_calculator_alm.py's
calculate_credits() actually reads (an aggregate list of values per
(site_type, timepoint)). This module does not replace it or feed it
automatically: recomputing the engine's aggregate input FROM granular
samples (e.g. per-stratum weighting) is a real quantification decision
this phase does not make unreviewed. `aggregate_from_samples()` exists
only as a cross-check/comparison view, explicitly labeled as such —
never silently substituted for the manually-entered aggregate.

This keeps existing aggregate `soc_measurements` rows usable as legacy
data (nothing here requires migrating them) while making it possible to
attach real traceability to a NEW calculation going forward. See
src/snapshot.py, which embeds both the aggregate values the engine used
AND (if present) this field's sampling plan/samples into the snapshot,
clearly labeled apart.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from src.database import get_db_connection

SITE_TYPES = {"project", "control"}
TIMEPOINTS = {"t_start", "t_final"}
MEASUREMENT_METHODS = {"dry_combustion", "wet_oxidation", "loss_on_ignition", "other"}


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
    shape src.database.get_soc_measurements returns, so a reviewer can
    compare the two side by side. NEVER substituted for the actual
    engine input automatically (see this module's docstring)."""
    result: dict = {}
    for s in field_samples(org_id, field_id):
        if s["soc_value_tco2e_ha"] is None:
            continue
        key = (s["site_type"], s["timepoint"])
        result.setdefault(key, []).append(s["soc_value_tco2e_ha"])
    return result
