"""Builds the immutable evidence bundle for one calculation commit
(Phase 2 — see src/calculations.py's module docstring).

build_snapshot() is the SINGLE read pass a commit uses: every record it
embeds is read once, here, and the same dict is both what gets persisted
AND (via its "engine_inputs"/schedule/measurement values) what the
calculation engine actually computes from — a caller must not read
records again afterward to "fill in" the snapshot, which is exactly the
drift this function exists to prevent.
"""
from src import methodology_registry as registry
from src import monitoring
from src import projects as projects_db
from src.database import get_alm_livestock_schedule, get_alm_practice_schedule


def build_snapshot(org_id: str, field: dict, project_id: str | None, accounting_pathway: str,
                    season_ids: list[str], monitoring_period_start: str, monitoring_period_end: str,
                    engine_inputs: dict, monitoring_run_ids: list[str], attachment_ids: list[str]) -> dict:
    field_id = field["field_id"]
    from src.readiness import compute_evidence_fingerprint
    initial_fingerprint = compute_evidence_fingerprint(org_id, field_id, accounting_pathway, season_ids, project_id)

    seasons = []
    for sid in season_ids:
        season = monitoring.season(org_id, field_id, sid)
        if season is None:
            raise ValueError(f"Crop season {sid!r} not found on this field")
        seasons.append({
            "season_id": sid,
            "version": season["payload"].get("version", 1),
            "season": season,
            "practice_events": monitoring.records("practice_events", org_id, field_id, sid),
            "observations": monitoring.records("field_observations", org_id, field_id, sid),
            "reviews": monitoring.records("observation_reviews", org_id, field_id, sid),
        })

    runs = []
    for run_id in monitoring_run_ids:
        matches = [r for sid in season_ids
                   for r in monitoring.records("monitoring_runs", org_id, field_id, sid) if r["id"] == run_id]
        if not matches:
            raise ValueError(f"Monitoring run {run_id!r} not found under the linked seasons")
        runs.append(matches[0])

    attachments = []
    for attachment_id in attachment_ids:
        attachment = projects_db.get_attachment(org_id, attachment_id)
        if attachment is None or attachment["field_id"] != field_id:
            raise ValueError(f"Attachment {attachment_id!r} not found on this field")
        attachments.append(attachment)

    # Freeze the applicable methodology bundle into the snapshot itself
    # (docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md Phase 1, deliverable:
    # "every readiness outcome identifies the applicable rule... Preserve
    # immutable historical results") — a full copy of the bundle + its
    # documents (ids, versions, hashes), not just a bundle_id, so this
    # snapshot stays self-describing even if the registry seed data is
    # later edited or a document is replaced.
    methodology_bundle = registry.resolve_bundle_for_project(org_id, project_id, accounting_pathway)

    snapshot = {
        "schema_version": "calculation-snapshot-v3",
        "field": {
            "field_id": field_id, "name": field["name"], "district": field["district"],
            "area_ha": field["area_ha"], "field_type": field["field_type"],
            "geojson_geometry": field["geojson_geometry"],
        },
        "project_id": project_id,
        "accounting_pathway": accounting_pathway,
        "monitoring_period": {"start": monitoring_period_start, "end": monitoring_period_end},
        "methodology_bundle": methodology_bundle,
        "seasons": seasons,
        "monitoring_runs": runs,
        "attachments": attachments,
        "engine_inputs": engine_inputs,
    }

    if accounting_pathway == "vm0042_alm":
        from src.production_records import leakage_snapshot
        snapshot["leakage_evidence"] = leakage_snapshot(
            org_id, field_id, project_id, (methodology_bundle or {}).get("bundle_id"),
            monitoring_period_start, monitoring_period_end,
        )
        from src.database import get_alm_cumulative_delta
        from src import soil_evidence as soil_evidence_db
        snapshot["alm_practice_schedule"] = get_alm_practice_schedule(org_id, field_id)
        snapshot["alm_livestock_schedule"] = get_alm_livestock_schedule(org_id, field_id)

        # THE actual engine input, resolved cell-by-cell: a current,
        # reviewer-adopted set of specific sample rows when one exists
        # (raw per-sample values preserved, never pre-averaged, so the
        # engine's own Eq. 70/71 variance-from-replicates calculation is
        # unaffected), else the legacy manually-entered aggregate,
        # honestly labeled either way — see
        # src.soil_evidence.resolved_soc_measurements's docstring. Both
        # the resolved values AND the full per-cell provenance (review id,
        # sample ids, reviewer, reason, decided_at, evidence fingerprint OR
        # "legacy_aggregate" note) are frozen into the snapshot, never
        # re-derived later.
        resolved = soil_evidence_db.resolved_soc_measurements(org_id, field_id)
        snapshot["soc_measurements"] = {
            f"{site}_{tp}": cell["values"] for (site, tp), cell in resolved.items()
        }
        snapshot["soc_measurements_provenance"] = {
            f"{site}_{tp}": {k: v for k, v in cell.items() if k != "values"}
            for (site, tp), cell in resolved.items()
        }
        # Read once, frozen into the snapshot — the calculation engine
        # computes from THIS value, never a second live read at commit time.
        snapshot["prior_cumulative_delta_co2_wp_t"] = get_alm_cumulative_delta(org_id, field_id)

        # Full soil evidence (Phase 3, Part B.7, extended): every plan,
        # stratum, sample, per-analyte lab result, chain-of-custody event,
        # and evidence review decided for this field — frozen for
        # reference/audit even where a cell above resolved to the legacy
        # aggregate instead of a reviewed sample set (so a reviewer can
        # still see what evidence existed and why it wasn't — or was —
        # adopted at commit time).
        plans = soil_evidence_db.list_plans(org_id, field_id)
        samples_by_plan = {p["plan_id"]: soil_evidence_db.list_samples(org_id, p["plan_id"]) for p in plans}
        for samples in samples_by_plan.values():
            for s in samples:
                s["lab_results"] = soil_evidence_db.list_lab_results(org_id, s["sample_id"])
                s["custody_events"] = soil_evidence_db.list_custody_events(org_id, s["sample_id"])
        snapshot["soil_evidence"] = {
            "plans": [{**p, "strata": soil_evidence_db.list_strata(org_id, p["plan_id"]),
                       "samples": samples_by_plan[p["plan_id"]]} for p in plans],
            "reviews": {
                f"{site}_{tp}": soil_evidence_db.latest_soc_evidence_review(org_id, field_id, site, tp)
                for site in sorted(soil_evidence_db.SITE_TYPES) for tp in sorted(soil_evidence_db.TIMEPOINTS)
            },
            "note": "Full soil sampling evidence, frozen for reference. See soc_measurements_provenance "
                    "above for exactly which cells this calculation actually used a reviewed sample set for, "
                    "versus the legacy aggregate.",
        }

    final_fingerprint = compute_evidence_fingerprint(org_id, field_id, accounting_pathway, season_ids, project_id)
    if final_fingerprint != initial_fingerprint:
        raise ValueError("Evidence changed while building the snapshot. Refresh and try again.")
    snapshot["evidence_fingerprint"] = final_fingerprint
    return snapshot


