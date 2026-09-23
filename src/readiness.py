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
    "vm0042_alm": ["vm0042.leakage_step2_mitigation", "vm0042.leakage_step3_land_impact",
                   "vm0042.leakage_step4_new_land_carbon_stock", "vm0042.leakage_step5_emissions",
                   "vm0042.liming_co2", "vm0042.quantification_approach", "vm0042.uncertainty_deduction",
                   "vm0042.soc_sampling_traceability"],
}

# Real, sourced VM0042 v2.2 figure (not invented) — see the "Historical
# look-back period" definition and "Development of Schedule of Activities
# in the Baseline Scenario" section: "at minimum three years and one
# complete crop rotation."
_HISTORICAL_LOOKBACK_MIN_YEARS = 3


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
                             bundle_id: str, monitoring_period_start: str, monitoring_period_end: str,
                             evidence_fingerprint: str) -> list[dict]:
    """A recorded determination only applies if it is still IN SCOPE for
    this exact (bundle, reporting period, evidence fingerprint) — see
    src.calculations.record_determination for how a determination is
    scoped at write time and src.calculations.latest_determinations for
    the matching read here. A stale determination (bundle changed,
    period changed, OR the underlying evidence changed even with the
    same bundle/period) is treated as if none exists — the automated/
    default status governs again, it is never silently carried forward."""
    determinations = latest_determinations(org_id, field_id, pathway, bundle_id,
                                            monitoring_period_start, monitoring_period_end, evidence_fingerprint)
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


def compute_evidence_fingerprint(org_id: str, field_id: str, accounting_pathway: str, season_ids: list[str]) -> str:
    """A hash of every record that could change what an automated
    readiness check concludes for this field/pathway — used to
    invalidate a manual determination when the underlying EVIDENCE
    changes, even if the bundle and reporting period are unchanged
    (docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md follow-up review,
    item 3: "Invalidate decisions when relevant evidence changes, even
    if the bundle and dates remain unchanged.").

    Deliberately FIELD-WIDE, not scoped to just `season_ids`: checks like
    vm0042.historical_lookback read every crop-season on the field (to
    find historical/look-back seasons outside the linked project-period
    season_ids) — a fingerprint that only hashed season_ids would miss a
    newly added historical season entirely (verified: this was an actual
    bug caught while testing this exact function, not a hypothetical).
    `season_ids` is accepted for API-signature symmetry with the rest of
    this module and to stay ready for a future finer-grained scope, but
    is deliberately NOT used to narrow what gets hashed today — being
    coarse (any change anywhere invalidates every determination for this
    field/pathway) is the safe direction; under-invalidating a stale
    approval is not."""
    payload = {
        "season_versions": sorted(
            (s["id"], s["created_at"]) for s in monitoring.records("crop_seasons", org_id, field_id)
        ),
        "observations": sorted(
            (o["id"], o["created_at"]) for o in monitoring.records("field_observations", org_id, field_id)
        ),
        "reviews": sorted(
            (r["id"], r["created_at"]) for r in monitoring.records("observation_reviews", org_id, field_id)
        ),
        "practice_events": sorted(
            (p["id"], p["created_at"]) for p in monitoring.records("practice_events", org_id, field_id)
        ),
    }
    if accounting_pathway == "vm0042_alm":
        payload["practice_schedule"] = get_alm_practice_schedule(org_id, field_id)
        payload["soc_measurements"] = {f"{s}_{t}": v for (s, t), v in get_soc_measurements(org_id, field_id).items()}
        payload["livestock_schedule"] = get_alm_livestock_schedule(org_id, field_id)
    return monitoring.digest(payload)


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
        # Crop taxonomy gives a coarse, indicative signal only — it is
        # NEVER sufficient on its own to mark full methodology
        # applicability 'satisfied' (docs/RESEARCH_IMPLEMENTATION_PLAN_
        # 2026-09-23.md's follow-up review, item 4). Actual applicability
        # depends on land-use conditions (e.g. real water regime,
        # drainage, prior land use) this codebase does not measure, so
        # the automated ceiling here is always 'needs_review' — only an
        # explicit reviewer determination (reviewer_authority=
        # 'reviewable') can move this to 'satisfied', after confirming
        # those conditions independently of the crop name alone.
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
                "common.methodology_applicability", "needs_review",
                f"Declared crop(s) {sorted(classifications)} are within pathway '{accounting_pathway}''s "
                "usual scope per crop taxonomy alone — this is an indicative signal, not a full "
                "applicability determination. Actual land-use conditions (e.g. water regime, drainage, "
                "prior land use) must still be confirmed by a reviewer before this can be marked satisfied.",
                bundle_id=bundle_id,
            ))

    if accounting_pathway == "vm0042_alm":
        # NOT "rice is wetland" as a crop-identity fact — crop identity
        # and land-use condition are deliberately kept separate (see
        # src.crop_taxonomy's docstring). The real, narrower claim: this
        # codebase has NOT implemented any rice-SOC applicability or
        # quantification assessment under VM0042 at all, in any water
        # regime, and VM0042 §4 condition 8 excludes wetland/flooded-rice
        # cropland specifically — so a rice declaration under this
        # pathway is treated as unsupported pending that dedicated
        # implementation, not because rice is assumed to be wetland.
        rice_declared = any(cls.get("key") == "rice" for cls in classifications.values())
        checks.append(_check(
            "vm0042.excludes_wetland_rice",
            "unsupported" if rice_declared else "not_applicable",
            "Rice is declared for a VM0042 (ALM) field. This codebase has not implemented a rice-SOC "
            "applicability or quantification assessment under VM0042 in any water regime — VM0042 §4 "
            "condition 8 excludes wetland/flooded-rice cropland specifically, and confirming whether a "
            "given rice field falls outside that exclusion (e.g. via documented water-regime/drainage "
            "evidence) is exactly the missing implementation, not a fact assumed from the crop name. This "
            "cannot be marked satisfied by a reviewer determination."
            if rice_declared else
            "No rice declared — VM0042's wetland/flooded-rice exclusion does not apply here.",
            bundle_id=bundle_id,
        ))
    return checks


