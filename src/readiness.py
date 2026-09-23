"""Versioned readiness checklist for evidence-linked calculations.

Each check dict:
    {
        "requirement_id": "vm0051.qa3_pathway_project_size",
        "status": "satisfied" | "missing" | "needs_review" | "not_applicable" | "unsupported",
        "explanation": "...",
        "evidence_references": [{"type": "season", "id": "..."}, ...],
        "source_reference": "VM0051 v1.1 §8.6.3" | None,
        "required_evidence": "..." | None,     # from the methodology registry
        "implementation_support": "implemented" | "partial" | "unsupported" | None,
        "determination": "automated" | "expert",
        "reviewer_authority": "automated_only" | "reviewable" | "expert_required" | None,
        "decided_by": None | user_id,   # only set for a recorded manual determination
        "reason": None | str,
    }

This is NOT a certification of methodology compliance — it only reflects
what this implementation can check automatically, plus whatever a human
has explicitly recorded (src.reviews.record_determination, restricted to
requirements whose reviewer_authority permits it — see that module).
"unsupported" is a permanent, non-overridable status: the requirement is
real but this engine does not implement it, and no determination can
mark it satisfied (see _apply_manual_overrides).

Per docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md Phase 1 gap #1,
methodology_applicability and baseline_documentation are no longer a
bare "field_type matches pathway" / "a schedule dict exists" check —
see _methodology_applicability_check and _alm_checks below.
"""
from src import crop_taxonomy
from src import methodology_registry as registry
from src import monitoring
from src.calculations import PATHWAYS, latest_determinations
from src.database import get_alm_livestock_schedule, get_alm_practice_schedule, get_soc_measurements
from src.field_types.alm_vm0042 import AlmPracticeValidator

EXPERT_REQUIREMENTS = {"common.additionality"}  # always needs_review unless a human recorded a determination

# Static, project-state-independent rows straight from the requirements
# matrix — "this equation/scope is not implemented," true regardless of
# what any specific project has recorded. Surfaced automatically for
# every checklist so a user always sees the full applicability picture,
# not just the subset this module has bespoke Python logic for.
_STATIC_REQUIREMENT_IDS = {
    "vm0051_rice_awd": ["vm0051.leakage_assessment", "vm0051.n2o_baseline_fertilizer", "vm0051.biomass_burning"],
    "vm0042_alm": ["vm0042.new_land_carbon_stock_accounting", "vm0042.liming_co2",
                   "vm0042.quantification_approach", "vm0042.uncertainty_deduction"],
}


def _check(requirement_id, status, explanation, evidence_references=(), bundle_id=None, determination="automated"):
    meta = registry.get_requirement_meta(requirement_id, bundle_id)
    check = {
        "requirement_id": requirement_id, "status": status, "explanation": explanation,
        "evidence_references": list(evidence_references), "determination": determination,
        "decided_by": None, "reason": None,
        "source_reference": None, "required_evidence": None, "implementation_support": None,
        "reviewer_authority": None,
    }
    if meta is not None:
        source_doc = None
        if meta.get("source_document_id"):
            with_doc = registry.list_documents()
            source_doc = next((d for d in with_doc if d["document_id"] == meta["source_document_id"]), None)
        parts = []
        if source_doc:
            parts.append(f"{source_doc['title']}" + (f" v{source_doc['version']}" if source_doc.get("version") else ""))
        if meta.get("source_section"):
            parts.append(meta["source_section"])
        check.update(
            source_reference=" ".join(parts) or None,
            required_evidence=meta["required_evidence"],
            implementation_support=meta["implementation_support"],
            reviewer_authority=meta["reviewer_authority"],
        )
        # A requirement this codebase does not implement is unsupported
        # REGARDLESS of what the dynamic evaluator below concluded —
        # never let project data accidentally look "satisfied" for
        # something the engine can't actually check.
        if meta["implementation_support"] == "unsupported" and status not in ("unsupported", "not_applicable"):
            check["status"] = "unsupported"
    return check


