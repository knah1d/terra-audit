"""Evidence-linked carbon calculations — Phase 2 of the multi-tenant/
multi-crop plan (docs/MULTICROP.md's roadmap; see also src/projects.py's
Phase 1 docstring).

Compatibility strategy: this is ADDITIVE. The existing stateless
preview/commit endpoints (backend/routers/carbon.py) and their
credit_history table are untouched and keep working exactly as before —
existing PDF/JSON/CSV exports still read credit_history. This module
introduces a *parallel* `calculations` table for the new evidence-linked,
versioned, project/season-aware flow. A caller can tell the two apart:
credit_history rows have no calculation_id; new-flow rows always do.
Existing fields, seasons, practice data and credit history are never
migrated or backfilled into this table — a pre-Phase-2 commit is
permanently a "legacy calculation, no snapshot" (see list_calculations()'s
`legacy` flag), never silently upgraded with fabricated provenance.

Key invariants:
  - A commit reads every referenced record exactly once, into one
    snapshot dict, and calculates from THAT dict — never recalculates
    from a second, possibly-drifted read (see build_snapshot()).
  - snapshot_json/result_json/inputs_json never change after insert.
    A correction is always a NEW row (new calculation_id, version+1,
    supersedes_calculation_id set) — the prior row is flipped to
    'superseded', never edited or deleted.
  - Idempotency-Key-guarded commit (mirrors src.database.
    commit_carbon_credit_result) so a retried submission returns the
    original row instead of creating a duplicate version.
"""
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from src.database import get_db_connection, is_sqlite

# One pathway per field_type today (two methodologies exist). Kept as an
# explicit mapping — never inferred from a crop declaration — so a client
# must state which pathway it means; this becomes a real choice only once
# a field_type ever supports more than one pathway.
PATHWAYS = {
    "rice_awd": "vm0051_rice_awd",
    "cropland_alm_vm0042": "vm0042_alm",
}

METHODOLOGY_VERSION = {
    "vm0051_rice_awd": "VM0051 v1.1 (QA3 Default Emission Factors pathway, scoped subset)",
    "vm0042_alm": "VM0042 v2.2 (Improved Agricultural Land Management, scoped subset)",
}

# Bump manually when calculate_credits()'s logic changes in either engine —
# mirrors src.processing.PROCESSING_VERSION/MULTICROP_VERSION's convention
# of a plain, hand-maintained version string rather than a build hash.
ENGINE_VERSION = {
    "vm0051_rice_awd": "carbon_calculator-v1",
    "vm0042_alm": "carbon_calculator_alm-v1",
}

STATUSES = {"draft", "ready_for_review", "superseded"}
DETERMINATION_STATUSES = {"satisfied", "missing", "needs_review", "not_applicable", "unsupported"}


