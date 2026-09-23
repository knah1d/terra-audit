"""Persistent methodology registry — documents, corrections, bundles, the
requirements matrix, and project-specific applicability.

Addresses docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md Phase 1, gap #1:
"src/readiness.py currently treats a matching field-type/pathway mapping
as methodology applicability... Replace this with actual conditions and
supporting evidence." This module is the persisted source of truth for
WHAT a requirement means (its source document/section, what evidence
satisfies it, whether this codebase implements it, and who may decide
it); src/readiness.py stays the place that evaluates whether a SPECIFIC
project/calculation currently satisfies it.

This is reference data, not tenant data — global across every
organization, the same way `src.field_types.registry.FIELD_TYPES` is a
shared in-memory registry. Unlike that one, this needs real persistence
(document hashes must be verifiable later, bundles must be frozen into
calculation snapshots and stay stable even if the seed data below is
edited in a future release) — so it lives in the database, seeded
idempotently from the Python manifest below at startup. Editing the
manifest and restarting is, today, the only way to change it (no admin
UI in this phase) — this is a deliberate, disclosed scope cut.

Every document hash in DOCUMENTS is computed from the actual PDF bytes
under methodologies/ at import time (see _file_sha256) rather than
hand-typed, so it can never silently drift from what's really on disk.
"""
import hashlib
from pathlib import Path

from sqlalchemy import text

from src.database import get_db_connection

METHODOLOGIES_DIR = Path(__file__).parent.parent / "methodologies"


def _file_sha256(relative_path: str) -> str | None:
    path = METHODOLOGIES_DIR / relative_path
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Seed manifest — every fact here is either read directly from a local PDF
# (hash, existence), stated verbatim in docs/RESEARCH_IMPLEMENTATION_PLAN_
# 2026-09-23.md's "Local methodology inventory" / "Official sources
# checked" sections (dates, correction relationships, version status), or
# already cited in this codebase's own engine docstrings (source sections
# for implemented equations). Nothing here is invented; where a fact
# isn't available locally, the field is left null and the document is
# marked ingestion_status='referenced_external'.
# --------------------------------------------------------------------------