def _apply_manual_overrides(checks: list[dict], org_id: str, field_id: str, pathway: str,
                             bundle_id: str, monitoring_period_start: str, monitoring_period_end: str) -> list[dict]:
    """A recorded determination only applies if it is still IN SCOPE for
    this exact (bundle, reporting period) — see src.reviews.
    record_determination for how a determination is scoped at write time
    and src.reviews.latest_determinations for the matching read here.
    A stale determination (bundle changed, period changed) is treated as
    if none exists — the automated/default status governs again, it is
    never silently carried forward."""
    determinations = latest_determinations(org_id, field_id, pathway, bundle_id,
                                            monitoring_period_start, monitoring_period_end)
    for check in checks:
        decision = determinations.get(check["requirement_id"])
        if decision is None:
            continue
        if check["implementation_support"] == "unsupported":
            continue  # never overridable — enforced again here even though src.reviews already refuses to record one
        check.update(status=decision["status"], decided_by=decision["decided_by"], reason=decision["reason"])
    return checks


def _season_checks(org_id, field_id, season_ids, monitoring_start, monitoring_end, bundle_id):
    checks = []
    if not season_ids:
        checks.append(_check(
            "common.monitoring_period_coverage", "missing",
            "No crop season is linked to this calculation's monitoring period.", bundle_id=bundle_id,
        ))
        return checks

    covered_start, covered_end = None, None
    review_refs = []
    unreviewed = 0
    for sid in season_ids:
        season = monitoring.season(org_id, field_id, sid)
        if season is None:
            checks.append(_check(f"common.season.{sid}", "missing", f"Season {sid} was not found on this field.",
                                  bundle_id=bundle_id))
            continue
        payload = season["payload"]
        covered_start = payload["start_date"] if covered_start is None else min(covered_start, payload["start_date"])
        covered_end = payload["end_date"] if covered_end is None else max(covered_end, payload["end_date"])
        observations = monitoring.records("field_observations", org_id, field_id, sid)
        reviews = monitoring.records("observation_reviews", org_id, field_id, sid)
        for obs in observations:
            obs_reviews = [r for r in reviews if r["payload"]["observation_id"] == obs["id"]]
            latest_review = obs_reviews[-1] if obs_reviews else None
            if latest_review is None or latest_review["payload"]["decision"] != "accepted":
                unreviewed += 1
            review_refs.append({"type": "observation", "id": obs["id"]})

    if covered_start is None:
        checks.append(_check("common.monitoring_period_coverage", "missing",
                              "None of the referenced seasons could be read.", bundle_id=bundle_id))
    elif covered_start > monitoring_start or covered_end < monitoring_end:
        checks.append(_check(
            "common.monitoring_period_coverage", "needs_review",
            f"Linked seasons span {covered_start} to {covered_end}, which does not fully cover "
            f"the requested monitoring period {monitoring_start} to {monitoring_end}.",
            evidence_references=[{"type": "season", "id": s} for s in season_ids], bundle_id=bundle_id,
        ))
    else:
        checks.append(_check(
            "common.monitoring_period_coverage", "satisfied",
            "Linked crop seasons cover the requested monitoring period.",
            evidence_references=[{"type": "season", "id": s} for s in season_ids], bundle_id=bundle_id,
        ))

    if not review_refs:
        checks.append(_check(
            "common.evidence_review_status", "needs_review",
            "No field observations are recorded for the linked seasons yet.", bundle_id=bundle_id,
        ))
    elif unreviewed:
        checks.append(_check(
            "common.evidence_review_status", "needs_review",
            f"{unreviewed} of {len(review_refs)} field observations are not yet accepted by an independent reviewer.",
            evidence_references=review_refs, bundle_id=bundle_id,
        ))
    else:
        checks.append(_check(
            "common.evidence_review_status", "satisfied",
            f"All {len(review_refs)} field observations for the linked seasons are reviewer-accepted.",
            evidence_references=review_refs, bundle_id=bundle_id,
        ))
    return checks


def _declared_crops(org_id, field_id, season_ids):
    crops = set()
    for sid in season_ids:
        season = monitoring.season(org_id, field_id, sid)
        if season is not None:
            crops.update(season["payload"].get("crops", []))
    return crops