def _decode_soc_measurements(flat: dict) -> dict:
    decoded = {}
    for key, values in flat.items():
        site, _, timepoint = key.partition("_")
        # site_type is one of 'project'/'control' (no underscore itself),
        # so partition on the first "_" cleanly separates it from timepoint
        # ('t_start'/'t_final').
        decoded[(site, timepoint)] = values
    return decoded


def calculate_from_snapshot(snapshot: dict) -> dict:
    """Computes calculate_credits() using ONLY values already frozen into
    the snapshot — never re-reads the database. Used identically by the
    stateless preview endpoint and the commit path, so a preview and its
    immediately-following commit (same snapshot) always agree."""
    from src.field_types.registry import build_methodology

    pathway = snapshot["accounting_pathway"]
    field = snapshot["field"]
    inputs = snapshot["engine_inputs"]
    engine = build_methodology(field["field_type"])

    if pathway == "vm0051_rice_awd":
        return engine.calculate_credits(
            awd_events=inputs["awd_events"],
            season_length_days=inputs["season_length_days"],
            area_ha=field["area_ha"],
            q_n_kg_per_ha=inputs.get("q_n_kg_per_ha", 100.0),
            preseason_category=inputs.get("preseason_category", "short"),
            baseline_amendments=inputs.get("baseline_amendments"),
            project_amendments=inputs.get("project_amendments"),
        )
    from src.leakage_vmd0054 import calculate_frozen_leakage
    leakage = calculate_frozen_leakage(snapshot.get("leakage_evidence", {}),
        snapshot.get("methodology_bundle"), snapshot["monitoring_period"], inputs.get("verification_years", 1.0))
    return engine.calculate_credits(
        practice_schedule=snapshot["alm_practice_schedule"],
        soc_measurements=_decode_soc_measurements(snapshot["soc_measurements"]),
        area_ha=field["area_ha"],
        verification_years=inputs.get("verification_years", 1.0),
        non_permanence_risk_pct=inputs.get("non_permanence_risk_pct", 20.0),
        prior_cumulative_delta_co2_wp_t=snapshot["prior_cumulative_delta_co2_wp_t"],
        baseline_livestock=snapshot["alm_livestock_schedule"].get("baseline"),
        project_livestock=snapshot["alm_livestock_schedule"].get("project"),
        leakage_result=leakage,
    )