DOCUMENTS = [
    {"document_id": "vm0042-v2.2", "methodology_key": "VM0042",
     "title": "VM0042: Methodology for Improved Agricultural Land Management", "version": "2.2",
     "document_type": "methodology", "file_path": "verra/vm0042/VM0042v2.2.pdf",
     "source_url": "https://verra.org/methodologies/vm0042-improved-agricultural-land-management-v2-2/"},
    {"document_id": "vm0042-cc-2026-06-11", "methodology_key": "VM0042",
     "title": "Corrections and Clarifications to VM0042 (11 June 2026)", "version": None,
     "document_type": "correction", "file_path": "verra/vm0042/VM0042v2.2_CC_11JUN2026.pdf",
     "publication_date": "2026-06-11", "corrects_document_id": "vm0042-v2.2",
     "source_url": "https://verra.org/program-notice/corrections-and-clarifications-to-ialm-methodology-vm0042/"},
    {"document_id": "vm0051-v1.1", "methodology_key": "VM0051",
     "title": "VM0051: Improved Management in Rice Production Systems", "version": "1.1",
     "document_type": "methodology", "file_path": "verra/vm0051/VM0051-Improved-Management-in-Rice-Production-Systems-v1.1.pdf",
     "effective_date": "2026-07-14",
     "source_url": "https://verra.org/methodologies/improved-management-in-rice-production-systems/"},
    {"document_id": "vm0051-v1.0-superseded", "methodology_key": "VM0051",
     "title": "VM0051: Improved Management in Rice Production Systems (superseded)", "version": "1.0",
     "document_type": "methodology", "file_path": "verra/vm0051/superseded/VM0051v1_27Feb25.pdf",
     "publication_date": "2025-02-27", "superseded_by": "vm0051-v1.1",
     "notes": "Transition eligibility for projects already registered under v1.0 before v1.1 took effect; "
              "Verra's methodology page describes an August 2027 inactivation. A folder name of "
              "'superseded' alone does not determine an individual project's continued eligibility — see "
              "project_methodology_applicability.",
     "source_url": "https://verra.org/methodologies/improved-management-in-rice-production-systems/"},
    {"document_id": "vt0014-v1.0", "methodology_key": "VT0014",
     "title": "VT0014: Estimating Organic Carbon Stocks Using Digital Soil Mapping", "version": "1.0",
     "document_type": "tool", "file_path": "verra/vm0042/VT0014-v1.0.pdf",
     "notes": "No digital-soil-mapping pathway is implemented in this codebase yet (deferred to a later phase "
              "per the research plan) — registered here for dependency tracking only.",
     "source_url": "https://verra.org/methodologies/vt0014-estimating-organic-carbon-stocks-using-digital-soil-mapping-v1-0/"},
    {"document_id": "vt0014-cc-2025-10-16", "methodology_key": "VT0014",
     "title": "Corrections to VT0014 v1.0 (16 October 2025)", "version": None,
     "document_type": "correction", "file_path": "verra/vm0042/CorrectionsVT0014v1.0_16OCT2025.pdf",
     "publication_date": "2025-10-16", "corrects_document_id": "vt0014-v1.0"},
    {"document_id": "vcs-standard-v5.0", "methodology_key": "VCS_STANDARD",
     "title": "VCS Standard", "version": "5.0", "document_type": "standard",
     "file_path": "verra/standards/VCS-Standard-v5.0.pdf",
     "source_url": "https://verra.org/programs/verified-carbon-standard/vcs-program-details/"},
    {"document_id": "vcs-program-guide-v5.0", "methodology_key": "VCS_PROGRAM_GUIDE",
     "title": "VCS Program Guide", "version": "5.0", "document_type": "standard",
     "file_path": "verra/standards/VCS-Program-Guide.pdf",
     "source_url": "https://verra.org/programs/verified-carbon-standard/vcs-program-details/"},
    {"document_id": "vcs-registration-issuance-v5.0", "methodology_key": "VCS_REGISTRATION_ISSUANCE",
     "title": "Registration and Issuance Process", "version": "5.0", "document_type": "standard",
     "file_path": "verra/standards/Registration-and-Issuance.pdf",
     "source_url": "https://verra.org/programs/verified-carbon-standard/vcs-program-details/"},
    {"document_id": "ipcc2019-v4-ch2", "methodology_key": "IPCC_2019_V4_CH2",
     "title": "2019 Refinement to the 2006 IPCC Guidelines — Volume 4, Chapter 2: Generic Methodologies",
     "document_type": "guidance", "file_path": "ipcc/2019_refinement/19R_V4_Ch02_Generic_Methodologies.pdf"},
    {"document_id": "ipcc2019-v4-ch5", "methodology_key": "IPCC_2019_V4_CH5",
     "title": "2019 Refinement to the 2006 IPCC Guidelines — Volume 4, Chapter 5: Cropland",
     "document_type": "guidance", "file_path": "ipcc/2019_refinement/19R_V4_Ch05_Cropland.pdf"},
    {"document_id": "ipcc2019-v4-ch10", "methodology_key": "IPCC_2019_V4_CH10",
     "title": "2019 Refinement to the 2006 IPCC Guidelines — Volume 4, Chapter 10: Livestock",
     "document_type": "guidance", "file_path": "ipcc/2019_refinement/19R_V4_Ch10_Livestock.pdf"},
    {"document_id": "ipcc2019-v4-ch11", "methodology_key": "IPCC_2019_V4_CH11",
     "title": "2019 Refinement to the 2006 IPCC Guidelines — Volume 4, Chapter 11: Soils N2O/CO2",
     "document_type": "guidance", "file_path": "ipcc/2019_refinement/19R_V4_Ch11_Soils_N2O_CO2.pdf"},
    {"document_id": "fao-gsoc-mrv", "methodology_key": "FAO_GSOC_MRV",
     "title": "FAO: A protocol for measurement, monitoring, reporting and verification of soil organic "
              "carbon in agricultural landscapes",
     "document_type": "protocol", "file_path": "fao/FAO_GSOC_MRV_Protocol.pdf",
     "notes": "Supporting guidance for sampling/laboratory workflows — not itself an authorization to issue "
              "credits (see docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md)."},
    # Referenced but not present locally — registered for dependency tracking (per the plan's
    # "Missing from this folder" note) with no file_path/sha256, ingestion_status makes this explicit.
    {"document_id": "vmd0054-v1.1", "methodology_key": "VMD0054", "title": "VMD0054: Estimating Leakage "
     "from the Displacement of Agricultural Activities", "version": "1.1",
     "document_type": "methodology_module", "effective_date": "2026-01-13",
     "notes": "This codebase's production-decline leakage screening implements only v1.0-era Steps 1-2 "
              "logic (see src/carbon_calculator_alm.py's _production_decline_leakage docstring); v1.1's "
              "new-commodity/ecosystem provisions are not implemented.",
     "source_url": "https://verra.org/methodologies/vmd0054-estimating-leakage-from-the-displacement-of-agricultural-activities-v1-1/"},
    {"document_id": "vmd0053-v2.1", "methodology_key": "VMD0053",
     "title": "VMD0053: Model Calibration, Validation, and Uncertainty Guidance for VM0042", "version": "2.1",
     "document_type": "methodology_module",
     "notes": "No biogeochemical-model quantification pathway is implemented; registered for future reference.",
     "source_url": "https://verra.org/methodologies/vmd0053-model-calibration-validation-and-uncertainty-guidance-for-the-methodology-for-improved-agricultural-land-management-v2-1/"},
    {"document_id": "vt0008", "methodology_key": "VT0008", "title": "VT0008: Additionality Assessment",
     "document_type": "tool",
     "notes": "Additionality procedures are not ingested or automated — always requires an expert reviewer "
              "decision (see EXPERT_REQUIREMENTS in src/readiness.py).",
     "source_url": "https://verra.org/methodologies/vt0008-additionality-assessment/"},
]