def _methodology_applicability_check(org_id, field, accounting_pathway, season_ids, bundle_id):
    """Substantive, evidence-based applicability — NOT a bare field_type/
    pathway match (docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md Phase
    1 gap #1). Cross-checks the pathway against the crop(s) actually
    DECLARED in the field's linked crop seasons, using src.crop_taxonomy,
    rather than trusting field_type alone. Field_type is still checked
    first since it remains the immutable, structural methodology
    selector — this adds a second, evidence-based signal on top."""
    checks = []
    expected_pathway = PATHWAYS.get(field["field_type"])
    if accounting_pathway != expected_pathway:
        checks.append(_check(
            "common.methodology_applicability", "not_applicable",
            f"Field type '{field['field_type']}' does not support pathway '{accounting_pathway}'.",
            bundle_id=bundle_id,
        ))
        return checks

    declared = _declared_crops(org_id, field["field_id"], season_ids)
    classifications = {c: crop_taxonomy.classify(c) for c in declared}
    unrecognized = [c for c, cls in classifications.items() if not cls["recognized"]]
    if not declared:
        checks.append(_check(
            "common.methodology_applicability", "needs_review",
            "No crop is declared in the linked seasons yet — applicability cannot be evidenced from crop "
            "declarations alone.", bundle_id=bundle_id,
        ))
    elif unrecognized:
        checks.append(_check(
            "common.methodology_applicability", "needs_review",
            f"Declared crop(s) not in the recognized taxonomy: {sorted(unrecognized)}. A reviewer must "
            "confirm applicability manually.", bundle_id=bundle_id,
        ))
    else:
        eligibility_key = "vm0051_eligible" if accounting_pathway == "vm0051_rice_awd" else "alm_eligible"
        ineligible = [c for c, cls in classifications.items() if not cls[eligibility_key]]
        if ineligible:
            checks.append(_check(
                "common.methodology_applicability", "needs_review",
                f"Declared crop(s) {sorted(ineligible)} are not in this pathway's usual scope per crop "
                "taxonomy — a reviewer must confirm applicability.", bundle_id=bundle_id,
            ))
        else:
            checks.append(_check(
                "common.methodology_applicability", "satisfied",
                f"Field type and declared crop(s) {sorted(classifications)} are within pathway "
                f"'{accounting_pathway}''s usual scope.", bundle_id=bundle_id,
            ))

    if accounting_pathway == "vm0042_alm":
        rice_declared = any(cls.get("key") == "rice" for cls in classifications.values())
        checks.append(_check(
            "vm0042.excludes_wetland_rice",
            "unsupported" if rice_declared else "not_applicable",
            "Rice is declared for a VM0042 (ALM) field. VM0042 excludes wetland/flooded-rice cropland "
            "(§4 applicability condition 8); rice SOC claims require a separate applicability and "
            "implementation assessment this codebase does not have. This cannot be marked satisfied by "
            "a reviewer determination."
            if rice_declared else
            "No rice declared — VM0042's wetland/flooded-rice exclusion does not apply here.",
            bundle_id=bundle_id,
        ))
    return checks


def _rice_checks(org_id, field_id, engine_inputs, preview_result, bundle_id):
    checks = [_check(
        "vm0051.required_measurement_inputs",
        "satisfied" if engine_inputs.get("awd_events") is not None and engine_inputs.get("season_length_days")
        else "missing",
        "AWD event count and season length are the engine's required satellite-derived inputs.",
        bundle_id=bundle_id,
    )]
    if preview_result is not None:
        if preview_result.get("qa3_pathway_valid") is False:
            checks.append(_check(
                "vm0051.qa3_pathway_project_size", "needs_review",
                preview_result.get("qa3_block_reason") or "Project exceeds the QA3 60,000 tCO2e/yr gate.",
                bundle_id=bundle_id,
            ))
        else:
            checks.append(_check(
                "vm0051.qa3_pathway_project_size", "satisfied",
                "Estimated annual reductions are within the QA3 default-emission-factors project-size gate.",
                bundle_id=bundle_id,
            ))
    else:
        checks.append(_check("vm0051.qa3_pathway_project_size", "needs_review",
                              "Run a calculation preview to evaluate the QA3 project-size gate.", bundle_id=bundle_id))
    for requirement_id in _STATIC_REQUIREMENT_IDS["vm0051_rice_awd"]:
        meta = registry.get_requirement_meta(requirement_id, bundle_id)
        checks.append(_check(requirement_id, "unsupported", meta["required_evidence"] if meta else "Not implemented.",
                              bundle_id=bundle_id))
    return checks