def _historical_lookback_check(org_id, field_id, season_ids, monitoring_period_start, practice_schedule, bundle_id):
    """Substantive VM0042 historical look-back check (Phase 1 gap #2,
    strengthened, then split per docs/RESEARCH_IMPLEMENTATION_PLAN_2026-
    09-23.md Phase 3 Priority 5): the methodology's OWN text requires
    "at minimum three years and one complete crop rotation" immediately
    preceding the project start date, used to build the baseline
    schedule of activities (see the registry's vm0042.historical_lookback
    and vm0042.rotation_completeness entries for exact citations). This
    function covers ONLY the date-coverage half of that requirement —
    actual DAY-BY-DAY coverage of the 3-year window, where a gap
    explicitly recorded as a "fallow" season counts as documented
    coverage (a known, observed state) but a "missing_period" season
    does NOT (VM0042 §6 requires practices to be "determined" for the
    look-back years — a documented ADMISSION that a period's activity is
    unknown is not itself evidence of what happened during it, so it
    must not silently count as coverage). Rotation completeness is a
    separate, distinct concern handled by _rotation_completeness_check
    below — VM0042's own text ties "complete crop rotation" to whether
    the BASELINE schedule of activities itself cycles through a full
    rotation, not to whether a later project-period crop happens to
    match history (a newly introduced project-period crop is an
    explicitly permitted "Improved agricultural land management
    practice" per VM0042's own definition — see that function's
    docstring)."""
    from datetime import date, timedelta

    start = date.fromisoformat(monitoring_period_start)
    lookback_start = date.fromordinal(start.toordinal() - 365 * _HISTORICAL_LOOKBACK_MIN_YEARS)
    all_seasons = monitoring.records("crop_seasons", org_id, field_id)

    covered_days = set()
    documented_gaps = []
    undocumented_gap = False
    historical_crops = set()
    for s in all_seasons:
        p = s["payload"]
        s_start, s_end = date.fromisoformat(p["start_date"]), date.fromisoformat(p["end_date"])
        clip_start, clip_end = max(s_start, lookback_start), min(s_end, start - timedelta(days=1))
        if clip_start > clip_end:
            continue
        historical_crops.update(p.get("crops", []))
        if p.get("season_type") == "missing_period":
            # Documented as a KNOWN gap, but a missing_period explicitly
            # records that the activity during it is NOT known — it must
            # not count toward "practices were determined" coverage.
            documented_gaps.append({"season_id": s["id"], "season_type": p["season_type"],
                                     "start_date": p["start_date"], "end_date": p["end_date"]})
            continue
        for ordinal in range(clip_start.toordinal(), clip_end.toordinal() + 1):
            covered_days.add(ordinal)
        if p.get("season_type") == "fallow":
            documented_gaps.append({"season_id": s["id"], "season_type": p["season_type"],
                                     "start_date": p["start_date"], "end_date": p["end_date"]})

    total_window_days = (start - lookback_start).days
    coverage_ratio = len(covered_days) / total_window_days if total_window_days else 1.0
    gap_refs = [{"type": "season", "id": g["season_id"]} for g in documented_gaps]

    if coverage_ratio >= 0.97:
        status = "satisfied"
        explanation = (
            f"Historical records cover {len(covered_days)} of {total_window_days} days in the "
            f"{_HISTORICAL_LOOKBACK_MIN_YEARS}-year look-back window ending at the monitoring period start "
            f"({len(documented_gaps)} gap period(s) explicitly documented as fallow/missing)."
        )
    elif coverage_ratio >= 0.5 and documented_gaps:
        status = "needs_review"
        explanation = (
            f"Historical records cover {len(covered_days)} of {total_window_days} days in the look-back "
            f"window ({len(documented_gaps)} gap period(s) explicitly documented as fallow/missing) — a "
            "reviewer must confirm the documented gaps do not undermine the look-back requirement."
        )
    else:
        status = "missing"
        explanation = (
            f"Historical activity records cover only {len(covered_days)} of {total_window_days} days "
            f"required by VM0042's minimum {_HISTORICAL_LOOKBACK_MIN_YEARS}-year look-back period, with "
            "undocumented gaps (no fallow/missing_period season recorded, or missing_period days not "
            "otherwise covered by another recorded season)."
        )
    return _check("vm0042.historical_lookback", status, explanation, evidence_references=gap_refs,
                   bundle_id=bundle_id), historical_crops