BUNDLES = [
    {"bundle_id": "vm0042-2026-06", "accounting_pathway": "vm0042_alm",
     "bundle_version": "VM0042 v2.2 + 11 Jun 2026 corrections", "effective_from": "2026-06-11",
     "is_current": True,
     "documents": [
         ("vm0042-v2.2", "primary"), ("vm0042-cc-2026-06-11", "correction"),
         ("vcs-standard-v5.0", "standard"), ("vcs-program-guide-v5.0", "standard"),
         ("vcs-registration-issuance-v5.0", "standard"),
         ("vmd0054-v1.1", "supporting"), ("vt0008", "supporting"),
         ("ipcc2019-v4-ch5", "supporting"), ("ipcc2019-v4-ch10", "supporting"),
         ("ipcc2019-v4-ch11", "supporting"), ("fao-gsoc-mrv", "supporting"),
     ]},
    {"bundle_id": "vm0051-2026-07", "accounting_pathway": "vm0051_rice_awd",
     "bundle_version": "VM0051 v1.1", "effective_from": "2026-07-14", "is_current": True,
     "documents": [
         ("vm0051-v1.1", "primary"), ("vcs-standard-v5.0", "standard"),
         ("vcs-program-guide-v5.0", "standard"), ("vcs-registration-issuance-v5.0", "standard"),
         ("vt0008", "supporting"), ("ipcc2019-v4-ch5", "supporting"),
     ]},
    {"bundle_id": "vm0051-2025-legacy", "accounting_pathway": "vm0051_rice_awd",
     "bundle_version": "VM0051 v1.0 (transition-eligible legacy projects only)",
     "effective_from": "2025-02-27", "effective_until": "2027-08-01", "is_current": False,
     "notes": "Select only for a project that was already registered under v1.0 before v1.1 took effect "
              "(project_methodology_applicability records that decision explicitly) — never the default "
              "for a new project.",
     "documents": [("vm0051-v1.0-superseded", "primary")]},
]