def _alm_checks(org_id, field_id, season_ids, monitoring_period_start, engine_inputs, preview_result, bundle_id):
    checks = []
    practice_schedule = get_alm_practice_schedule(org_id, field_id)
    soc_measurements = get_soc_measurements(org_id, field_id)
    problems = AlmPracticeValidator().check_completeness(practice_schedule, soc_measurements)

    # Substantive baseline check (Phase 1 gap #1): a baseline SCHEDULE
    # existing is not itself a historical record — also require at least
    # one crop-season record that predates the monitoring period start,
    # explicitly labeled as a minimum evidentiary bar, not full look-back
    # verification (which would need a documented look-back length this
    # codebase does not have sourced from the methodology yet).
    historical_seasons = [
        s for s in monitoring.records("crop_seasons", org_id, field_id)
        if s["payload"]["start_date"] < monitoring_period_start
    ]
    if not practice_schedule.get("baseline"):
        checks.append(_check("vm0042.baseline_documentation", "missing",
                              "Baseline practice schedule is missing.", bundle_id=bundle_id))
    elif not historical_seasons:
        checks.append(_check(
            "vm0042.baseline_documentation", "needs_review",
            "A baseline practice schedule is recorded, but no crop-season record predates the monitoring "
            "period — historical activity evidence is incomplete. This is a minimum evidentiary bar, not "
            "confirmation of the full applicable look-back period.", bundle_id=bundle_id,
        ))
    else:
        checks.append(_check(
            "vm0042.baseline_documentation", "satisfied",
            f"Baseline practice schedule is recorded, and {len(historical_seasons)} historical crop-season "
            "record(s) predate the monitoring period.", bundle_id=bundle_id,
        ))

    soc_problems = [p for p in problems if p.startswith("SOC samples")]
    if soc_problems:
        checks.append(_check("vm0042.soc_measurements", "missing", " ".join(soc_problems), bundle_id=bundle_id))
    else:
        checks.append(_check("vm0042.soc_measurements", "satisfied",
                              "Paired project/control SOC samples are recorded at both timepoints.",
                              bundle_id=bundle_id))
    if not practice_schedule.get("project"):
        checks.append(_check("vm0042.project_practice_schedule", "missing", "Project practice schedule is missing.",
                              bundle_id=bundle_id))
    else:
        checks.append(_check("vm0042.project_practice_schedule", "satisfied", "Project practice schedule is recorded.",
                              bundle_id=bundle_id))

    livestock = get_alm_livestock_schedule(org_id, field_id)
    if not livestock.get("baseline") and not livestock.get("project"):
        checks.append(_check("vm0042.integrated_livestock_scope", "not_applicable",
                              "No livestock schedule recorded — the integrated crop-livestock scope does not apply.",
                              bundle_id=bundle_id))
    else:
        checks.append(_check("vm0042.integrated_livestock_scope", "satisfied",
                              "Livestock schedule recorded for the integrated crop-livestock scope.",
                              bundle_id=bundle_id))

    if preview_result is not None and preview_result.get("production_decline_leakage_blocked"):
        checks.append(_check(
            "vm0042.production_decline_leakage", "needs_review",
            preview_result.get("leakage_block_reason") or "Genuine production-decline leakage detected.",
            bundle_id=bundle_id,
        ))
    else:
        checks.append(_check(
            "vm0042.production_decline_leakage", "satisfied" if preview_result is not None else "needs_review",
            "No production-decline leakage flagged." if preview_result is not None
            else "Run a calculation preview to evaluate production-decline leakage.", bundle_id=bundle_id,
        ))
    for requirement_id in _STATIC_REQUIREMENT_IDS["vm0042_alm"]:
        meta = registry.get_requirement_meta(requirement_id, bundle_id)
        checks.append(_check(requirement_id, "unsupported" if meta and meta["implementation_support"] == "unsupported"
                              else "satisfied",
                              meta["required_evidence"] if meta else "Not implemented.", bundle_id=bundle_id))
    return checks