def initialize_tables(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS calculations (
            org_id                    TEXT NOT NULL,
            calculation_id            TEXT NOT NULL,
            chain_id                  TEXT NOT NULL,
            version                   INTEGER NOT NULL,
            supersedes_calculation_id TEXT,
            project_id                TEXT,
            field_id                  TEXT NOT NULL,
            field_type                TEXT NOT NULL,
            accounting_pathway        TEXT NOT NULL,
            monitoring_period_start   TEXT NOT NULL,
            monitoring_period_end     TEXT NOT NULL,
            season_ids                TEXT NOT NULL,
            status                    TEXT NOT NULL DEFAULT 'draft'
                                      CHECK (status IN ('draft', 'ready_for_review', 'superseded')),
            snapshot_json             TEXT NOT NULL,
            inputs_json               TEXT NOT NULL,
            result_json               TEXT NOT NULL,
            readiness_json            TEXT NOT NULL,
            methodology_version       TEXT NOT NULL,
            engine_version            TEXT NOT NULL,
            bundle_id                 TEXT,
            final_issuance            REAL,
            created_by                TEXT NOT NULL,
            created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, calculation_id)
        )
    """))
    # Additive migration for a pre-existing `calculations` table (this
    # column was added after that table's original release) — the
    # frozen methodology bundle a calculation was computed against
    # (docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md Phase 1 gap #1:
    # "Freeze the applicable methodology bundle into each calculation
    # snapshot"). Historical rows keep bundle_id NULL — they predate the
    # registry and are never backfilled with a guessed bundle.
    if is_sqlite():
        try:
            conn.execute(text("ALTER TABLE calculations ADD COLUMN bundle_id TEXT"))
        except Exception:
            pass
    else:
        conn.execute(text("ALTER TABLE calculations ADD COLUMN IF NOT EXISTS bundle_id TEXT"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_calculations_field ON calculations(org_id, field_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_calculations_chain ON calculations(org_id, chain_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_calculations_project ON calculations(org_id, project_id)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS calculation_idempotency_keys (
            org_id          TEXT NOT NULL,
            field_id        TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            calculation_id  TEXT NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, field_id, idempotency_key)
        )
    """))

    # Populated at commit time so attachments referenced by an immutable
    # snapshot can be protected from deletion (see referenced_attachment_ids
    # below and backend/routers/attachments.py's delete guard) without
    # scanning every snapshot_json blob.
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS calculation_attachment_refs (
            org_id         TEXT NOT NULL,
            calculation_id TEXT NOT NULL,
            attachment_id  TEXT NOT NULL,
            PRIMARY KEY (org_id, calculation_id, attachment_id)
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_calc_attachment_refs_attachment "
        "ON calculation_attachment_refs(org_id, attachment_id)"
    ))

    # Append-only, mirroring observation_reviews' pattern: every manual
    # readiness determination (e.g. an expert additionality call) is kept,
    # never overwritten — the most recent row per (field, pathway,
    # requirement_id) governs.
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS readiness_determinations (
            id                      TEXT NOT NULL,
            org_id                  TEXT NOT NULL,
            field_id                TEXT NOT NULL,
            accounting_pathway      TEXT NOT NULL,
            requirement_id          TEXT NOT NULL,
            bundle_id               TEXT NOT NULL DEFAULT '',
            monitoring_period_start TEXT NOT NULL DEFAULT '',
            monitoring_period_end   TEXT NOT NULL DEFAULT '',
            evidence_fingerprint    TEXT NOT NULL DEFAULT '',
            status                  TEXT NOT NULL,
            reason                  TEXT NOT NULL,
            decided_by              TEXT NOT NULL,
            decided_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (org_id, id)
        )
    """))
    # Additive migration for a pre-existing table (Phase 3 shipped this
    # table without bundle/period scoping). A determination scoped to
    # docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md Phase 1 gap #2/#5
    # requirements ("Scope reviewer decisions to the project, methodology
    # bundle, reporting period, and evidence version; invalidate stale
    # decisions") must match on ALL of these to still apply — see
    # latest_determinations()'s exact-match WHERE clause. A pre-migration
    # row defaults to '' for all three, so it will simply never match a
    # real (non-empty) scope again — its determination is not deleted,
    # but src.readiness stops honoring it, which is the intended
    # "invalidate when scope changes" behavior applied retroactively.
    for col in ("bundle_id", "monitoring_period_start", "monitoring_period_end", "evidence_fingerprint"):
        if is_sqlite():
            try:
                conn.execute(text(f"ALTER TABLE readiness_determinations ADD COLUMN {col} TEXT NOT NULL DEFAULT ''"))
            except Exception:
                pass
        else:
            conn.execute(text(f"ALTER TABLE readiness_determinations ADD COLUMN IF NOT EXISTS {col} TEXT NOT NULL DEFAULT ''"))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_readiness_determinations_scope "
        "ON readiness_determinations(org_id, field_id, accounting_pathway)"
    ))


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Readiness determinations (manual, persisted, append-only)
# --------------------------------------------------------------------------

def record_determination(org_id: str, field_id: str, accounting_pathway: str, requirement_id: str,
                          bundle_id: str, monitoring_period_start: str, monitoring_period_end: str,
                          evidence_fingerprint: str, status: str, reason: str, decided_by: str) -> dict:
    """Restricted to explicitly reviewable requirements
    (docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md Phase 1 gap #2/#5):
    a requirement whose registry entry says implementation_support=
    'unsupported' or reviewer_authority='automated_only' can never
    receive a manual determination — raises ValueError (422), not a
    silent no-op, so a client can't quietly fail to override something
    it shouldn't have been trying to override. Scoped to the exact
    bundle, reporting period, AND evidence fingerprint supplied (see
    src.readiness.compute_evidence_fingerprint) — see
    latest_determinations()'s exact-match read, which is what actually
    makes an out-of-scope OR evidence-changed decision stop applying,
    even when the bundle and dates are unchanged."""
    if status not in DETERMINATION_STATUSES:
        raise ValueError(f"status must be one of {sorted(DETERMINATION_STATUSES)}")
    from src import methodology_registry as registry
    meta = registry.get_requirement_meta(requirement_id, bundle_id)
    if meta is not None:
        if meta["implementation_support"] == "unsupported":
            raise ValueError(
                f"Requirement {requirement_id!r} is not implemented by this system and can never be "
                "manually marked satisfied."
            )
        if meta["reviewer_authority"] == "automated_only":
            raise ValueError(f"Requirement {requirement_id!r} does not accept a manual reviewer determination.")
    row_id = uuid.uuid4().hex
    with get_db_connection() as conn:
        conn.execute(text("""
            INSERT INTO readiness_determinations
                (id, org_id, field_id, accounting_pathway, requirement_id, bundle_id,
                 monitoring_period_start, monitoring_period_end, evidence_fingerprint, status, reason, decided_by)
            VALUES (:id, :org_id, :field_id, :accounting_pathway, :requirement_id, :bundle_id,
                    :monitoring_period_start, :monitoring_period_end, :evidence_fingerprint, :status, :reason, :decided_by)
        """), {"id": row_id, "org_id": org_id, "field_id": field_id, "accounting_pathway": accounting_pathway,
               "requirement_id": requirement_id, "bundle_id": bundle_id or "",
               "monitoring_period_start": monitoring_period_start, "monitoring_period_end": monitoring_period_end,
               "evidence_fingerprint": evidence_fingerprint, "status": status, "reason": reason,
               "decided_by": decided_by})
        conn.commit()
    return {"id": row_id, "requirement_id": requirement_id, "status": status,
            "reason": reason, "decided_by": decided_by}


def latest_determinations(org_id: str, field_id: str, accounting_pathway: str, bundle_id: str | None,
                           monitoring_period_start: str, monitoring_period_end: str,
                           evidence_fingerprint: str) -> dict:
    """Returns {requirement_id: {status, reason, decided_by, decided_at}}
    for the most recent determination on each requirement THAT STILL
    MATCHES this exact bundle + reporting period + evidence fingerprint.
    A determination recorded under a different bundle/period, OR whose
    evidence fingerprint no longer matches the field's CURRENT evidence
    (a season was corrected, a new observation was added, the practice
    schedule was edited, etc. — even with the bundle/dates unchanged),
    is invisible here — not deleted, just no longer honored (see
    record_determination's docstring and the additive-migration note in
    initialize_tables)."""
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT * FROM readiness_determinations
            WHERE org_id = :org_id AND field_id = :field_id AND accounting_pathway = :pathway
              AND bundle_id = :bundle_id AND monitoring_period_start = :period_start
              AND monitoring_period_end = :period_end AND evidence_fingerprint = :evidence_fingerprint
            ORDER BY decided_at
        """), {"org_id": org_id, "field_id": field_id, "pathway": accounting_pathway,
               "bundle_id": bundle_id or "", "period_start": monitoring_period_start,
               "period_end": monitoring_period_end, "evidence_fingerprint": evidence_fingerprint}).mappings().fetchall()
    result = {}
    for row in rows:
        result[row["requirement_id"]] = dict(row)  # later rows overwrite earlier ones (append-only, latest wins)
    return result