def _rotation_completeness_check(org_id, field_id, historical_crops, practice_schedule, bundle_id):
    """VM0042 §6 ("Development of Schedule of Activities in the Baseline
    Scenario"): "must include at least one complete crop rotation, where
    applicable. Where a crop rotation is not implemented in the
    baseline, x >= 3 years [alone applies]." So this requirement is
    ONLY about whether the BASELINE's own historical schedule evidences
    a full rotation cycle — NOT about whether a project-period crop
    happens to match history. A crop newly introduced as a project
    activity (VM0042's own "Improved agricultural land management
    practice" definition explicitly includes "crop planting and
    harvesting" changes) is a legitimate project design choice, not a
    baseline-documentation defect, so it is never penalized here.

    Limitation (disclosed, not silently assumed away): this cannot
    verify true agronomic rotation-cycle completeness (e.g., that a
    declared N-crop rotation returns to its starting crop) without a
    recorded rotation plan/cycle length, which this codebase does not
    collect. It uses a weaker, honestly-labeled proxy: when the
    baseline practice schedule declares crop_rotation=True, the
    look-back window must show at least 2 distinct historical crops as
    minimal evidence that *some* rotation actually occurred (not just a
    single continuously-repeated crop under a mislabeled flag)."""
    baseline = (practice_schedule or {}).get("baseline") or {}
    if not baseline.get("crop_rotation"):
        return _check(
            "vm0042.rotation_completeness", "not_applicable",
            "Baseline practice schedule does not declare a crop rotation (VM0042 §6: where a rotation is "
            "not implemented in the baseline, the 3-year look-back window alone applies) — see "
            "vm0042.historical_lookback for that check.",
            bundle_id=bundle_id,
        )
    if len(historical_crops) >= 2:
        return _check(
            "vm0042.rotation_completeness", "satisfied",
            f"Baseline declares a crop rotation, and the historical look-back window records "
            f"{len(historical_crops)} distinct crop(s) ({sorted(historical_crops)}) — minimal evidence a "
            "rotation actually occurred. This does not verify the rotation returns to its starting crop "
            "(no rotation-cycle length is recorded by this system) — a reviewer should confirm agronomic "
            "completeness against the project's actual rotation plan.",
            bundle_id=bundle_id,
        )
    return _check(
        "vm0042.rotation_completeness", "needs_review",
        "Baseline practice schedule declares a crop rotation, but the historical look-back window records "
        f"{len(historical_crops)} distinct crop(s) — insufficient to evidence a rotation cycle occurred. "
        "A reviewer must confirm the baseline schedule genuinely reflects a complete crop rotation.",
        bundle_id=bundle_id,
    )


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

    if not practice_schedule.get("baseline"):
        checks.append(_check("vm0042.baseline_documentation", "missing",
                              "Baseline practice schedule is missing.", bundle_id=bundle_id))
    else:
        checks.append(_check("vm0042.baseline_documentation", "satisfied",
                              "Baseline practice schedule is recorded.", bundle_id=bundle_id))
    # Substantive historical look-back check (Phase 1 gap #2, strengthened
    # further per the follow-up review, then split into two distinct
    # checks per docs/RESEARCH_IMPLEMENTATION_PLAN_2026-09-23.md Phase 3
    # Priority 5): date-coverage vs. rotation-completeness are evaluated
    # separately, since VM0042's own text treats them as distinct
    # conditions — see both functions' docstrings.
    lookback_check, historical_crops = _historical_lookback_check(
        org_id, field_id, season_ids, monitoring_period_start, practice_schedule, bundle_id
    )
    checks.append(lookback_check)
    checks.append(_rotation_completeness_check(org_id, field_id, historical_crops, practice_schedule, bundle_id))

    soc_problems = [p for p in problems if p.startswith("SOC samples")]
    if soc_problems:
        checks.append(_check("vm0042.soc_measurements", "missing", " ".join(soc_problems), bundle_id=bundle_id))
    else:
        checks.append(_check("vm0042.soc_measurements", "satisfied",
                              "Paired project/control SOC samples are recorded at both timepoints.",
                              bundle_id=bundle_id))

    # Dynamic — only relevant when a non-annual verification period is
    # actually requested (see src/carbon_calculator_alm.py's
    # _soc_stock_change docstring for the full reconciliation). 'unsupported'
    # here also hard-blocks the commit itself (src.issuance.result_is_issuable
    # checks the engine's own soc_uncertainty_annualization_unresolved flag
    # unconditionally) — this checklist entry is for visibility BEFORE a
    # user attempts to commit, not the actual enforcement point.
    verification_years = engine_inputs.get("verification_years", 1.0)
    if verification_years == 1.0:
        checks.append(_check(
            "vm0042.soc_uncertainty_annualization", "not_applicable",
            "Annual (verification_years=1) SOC verification period — the Eq. 46/47 vs. 70/71 time-basis "
            "concern does not manifest.", bundle_id=bundle_id,
        ))
    else:
        checks.append(_check(
            "vm0042.soc_uncertainty_annualization", "unsupported",
            f"verification_years={verification_years} requests a non-annual SOC verification period. "
            "This will be refused at commit time.", bundle_id=bundle_id,
        ))
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
            "vm0042.leakage_step1_production_change", "needs_review",
            preview_result.get("leakage_block_reason") or "Genuine production-decline leakage detected.",
            bundle_id=bundle_id,
        ))
    else:
        checks.append(_check(
            "vm0042.leakage_step1_production_change", "satisfied" if preview_result is not None else "needs_review",
            "No production-decline leakage flagged (approximate Step 1 screen only — see this "
            "requirement's required_evidence for what is and isn't implemented)."
            if preview_result is not None
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

    evidence_fingerprint = compute_evidence_fingerprint(org_id, field_id, accounting_pathway, season_ids)
    checks = _apply_manual_overrides(checks, org_id, field_id, accounting_pathway, bundle_id,
                                      monitoring_period_start, monitoring_period_end, evidence_fingerprint)
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