def build_readiness_checklist(org_id, field, accounting_pathway, season_ids, monitoring_period_start,
                               monitoring_period_end, engine_inputs, preview_result=None, project_id=None):
    field_id = field["field_id"]
    bundle = registry.resolve_bundle_for_project(org_id, project_id, accounting_pathway)
    bundle_id = bundle["bundle_id"] if bundle else None

    checks = _methodology_applicability_check(org_id, field, accounting_pathway, season_ids, bundle_id)
    checks += _season_checks(org_id, field_id, season_ids, monitoring_period_start, monitoring_period_end, bundle_id)
    if accounting_pathway == "vm0051_rice_awd":
        checks += _rice_checks(org_id, field_id, engine_inputs, preview_result, bundle_id)
    elif accounting_pathway == "vm0042_alm":
        checks += _alm_checks(org_id, field_id, season_ids, monitoring_period_start, engine_inputs, preview_result, bundle_id)

    for requirement_id in EXPERT_REQUIREMENTS:
        checks.append(_check(
            requirement_id, "needs_review",
            "Additionality is an expert determination, not something this implementation can check "
            "automatically — a reviewer must record a decision explicitly.",
            bundle_id=bundle_id, determination="expert",
        ))

    checks = _apply_manual_overrides(checks, org_id, field_id, accounting_pathway, bundle_id,
                                      monitoring_period_start, monitoring_period_end)
    return checks, bundle_id


def guided_enrollment(org_id: str, field: dict) -> dict:
    """A lighter-weight view than the full calculation-context readiness
    checklist — usable BEFORE a user has chosen a monitoring period or
    entered engine inputs (docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md
    Phase 2: "Add guided enrollment that explains eligible pathways and
    missing evidence."). Reports what pathway this field's type maps to,
    what crops are actually declared across ALL of its crop seasons (not
    scoped to any particular calculation), a taxonomy-based eligibility
    signal for each, this pathway's unsupported/partial scope straight
    from the registry, and the most basic evidence-presence facts —
    never a full substitute for build_readiness_checklist's per-
    calculation evaluation."""
    field_id = field["field_id"]
    accounting_pathway = PATHWAYS.get(field["field_type"])
    bundle = registry.resolve_bundle_for_project(org_id, None, accounting_pathway) if accounting_pathway else None
    bundle_id = bundle["bundle_id"] if bundle else None

    all_seasons = monitoring.records("crop_seasons", org_id, field_id)
    declared = set()
    for s in all_seasons:
        declared.update(s["payload"].get("crops", []))
    crop_info = [crop_taxonomy.classify(c) for c in sorted(declared)]

    unsupported_scope = []
    if bundle_id:
        for req in registry.list_requirements(bundle_id):
            if req["implementation_support"] in ("unsupported", "partial"):
                unsupported_scope.append({
                    "requirement_id": req["requirement_id"], "title": req["title"],
                    "implementation_support": req["implementation_support"],
                    "required_evidence": req["required_evidence"],
                })

    missing_evidence = []
    if not all_seasons:
        missing_evidence.append("No crop seasons recorded yet.")
    if accounting_pathway == "vm0042_alm":
        practice_schedule = get_alm_practice_schedule(org_id, field_id)
        if not practice_schedule.get("baseline"):
            missing_evidence.append("Baseline practice schedule is missing.")
        if not practice_schedule.get("project"):
            missing_evidence.append("Project practice schedule is missing.")
        soc = get_soc_measurements(org_id, field_id)
        if len(soc) < 4:
            missing_evidence.append("Paired project/control SOC samples are incomplete.")
    elif accounting_pathway == "vm0051_rice_awd":
        from src.database import get_latest_signal_result
        if get_latest_signal_result(org_id, field_id) is None:
            missing_evidence.append("No signal-analytics (satellite AWD) run recorded yet.")

    return {
        "field_type": field["field_type"], "accounting_pathway": accounting_pathway,
        "methodology_bundle": bundle, "declared_crops": crop_info,
        "unsupported_or_partial_scope": unsupported_scope, "missing_evidence": missing_evidence,
    }