# --------------------------------------------------------------------------
# Calculations
# --------------------------------------------------------------------------

def get_calculation(org_id: str, calculation_id: str) -> dict | None:
    with get_db_connection() as conn:
        row = conn.execute(
            text("SELECT * FROM calculations WHERE org_id = :org_id AND calculation_id = :calculation_id"),
            {"org_id": org_id, "calculation_id": calculation_id},
        ).mappings().fetchone()
    if row is None:
        return None
    return _decode(dict(row))


def _decode(row: dict) -> dict:
    row["season_ids"] = json.loads(row["season_ids"])
    row["snapshot"] = json.loads(row.pop("snapshot_json"))
    row["inputs"] = json.loads(row.pop("inputs_json"))
    row["result"] = json.loads(row.pop("result_json"))
    row["readiness"] = json.loads(row.pop("readiness_json"))
    return row


def list_calculations(org_id: str, field_id: str | None = None, project_id: str | None = None,
                       latest_only: bool = False) -> list[dict]:
    """Returns calculations, most recent first. latest_only=True keeps only
    the newest (highest version) non-superseded row per chain — the view
    any "current outcome" consumer (a future portfolio aggregation, a
    project dashboard) MUST use to avoid double-counting a chain's
    superseded versions."""
    query = "SELECT * FROM calculations WHERE org_id = :org_id"
    params = {"org_id": org_id}
    if field_id is not None:
        query += " AND field_id = :field_id"
        params["field_id"] = field_id
    if project_id is not None:
        query += " AND project_id = :project_id"
        params["project_id"] = project_id
    query += " ORDER BY created_at DESC, version DESC"
    with get_db_connection() as conn:
        rows = [_decode(dict(r)) for r in conn.execute(text(query), params).mappings().fetchall()]
    if not latest_only:
        return rows
    best_per_chain: dict[str, dict] = {}
    for row in rows:
        if row["status"] == "superseded":
            continue
        current = best_per_chain.get(row["chain_id"])
        if current is None or row["version"] > current["version"]:
            best_per_chain[row["chain_id"]] = row
    return sorted(best_per_chain.values(), key=lambda r: r["created_at"], reverse=True)