# The requirements matrix: requirement_id -> source section / evidence /
# implementation support / who may decide it / whether it blocks
# readiness. `implementation_support='unsupported'` rows can NEVER be
# manually overridden to 'satisfied' (enforced in src/reviews.py's
# record_determination and src/readiness.py's _apply_manual_overrides) —
# see docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md Phase 1, gap #2/#5.
REQUIREMENTS = [
    # --- Common to both pathways ---
    {"requirement_id": "common.methodology_applicability", "bundle_id": "",  # applies under both bundles
     "title": "Field type, declared crop, and eligibility area match the selected methodology's scope",
     "source_document_id": None, "source_section": None,
     "required_evidence": "Field type (immutable at registration) plus the crop(s) declared in linked crop "
                           "seasons must be within the selected pathway's documented scope.",
     "implementation_support": "implemented", "reviewer_authority": "reviewable", "blocking": True},
    {"requirement_id": "vm0042.excludes_wetland_rice", "bundle_id": "vm0042-2026-06",
     "title": "VM0042 excludes wetland/flooded-rice cropland from its project boundary",
     "source_document_id": "vm0042-v2.2", "source_section": "§4, applicability condition 8",
     "required_evidence": "None accepted automatically — rice SOC claims require a separate applicability "
                           "and implementation assessment that does not exist in this codebase yet.",
     "implementation_support": "unsupported", "reviewer_authority": "automated_only", "blocking": True},
    {"requirement_id": "common.monitoring_period_coverage", "bundle_id": "",
     "title": "Linked crop seasons cover the requested monitoring period",
     "source_document_id": None, "source_section": None,
     "required_evidence": "Crop-season start/end dates spanning the monitoring period.",
     "implementation_support": "implemented", "reviewer_authority": "reviewable", "blocking": True},
    {"requirement_id": "common.evidence_review_status", "bundle_id": "",
     "title": "Field observations are independently reviewed",
     "source_document_id": None, "source_section": None,
     "required_evidence": "Each field observation accepted by a team member other than its author.",
     "implementation_support": "implemented", "reviewer_authority": "reviewable", "blocking": True},
    {"requirement_id": "common.additionality", "bundle_id": "",
     "title": "Additionality assessment",
     "source_document_id": "vt0008", "source_section": None,
     "required_evidence": "VT0008 procedures applied by an expert reviewer — not automated by this system.",
     "implementation_support": "unsupported", "reviewer_authority": "expert_required", "blocking": True},
    # --- VM0051 rice AWD ---
    {"requirement_id": "vm0051.required_measurement_inputs", "bundle_id": "vm0051-2026-07",
     "title": "Satellite-derived AWD event count and season length are supplied",
     "source_document_id": "vm0051-v1.1", "source_section": "§8.2.3 Eq. 6",
     "required_evidence": "AWD event count and season length from signal analytics or manual entry.",
     "implementation_support": "implemented", "reviewer_authority": "automated_only", "blocking": True},
    {"requirement_id": "vm0051.qa3_pathway_project_size", "bundle_id": "vm0051-2026-07",
     "title": "Estimated reductions are within the QA3 default-emission-factors project-size gate",
     "source_document_id": "vm0051-v1.1", "source_section": "§8.6.3",
     "required_evidence": "Computed from the calculation result; not evidence supplied by a user.",
     "implementation_support": "implemented", "reviewer_authority": "automated_only", "blocking": True},
    {"requirement_id": "vm0051.leakage_assessment", "bundle_id": "vm0051-2026-07",
     "title": "VM0051 §8.4 leakage assessment (organic-amendment import / yield decline / biomass diversion)",
     "source_document_id": "vm0051-v1.1", "source_section": "§8.4",
     "required_evidence": "Not implemented — no evidence can satisfy this in the current codebase.",
     "implementation_support": "unsupported", "reviewer_authority": "automated_only", "blocking": False},
    {"requirement_id": "vm0051.n2o_baseline_fertilizer", "bundle_id": "vm0051-2026-07",
     "title": "N2O from baseline nitrogen fertilizer (assumed zero — no fertilizer change modeled)",
     "source_document_id": "vm0051-v1.1", "source_section": "§8.2.6",
     "required_evidence": "Not implemented.", "implementation_support": "unsupported",
     "reviewer_authority": "automated_only", "blocking": False},
    {"requirement_id": "vm0051.biomass_burning", "bundle_id": "vm0051-2026-07",
     "title": "CH4/N2O from biomass burning",
     "source_document_id": "vm0051-v1.1", "source_section": "§8.2.5-8.2.7",
     "required_evidence": "Not implemented.", "implementation_support": "unsupported",
     "reviewer_authority": "automated_only", "blocking": False},
    # --- VM0042 ALM ---
    {"requirement_id": "vm0042.baseline_documentation", "bundle_id": "vm0042-2026-06",
     "title": "Baseline practice schedule and historical activity record",
     "source_document_id": "vm0042-v2.2", "source_section": "Table 4",
     "required_evidence": "A baseline practice schedule AND at least one recorded crop season predating "
                           "the monitoring period (a minimum evidentiary bar — not full historical "
                           "look-back verification; see docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md "
                           "Phase 1 gap #1).",
     "implementation_support": "implemented", "reviewer_authority": "reviewable", "blocking": True},
    {"requirement_id": "vm0042.soc_measurements", "bundle_id": "vm0042-2026-06",
     "title": "Paired project/control SOC samples at both timepoints",
     "source_document_id": "vm0042-v2.2", "source_section": "§8.2.1/8.3 Eqs. 3-5, 46-47",
     "required_evidence": ">=3 samples per (site type, timepoint) cell — aggregate values only in this "
                           "codebase, not full sampling-plan/strata/chain-of-custody records (Phase 3).",
     "implementation_support": "partial", "reviewer_authority": "reviewable", "blocking": True},
    {"requirement_id": "vm0042.project_practice_schedule", "bundle_id": "vm0042-2026-06",
     "title": "Project-scenario practice schedule",
     "source_document_id": "vm0042-v2.2", "source_section": "Table 4",
     "required_evidence": "Project practice schedule recorded.",
     "implementation_support": "implemented", "reviewer_authority": "reviewable", "blocking": True},
    {"requirement_id": "vm0042.integrated_livestock_scope", "bundle_id": "vm0042-2026-06",
     "title": "Integrated crop-livestock scope (Pasture/Range/Paddock only)",
     "source_document_id": "vm0042-v2.2", "source_section": "§8.2.6/8.2.7",
     "required_evidence": "Livestock schedule recorded, or not applicable if none.",
     "implementation_support": "implemented", "reviewer_authority": "automated_only", "blocking": False},
    {"requirement_id": "vm0042.production_decline_leakage", "bundle_id": "vm0042-2026-06",
     "title": "Production-decline leakage screening",
     "source_document_id": "vmd0054-v1.1", "source_section": "§8.4.3 Eq. 39/42 (v1.0-era Steps 1-2 only)",
     "required_evidence": "Computed from baseline vs. project crop yield.",
     "implementation_support": "partial", "reviewer_authority": "automated_only", "blocking": True},
    {"requirement_id": "vm0042.new_land_carbon_stock_accounting", "bundle_id": "vm0042-2026-06",
     "title": "New-land carbon-stock accounting for foregone production (VMD0054 Steps 3-5)",
     "source_document_id": "vmd0054-v1.1", "source_section": "§8.4.3",
     "required_evidence": "Not implemented — the engine blocks rather than quantifying.",
     "implementation_support": "unsupported", "reviewer_authority": "automated_only", "blocking": False},
    {"requirement_id": "vm0042.liming_co2", "bundle_id": "vm0042-2026-06",
     "title": "CO2 from liming",
     "source_document_id": "vm0042-v2.2", "source_section": "§8.2.4",
     "required_evidence": "Not implemented.", "implementation_support": "unsupported",
     "reviewer_authority": "automated_only", "blocking": False},
    {"requirement_id": "vm0042.quantification_approach", "bundle_id": "vm0042-2026-06",
     "title": "Quantification approach used for SOC stock change",
     "source_document_id": "vm0042-v2.2", "source_section": "§8.2.1",
     "required_evidence": "This system implements only Quantification Approach 2 (measure and remeasure). "
                           "Approach 1 (biogeochemical model, VMD0053) is not implemented — never presented "
                           "as available.",
     "implementation_support": "partial", "reviewer_authority": "automated_only", "blocking": False},
    {"requirement_id": "vm0042.uncertainty_deduction", "bundle_id": "vm0042-2026-06",
     "title": "SOC-only uncertainty deduction via probability of exceedance",
     "source_document_id": "vm0042-v2.2", "source_section": "§8.6.2/8.6.4 Eqs. 70-71, 74",
     "required_evidence": "Computed from SOC measurements and the supplied non-permanence risk rating. "
                           "The annualization in the uncertainty denominator and variance conversions "
                           "against Eqs. 70-71/74 has not been independently re-derived in this phase — "
                           "flagged for Phase 3 review, not a confirmed defect.",
     "implementation_support": "partial", "reviewer_authority": "automated_only", "blocking": False},
]