def commit_calculation(
    org_id: str, field_id: str, idempotency_key: str, snapshot: dict, inputs: dict, result: dict,
    readiness: list[dict], field_type: str, accounting_pathway: str, project_id: str | None,
    monitoring_period_start: str, monitoring_period_end: str, season_ids: list[str],
    attachment_ids: list[str], created_by: str, supersedes_calculation_id: str | None,
    bundle_id: str | None = None,
) -> dict:
    """Atomically persists one immutable calculation snapshot, its
    idempotency-key record, its attachment references, and (if
    supersedes_calculation_id is given) flips the prior version to
    'superseded' — all in ONE connection/ONE commit, mirroring
    src.database.commit_carbon_credit_result's atomicity rationale.

    status is derived here, not trusted from the caller: 'draft' if any
    readiness item is blocking (see _is_blocking), else 'ready_for_review'
    — so a client can never talk its way into a false "ready" state.

    Returns {"calculation": <decoded row>, "already_committed": bool}.
    """
    blocking = any(_is_blocking(item) for item in readiness)
    status = "draft" if blocking else "ready_for_review"

    with get_db_connection() as conn:
        existing = conn.execute(text("""
            SELECT calculation_id FROM calculation_idempotency_keys
            WHERE org_id = :org_id AND field_id = :field_id AND idempotency_key = :key
        """), {"org_id": org_id, "field_id": field_id, "key": idempotency_key}).mappings().fetchone()
        if existing is not None:
            prior = conn.execute(
                text("SELECT * FROM calculations WHERE org_id = :org_id AND calculation_id = :cid"),
                {"org_id": org_id, "cid": existing["calculation_id"]},
            ).mappings().fetchone()
            return {"calculation": _decode(dict(prior)), "already_committed": True}

        if supersedes_calculation_id is not None:
            prior = conn.execute(
                text("SELECT chain_id, version FROM calculations WHERE org_id = :org_id AND calculation_id = :cid"),
                {"org_id": org_id, "cid": supersedes_calculation_id},
            ).mappings().fetchone()
            if prior is None:
                raise ValueError(f"Calculation to supersede ({supersedes_calculation_id!r}) not found")
            chain_id = prior["chain_id"]
            version = prior["version"] + 1
        else:
            chain_id = None  # set to this row's own id below (v1 anchors its chain, mirrors monitoring.py's season_id convention)
            version = 1

        calculation_id = uuid.uuid4().hex
        chain_id = chain_id or calculation_id

        conn.execute(text("""
            INSERT INTO calculations (
                org_id, calculation_id, chain_id, version, supersedes_calculation_id, project_id,
                field_id, field_type, accounting_pathway, monitoring_period_start, monitoring_period_end,
                season_ids, status, snapshot_json, inputs_json, result_json, readiness_json,
                methodology_version, engine_version, bundle_id, final_issuance, created_by
            ) VALUES (
                :org_id, :calculation_id, :chain_id, :version, :supersedes_calculation_id, :project_id,
                :field_id, :field_type, :accounting_pathway, :monitoring_period_start, :monitoring_period_end,
                :season_ids, :status, :snapshot_json, :inputs_json, :result_json, :readiness_json,
                :methodology_version, :engine_version, :bundle_id, :final_issuance, :created_by
            )
        """), {
            "org_id": org_id, "calculation_id": calculation_id, "chain_id": chain_id, "version": version,
            "supersedes_calculation_id": supersedes_calculation_id, "project_id": project_id,
            "field_id": field_id, "field_type": field_type, "accounting_pathway": accounting_pathway,
            "monitoring_period_start": monitoring_period_start, "monitoring_period_end": monitoring_period_end,
            "season_ids": json.dumps(season_ids), "status": status,
            "snapshot_json": json.dumps(snapshot, default=str), "inputs_json": json.dumps(inputs, default=str),
            "result_json": json.dumps(result, default=str), "readiness_json": json.dumps(readiness, default=str),
            "methodology_version": METHODOLOGY_VERSION[accounting_pathway],
            "engine_version": ENGINE_VERSION[accounting_pathway], "bundle_id": bundle_id,
            "final_issuance": result.get("final_issuance"), "created_by": created_by,
        })

        if supersedes_calculation_id is not None:
            conn.execute(
                text("UPDATE calculations SET status = 'superseded' "
                     "WHERE org_id = :org_id AND calculation_id = :cid AND status != 'superseded'"),
                {"org_id": org_id, "cid": supersedes_calculation_id},
            )

        conn.execute(
            text("INSERT INTO calculation_idempotency_keys (org_id, field_id, idempotency_key, calculation_id) "
                 "VALUES (:org_id, :field_id, :key, :cid)"),
            {"org_id": org_id, "field_id": field_id, "key": idempotency_key, "cid": calculation_id},
        )
        for attachment_id in attachment_ids:
            conn.execute(
                text("INSERT INTO calculation_attachment_refs (org_id, calculation_id, attachment_id) "
                     "VALUES (:org_id, :cid, :aid)"),
                {"org_id": org_id, "cid": calculation_id, "aid": attachment_id},
            )
        conn.commit()

    return {"calculation": get_calculation(org_id, calculation_id), "already_committed": False}


def _is_blocking(item: dict) -> bool:
    """A calculation cannot become 'ready_for_review' while any check is
    'missing' or 'needs_review'. 'unsupported' items are surfaced but do
    NOT block by themselves — they describe an engine limitation the user
    is expected to already know is out of scope (documented, not hidden),
    not an outstanding task the user could resolve here."""
    return item["status"] in ("missing", "needs_review")


def referenced_attachment_ids(org_id: str) -> set[str]:
    """Every attachment_id referenced by ANY committed calculation snapshot
    in this org — used to refuse deleting an attachment a snapshot depends
    on (backend/routers/attachments.py)."""
    with get_db_connection() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT attachment_id FROM calculation_attachment_refs WHERE org_id = :org_id"),
            {"org_id": org_id},
        ).fetchall()
    return {r[0] for r in rows}