def initialize_tables(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS methodology_documents (
            document_id          TEXT PRIMARY KEY,
            methodology_key      TEXT NOT NULL,
            title                TEXT NOT NULL,
            version              TEXT,
            document_type        TEXT NOT NULL,
            publication_date     TEXT,
            effective_date       TEXT,
            superseded_by        TEXT,
            corrects_document_id TEXT,
            file_path            TEXT,
            sha256               TEXT,
            source_url           TEXT,
            ingestion_status     TEXT NOT NULL CHECK (ingestion_status IN ('ingested_local', 'referenced_external')),
            notes                TEXT
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS methodology_bundles (
            bundle_id          TEXT PRIMARY KEY,
            accounting_pathway TEXT NOT NULL,
            bundle_version     TEXT NOT NULL,
            effective_from     TEXT,
            effective_until    TEXT,
            is_current         INTEGER NOT NULL DEFAULT 0,
            notes              TEXT,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS methodology_bundle_documents (
            bundle_id   TEXT NOT NULL,
            document_id TEXT NOT NULL,
            role        TEXT NOT NULL CHECK (role IN ('primary', 'correction', 'standard', 'supporting')),
            PRIMARY KEY (bundle_id, document_id)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS methodology_requirements (
            requirement_id       TEXT NOT NULL,
            bundle_id            TEXT NOT NULL DEFAULT '',
            title                TEXT NOT NULL,
            source_document_id   TEXT,
            source_section       TEXT,
            required_evidence    TEXT NOT NULL,
            implementation_support TEXT NOT NULL CHECK (implementation_support IN ('implemented', 'partial', 'unsupported')),
            reviewer_authority   TEXT NOT NULL CHECK (reviewer_authority IN ('automated_only', 'reviewable', 'expert_required')),
            blocking             INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (requirement_id, bundle_id)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS project_methodology_applicability (
            org_id           TEXT NOT NULL,
            id               TEXT NOT NULL,
            project_id       TEXT NOT NULL,
            accounting_pathway TEXT NOT NULL,
            bundle_id        TEXT NOT NULL,
            applicable_from  TEXT,
            applicable_until TEXT,
            decided_by       TEXT NOT NULL,
            reason           TEXT NOT NULL,
            decided_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, id)
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_project_methodology_applicability_scope "
        "ON project_methodology_applicability(org_id, project_id, accounting_pathway)"
    ))
    _seed(conn)


def _seed(conn):
    """Idempotent upsert — safe to run on every startup. Recomputes
    sha256 from disk every time, so a corrected/replaced PDF is detected
    (the row's hash changes) rather than silently trusted from a stale
    DB value."""
    for doc in DOCUMENTS:
        sha256 = _file_sha256(doc["file_path"]) if doc.get("file_path") else None
        row = {
            "document_id": doc["document_id"], "methodology_key": doc["methodology_key"],
            "title": doc["title"], "version": doc.get("version"),
            "document_type": doc["document_type"], "publication_date": doc.get("publication_date"),
            "effective_date": doc.get("effective_date"), "superseded_by": doc.get("superseded_by"),
            "corrects_document_id": doc.get("corrects_document_id"), "file_path": doc.get("file_path"),
            "sha256": sha256, "source_url": doc.get("source_url"),
            "ingestion_status": "ingested_local" if sha256 else "referenced_external",
            "notes": doc.get("notes"),
        }
        conn.execute(text("""
            INSERT INTO methodology_documents (document_id, methodology_key, title, version, document_type,
                publication_date, effective_date, superseded_by, corrects_document_id, file_path, sha256,
                source_url, ingestion_status, notes)
            VALUES (:document_id, :methodology_key, :title, :version, :document_type, :publication_date,
                :effective_date, :superseded_by, :corrects_document_id, :file_path, :sha256, :source_url,
                :ingestion_status, :notes)
            ON CONFLICT (document_id) DO UPDATE SET
                title = excluded.title, version = excluded.version, document_type = excluded.document_type,
                publication_date = excluded.publication_date, effective_date = excluded.effective_date,
                superseded_by = excluded.superseded_by, corrects_document_id = excluded.corrects_document_id,
                file_path = excluded.file_path, sha256 = excluded.sha256, source_url = excluded.source_url,
                ingestion_status = excluded.ingestion_status, notes = excluded.notes
        """), row)

    for bundle in BUNDLES:
        conn.execute(text("""
            INSERT INTO methodology_bundles (bundle_id, accounting_pathway, bundle_version, effective_from,
                effective_until, is_current, notes)
            VALUES (:bundle_id, :accounting_pathway, :bundle_version, :effective_from, :effective_until,
                :is_current, :notes)
            ON CONFLICT (bundle_id) DO UPDATE SET
                accounting_pathway = excluded.accounting_pathway, bundle_version = excluded.bundle_version,
                effective_from = excluded.effective_from, effective_until = excluded.effective_until,
                is_current = excluded.is_current, notes = excluded.notes
        """), {"bundle_id": bundle["bundle_id"], "accounting_pathway": bundle["accounting_pathway"],
               "bundle_version": bundle["bundle_version"], "effective_from": bundle.get("effective_from"),
               "effective_until": bundle.get("effective_until"), "is_current": int(bundle.get("is_current", False)),
               "notes": bundle.get("notes")})
        conn.execute(text("DELETE FROM methodology_bundle_documents WHERE bundle_id = :bundle_id"),
                     {"bundle_id": bundle["bundle_id"]})
        for document_id, role in bundle["documents"]:
            conn.execute(text(
                "INSERT INTO methodology_bundle_documents (bundle_id, document_id, role) "
                "VALUES (:bundle_id, :document_id, :role)"
            ), {"bundle_id": bundle["bundle_id"], "document_id": document_id, "role": role})

    for req in REQUIREMENTS:
        conn.execute(text("""
            INSERT INTO methodology_requirements (requirement_id, bundle_id, title, source_document_id,
                source_section, required_evidence, implementation_support, reviewer_authority, blocking)
            VALUES (:requirement_id, :bundle_id, :title, :source_document_id, :source_section,
                :required_evidence, :implementation_support, :reviewer_authority, :blocking)
            ON CONFLICT (requirement_id, bundle_id) DO UPDATE SET
                title = excluded.title, source_document_id = excluded.source_document_id,
                source_section = excluded.source_section, required_evidence = excluded.required_evidence,
                implementation_support = excluded.implementation_support,
                reviewer_authority = excluded.reviewer_authority, blocking = excluded.blocking
        """), {"requirement_id": req["requirement_id"], "bundle_id": req.get("bundle_id") or "",
               "title": req["title"], "source_document_id": req.get("source_document_id"),
               "source_section": req.get("source_section"), "required_evidence": req["required_evidence"],
               "implementation_support": req["implementation_support"],
               "reviewer_authority": req["reviewer_authority"], "blocking": int(req["blocking"])})


# --------------------------------------------------------------------------
# Query helpers
# --------------------------------------------------------------------------

def current_bundle_for_pathway(accounting_pathway: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM methodology_bundles WHERE accounting_pathway = :pathway AND is_current = 1 "
            "ORDER BY effective_from DESC LIMIT 1"
        ), {"pathway": accounting_pathway}).mappings().fetchone()
    return dict(row) if row else None


def get_bundle(bundle_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM methodology_bundles WHERE bundle_id = :bundle_id"
        ), {"bundle_id": bundle_id}).mappings().fetchone()
    if row is None:
        return None
    bundle = dict(row)
    with get_db_connection() as conn:
        docs = conn.execute(text("""
            SELECT d.*, bd.role FROM methodology_bundle_documents bd
            JOIN methodology_documents d ON d.document_id = bd.document_id
            WHERE bd.bundle_id = :bundle_id
        """), {"bundle_id": bundle_id}).mappings().fetchall()
    bundle["documents"] = [dict(d) for d in docs]
    return bundle


def list_bundles(accounting_pathway: str | None = None) -> list[dict]:
    query = "SELECT * FROM methodology_bundles"
    params = {}
    if accounting_pathway is not None:
        query += " WHERE accounting_pathway = :pathway"
        params["pathway"] = accounting_pathway
    query += " ORDER BY effective_from DESC"
    with get_db_connection() as conn:
        rows = conn.execute(text(query), params).mappings().fetchall()
    return [dict(r) for r in rows]


def get_requirement_meta(requirement_id: str, bundle_id: str | None) -> dict | None:
    """A requirement's static metadata is looked up bundle-specific first
    (a future bundle might revise wording/section for the same
    requirement_id), falling back to the bundle-agnostic ('common')
    definition."""
    with get_db_connection() as conn:
        if bundle_id:
            row = conn.execute(text(
                "SELECT * FROM methodology_requirements WHERE requirement_id = :rid AND bundle_id = :bundle_id"
            ), {"rid": requirement_id, "bundle_id": bundle_id}).mappings().fetchone()
            if row is not None:
                return dict(row)
        row = conn.execute(text(
            "SELECT * FROM methodology_requirements WHERE requirement_id = :rid AND bundle_id = ''"
        ), {"rid": requirement_id}).mappings().fetchone()
    return dict(row) if row else None


def list_requirements(bundle_id: str) -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text(
            "SELECT * FROM methodology_requirements WHERE bundle_id = :bundle_id OR bundle_id = ''"
        ), {"bundle_id": bundle_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def list_documents() -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(text("SELECT * FROM methodology_documents ORDER BY methodology_key, version")).mappings().fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Project-specific applicability (e.g. "this project may continue under
# VM0051 v1.0 transition eligibility")
# --------------------------------------------------------------------------

def set_project_applicability(org_id: str, project_id: str, accounting_pathway: str, bundle_id: str,
                               decided_by: str, reason: str, applicable_from: str | None = None,
                               applicable_until: str | None = None) -> dict:
    if get_bundle(bundle_id) is None:
        raise ValueError(f"Unknown methodology bundle {bundle_id!r}")
    import uuid
    row_id = uuid.uuid4().hex
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO project_methodology_applicability
                (org_id, id, project_id, accounting_pathway, bundle_id, applicable_from, applicable_until,
                 decided_by, reason)
            VALUES (:org_id, :id, :project_id, :accounting_pathway, :bundle_id, :applicable_from,
                    :applicable_until, :decided_by, :reason)
        """), {"org_id": org_id, "id": row_id, "project_id": project_id, "accounting_pathway": accounting_pathway,
               "bundle_id": bundle_id, "applicable_from": applicable_from, "applicable_until": applicable_until,
               "decided_by": decided_by, "reason": reason})
        conn.commit()
    return get_project_applicability(org_id, project_id, accounting_pathway) or {}


def get_project_applicability(org_id: str, project_id: str, accounting_pathway: str) -> dict | None:
    """The most recent explicit applicability decision for this project +
    pathway, if any — falls back to current_bundle_for_pathway() when
    none was ever recorded (the ordinary case: a new project just uses
    whatever bundle is current)."""
    with get_db_connection() as conn:
        row = conn.execute(text("""
            SELECT * FROM project_methodology_applicability
            WHERE org_id = :org_id AND project_id = :project_id AND accounting_pathway = :pathway
            ORDER BY decided_at DESC LIMIT 1
        """), {"org_id": org_id, "project_id": project_id, "pathway": accounting_pathway}).mappings().fetchone()
    return dict(row) if row else None


def resolve_bundle_for_project(org_id: str, project_id: str | None, accounting_pathway: str) -> dict | None:
    """The bundle a NEW calculation for this project/pathway should be
    frozen against: an explicit project-level applicability decision if
    one was recorded, else the pathway's current bundle."""
    if project_id:
        applicability = get_project_applicability(org_id, project_id, accounting_pathway)
        if applicability is not None:
            return get_bundle(applicability["bundle_id"])
    return current_bundle_for_pathway(accounting_pathway)
