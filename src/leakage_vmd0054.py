"""VMD0054 v1.1 — Estimating Leakage from the Displacement of
Agricultural Activities. Source: methodologies/verra/vmd0054/
VMD0054-v1.1.pdf (sha256 9c45a369c5dfc2f9f779424dcc142e9bee442820cae
8e0367674c89686882824), registered in src.methodology_registry as
"vmd0054-v1.1". Equation numbers/section refs below are quoted from
that document (extracted via pdftotext -layout for verification).

This module implements Steps 1, 3, 4, 5 against src.production_records'
real per-commodity, multi-year data (Step 2, "leakage mitigation
activities outside the project area", is EXPLICITLY OPTIONAL per the
source text itself — §5.2 heading says "(Optional)" — and is not
implemented; LM_j,t is therefore always 0 in Eq. 6, which is the
methodology's own "no mitigation claimed" case, not an invented
substitute for unavailable mitigation data).

Applicability/branching (decided BEFORE any equation executes, per
this module's `plan_commodity` / `plan_leakage`):
  - A commodity with no historical_year production records at all
    cannot have Step 1 (Eq. 1) computed — blocked, not defaulted.
  - Step 3 (Eq. 9/10) requires a commodity-specific expected yield
    (Gj,t) and, in 'cross_commodity' accounting mode, MANDATORY Table 1
    defaults (no override permitted per §5.3); in 'leakage_only' mode a
    project may override IS/NL with justification, defaulting to
    Table 1 otherwise.
  - Steps 4-5 require project-wide, region-specific carbon-stock change
    parameters (ΔCbiomass, SOCREF, fLU, fMG, fIN — Eq. 11/12) this
    codebase does not have a registered regional source for. Where
    ALt > 0 and these are not supplied, LEAKAGE EMISSIONS CANNOT BE
    QUANTIFIED and the result says so explicitly — this is a genuine,
    disclosed missing-regional-data gap (distinct from "not
    implemented in software"), not a defaulted-to-zero leakage amount.
"""
# Table 1 (§5.3) — official default values for Increased Supply (ISj)
# and New Lands (NLj), quoted verbatim.
_TABLE1_LEAKAGE_ONLY = {
    "agricultural": {"is_pct": 75.0, "nl_pct": 40.0},
    "fuelwood": {"is_pct": 100.0, "nl_pct": 100.0},
}
_TABLE1_CROSS_COMMODITY = {
    # Cross-commodity mode uses the SAME 100/100 default for both a
    # displaced and an introduced commodity per Table 1's two
    # "Cross-commodity production default" columns.
    "displaced": {"is_pct": 100.0, "nl_pct": 100.0},
    "introduced": {"is_pct": 100.0, "nl_pct": 100.0},
}

# Appendix 1's documented, source-backed default annual growth rate —
# usable as-is (it is the methodology's OWN default, not invented here),
# but every use must record which source (this default, or a
# regional/FAOSTAT-derived value) actually governed the calculation.
DEFAULT_GROWTH_RATE_PCT = 2.5
DEFAULT_GROWTH_RATE_SOURCE = (
    "VMD0054 v1.1 Appendix 1 default (2.5%/year) — IFPRI/FAO-derived conservative default for rj "
    "where regional/national/FAOSTAT yield data is not supplied for this commodity."
)

ACCOUNTING_MODES = {"leakage_only", "cross_commodity"}
COMMODITY_TYPES = {"agricultural", "fuelwood"}


def plan_commodity(commodity: str, historical_records: list[dict], project_records: list[dict],
                   historical_years: float | None = None, monitoring_years: float | None = None) -> dict:
    """Sum harvests before annualization; missing observations are never zero."""
    records = historical_records + project_records
    if not historical_records or not project_records:
        return {"computable": False, "reason": f"{commodity}: explicit historical and project records required."}
    if any(r["production_status"] == "missing" for r in records):
        return {"computable": False, "reason": f"{commodity}: missing production evidence."}
    if any(r["production_status"] == "produced" and
           (r.get("production_quantity") is None or r["production_quantity"] < 0) for r in records):
        return {"computable": False, "reason": f"{commodity}: invalid production quantity."}
    units = {r["unit"].strip().lower() for r in records if r["production_status"] == "produced"}
    if len(units) > 1:
        return {"computable": False, "reason": f"{commodity}: normalize production units before calculating."}
    h = historical_years or len({r["period_label"] for r in historical_records})
    w = monitoring_years or len({r["period_label"] for r in project_records})
    introduced = all(r["production_status"] == "not_applicable" for r in historical_records)
    return {
        "computable": True, "reason": None, "is_new_cross_commodity": introduced,
        "historical_mean": sum(r.get("production_quantity") or 0 for r in historical_records) / h,
        "monitored_mean": sum(r.get("production_quantity") or 0 for r in project_records) / w,
        "H": h, "W": w, "unit": next(iter(units), None),
    }


def step1_change_in_production(plan: dict, growth_rate_pct: float, years_elapsed: float) -> dict:
    """Eqs. 1-3. `plan` is plan_commodity's output for a computable
    commodity. `plan["historical_mean"]` is 0.0 for a genuinely NEW
    cross-commodity introduction per Eq. 1's own note ("baseline
    production (BPj,t) is set to zero"), not a missing-data default."""
    bp_t = plan["historical_mean"] * (1 + growth_rate_pct / 100) ** years_elapsed
    mp_t = plan["monitored_mean"]
    cp_t = bp_t - mp_t
    return {"BP_t": bp_t, "MP_t": mp_t, "CP_t": cp_t}


def step3_land_impact(commodity_type: str, role: str, accounting_mode: str, cp_t: float,
                       yield_units_per_ha: float | None, yield_source: str | None,
                       is_override_pct: float | None, nl_override_pct: float | None,
                       override_justification: str | None) -> dict:
    """Eq. 9. `role` is 'displaced' (CP_t > 0) or 'introduced' (CP_t < 0,
    cross-commodity only). Blocks when Gj,t (yield) is missing — this is
    a per-commodity, regionally-specific REQUIRED input with no
    methodology default, unlike ISj/NLj."""
    if commodity_type not in COMMODITY_TYPES:
        raise ValueError(f"commodity_type must be one of {sorted(COMMODITY_TYPES)}")
    if accounting_mode not in ACCOUNTING_MODES:
        raise ValueError(f"accounting_mode must be one of {sorted(ACCOUNTING_MODES)}")
    if yield_units_per_ha is None or yield_units_per_ha <= 0 or not yield_source:
        return {
            "computable": False,
            "reason": "Expected yield (Gj,t, units of commodity per hectare) is required for Step 3 "
                      "(Eq. 9) and has no methodology default — VMD0054 §5.3 requires regionally "
                      "appropriate yield data specific to this commodity and project region. This is "
                      "missing PROJECT/REGIONAL data, not an unimplemented calculation.",
        }
    if accounting_mode == "cross_commodity" and (is_override_pct is not None or nl_override_pct is not None):
        return {"computable": False, "reason": "Cross-commodity accounting requires Table 1 defaults."}
    if commodity_type == "fuelwood" and (is_override_pct is not None or nl_override_pct is not None):
        return {"computable": False, "reason": "Fuelwood overrides are outside the supported scope."}
    if accounting_mode == "cross_commodity":
        defaults = _TABLE1_CROSS_COMMODITY[role]
        is_pct, nl_pct = defaults["is_pct"], defaults["nl_pct"]
        source = "VMD0054 v1.1 Table 1 (cross-commodity production default — mandatory, no override permitted)"
    else:
        defaults = _TABLE1_LEAKAGE_ONLY[commodity_type]
        if is_override_pct is not None or nl_override_pct is not None:
            if not override_justification:
                return {
                    "computable": False,
                    "reason": "An ISj/NLj override was supplied without a justification — VMD0054 §5.3 "
                               "requires evidence when a less-conservative-than-default value is used.",
                }
            is_pct = is_override_pct if is_override_pct is not None else defaults["is_pct"]
            nl_pct = nl_override_pct if nl_override_pct is not None else defaults["nl_pct"]
            source = f"Project-supplied override: {override_justification}"
        else:
            is_pct, nl_pct = defaults["is_pct"], defaults["nl_pct"]
            source = "VMD0054 v1.1 Table 1 (leakage-only default)"
    l_j_t = max(0.0, cp_t) if accounting_mode == "leakage_only" else cp_t  # Eq. 6 with LM_j,t = 0 (Step 2 not implemented — see module docstring)
    inl_j_t = (l_j_t * (is_pct / 100) * (nl_pct / 100)) / yield_units_per_ha
    return {
        "computable": True, "l_j_t": l_j_t, "is_pct": is_pct, "nl_pct": nl_pct,
        "is_nl_source": source, "yield_units_per_ha": yield_units_per_ha, "yield_source": yield_source,
        "INL_j_t": inl_j_t,
    }


def step3_total_area(commodity_land_impacts: list[dict]) -> float:
    """Eq. 10 — AL_t = max(sum(INL_j,t), 0)."""
    return max(sum(c["INL_j_t"] for c in commodity_land_impacts), 0.0)


def step4_carbon_stock_change(delta_cbiomass_t_c_ha: float | None, soc_ref_t_c_ha: float | None,
                               f_lu: float | None, f_mg: float | None, f_in: float | None,
                               factors_source: str | None) -> dict:
    """Eq. 11/12. Every parameter here is region/ecoregion-specific and
    has NO source registered in this codebase (no ecoregion/IPCC Tier-1
    SOC-factor-table dataset is ingested) — always blocks unless a
    caller supplies all five with a disclosed source. Reference for
    where to source them: IPCC 2019 Refinement Vol. 4 (Ch. 5/6 Tables
    for fLU/fMG/fIN and reference SOC stocks), Global Forest Watch (for
    the ecoregion/deforestation-rate justification in §5.4), and
    regional forest-inventory biomass studies for ΔCbiomass."""
    missing = [name for name, v in (
        ("delta_cbiomass_t_c_ha", delta_cbiomass_t_c_ha), ("soc_ref_t_c_ha", soc_ref_t_c_ha),
        ("f_lu", f_lu), ("f_mg", f_mg), ("f_in", f_in),
    ) if v is None]
    if missing or not factors_source:
        return {
            "computable": False,
            "reason": "Step 4 (Eq. 11/12) requires region-specific carbon-stock-change parameters this "
                      f"codebase has no registered source for: missing {missing or ['factors_source']}. "
                      "VMD0054 §5.4 requires an identified ecoregion, IPCC 2019 Refinement Vol. 4 Ch. 5/6 "
                      "SOC change factors, and a regional biomass-change estimate — supply these with "
                      "their source to compute Steps 4-5, or leakage emissions cannot be quantified.",
        }
    delta_soc = soc_ref_t_c_ha * (1 - (f_lu * f_mg * f_in))
    delta_cs = delta_cbiomass_t_c_ha + delta_soc
    return {"computable": True, "delta_soc_t_c_ha": delta_soc, "delta_cs_t_c_ha": delta_cs,
            "factors_source": factors_source}


def step5_leakage_emissions(al_t_ha: float, delta_cs_t_c_ha: float, elm_t_tco2e: float = 0.0) -> float:
    """Eq. 13 — LKt = (ALt * ΔCS * 44/12) + ELM,t. ELM,t (leakage
    mitigation emissions) is always 0.0 here since Step 2 is not
    implemented (see module docstring)."""
    return al_t_ha * delta_cs_t_c_ha * (44 / 12) + elm_t_tco2e


def compute_vmd0054_leakage(
    org_id: str, field_id: str, accounting_mode: str, years_elapsed: float,
    commodity_params: dict, new_land_carbon_stock_params: dict | None,
) -> dict:
    """End-to-end Steps 1/3/4/5 for one field.

    commodity_params: {commodity: {"commodity_type", "growth_rate_pct"
    (None -> DEFAULT_GROWTH_RATE_PCT), "growth_rate_source" (None ->
    DEFAULT_GROWTH_RATE_SOURCE), "yield_units_per_ha", "yield_source",
    "is_override_pct", "nl_override_pct", "override_justification"}}
    new_land_carbon_stock_params: {"delta_cbiomass_t_c_ha", "soc_ref_t_c_ha",
    "f_lu", "f_mg", "f_in", "factors_source"} or None.

    Returns a dict that ALWAYS reports per-commodity Step 1/3 results
    (even where the overall total is blocked at Step 4/5), so a caller
    can see exactly how far the calculation got and what specifically
    is missing — never conflating "this software doesn't implement X"
    with "this project hasn't supplied Y".
    """
    from src.production_records import production_summary
    return calculate_summary(production_summary(org_id, field_id), accounting_mode, years_elapsed,
                             commodity_params, new_land_carbon_stock_params)


def calculate_summary(summary: dict, accounting_mode: str, years_elapsed: float,
                      commodity_params: dict, new_land_carbon_stock_params: dict | None,
                      historical_years: float | None = None, monitoring_years: float | None = None) -> dict:
    """Pure calculation shared by exploratory and frozen-evidence workflows."""
    if accounting_mode not in ACCOUNTING_MODES:
        raise ValueError(f"accounting_mode must be one of {sorted(ACCOUNTING_MODES)}")

    commodities = {}
    land_impacts = []
    for commodity, periods in summary.items():
        params = commodity_params.get(commodity, {})
        plan = plan_commodity(commodity, periods["historical_year"], periods["project_period"], historical_years, monitoring_years)
        if plan["computable"] and plan.get("unit") and params.get("unit", "").strip().lower() != plan["unit"]:
            plan = {"computable": False, "reason": "Yield and production must use the same declared commodity unit."}
        if plan["computable"] and params.get("growth_rate_pct") is not None and not params.get("growth_rate_source"):
            plan = {"computable": False, "reason": "A supplied growth rate requires a source."}
        entry = {"plan": plan}
        if plan["computable"]:
            growth_rate_pct = params.get("growth_rate_pct")
            growth_rate_source = params.get("growth_rate_source")
            if growth_rate_pct is None:
                growth_rate_pct, growth_rate_source = DEFAULT_GROWTH_RATE_PCT, DEFAULT_GROWTH_RATE_SOURCE
            step1 = step1_change_in_production(plan, growth_rate_pct, years_elapsed)
            entry["step1"] = {**step1, "growth_rate_pct": growth_rate_pct, "growth_rate_source": growth_rate_source}
            role = "introduced" if step1["CP_t"] < 0 else "displaced"
            if accounting_mode == "cross_commodity" and (params.get("commodity_type") == "fuelwood" or
                    (role == "introduced" and not params.get("cross_commodity_evidence"))):
                entry["plan"] = {"computable": False, "reason": "Cross-commodity scope needs agricultural commodities and national production/increasing-production evidence (§5.3)."}
                commodities[commodity] = entry
                continue
            step3 = step3_land_impact(
                params.get("commodity_type", "agricultural"), role, accounting_mode, step1["CP_t"],
                params.get("yield_units_per_ha"), params.get("yield_source"),
                params.get("is_override_pct"), params.get("nl_override_pct"), params.get("override_justification"),
            )
            entry["step3"] = step3
            if step3["computable"]:
                land_impacts.append(step3)
        commodities[commodity] = entry

    al_t = step3_total_area(land_impacts) if land_impacts else 0.0
    blocked_commodities = [c for c, e in commodities.items()
                            if not e["plan"]["computable"] or (e.get("step3") and not e["step3"]["computable"])]

    result = {
        "commodities": commodities, "AL_t_ha": al_t, "accounting_mode": accounting_mode,
        "blocked_commodities": blocked_commodities, "leakage_emissions_tco2e": None,
        "leakage_block_reason": None,
    }
    if not summary or blocked_commodities:
        result["leakage_block_reason"] = "No complete production evidence." if not summary else "Incomplete commodities: " + ", ".join(blocked_commodities)
        return result
    if al_t <= 0:
        result["leakage_emissions_tco2e"] = 0.0
        result["leakage_block_reason"] = None
        return result
    step4 = step4_carbon_stock_change(
        (new_land_carbon_stock_params or {}).get("delta_cbiomass_t_c_ha"),
        (new_land_carbon_stock_params or {}).get("soc_ref_t_c_ha"),
        (new_land_carbon_stock_params or {}).get("f_lu"),
        (new_land_carbon_stock_params or {}).get("f_mg"),
        (new_land_carbon_stock_params or {}).get("f_in"),
        (new_land_carbon_stock_params or {}).get("factors_source"),
    )
    result["step4"] = step4
    if not step4["computable"]:
        result["leakage_block_reason"] = (
            f"AL_t = {al_t:.3f} ha of new land is implicated (Step 3), but leakage emissions cannot be "
            f"quantified: {step4['reason']}"
        )
        return result
    if step4["delta_cs_t_c_ha"] < 0:
        result["leakage_block_reason"] = "Negative regional carbon-stock loss requires methodological review; no negative deduction is applied."
        return result
    result["leakage_emissions_tco2e"] = step5_leakage_emissions(al_t, step4["delta_cs_t_c_ha"])
    return result


def _whole_years(start: str, end: str) -> int:
    """Supported scope: complete anniversary years, inclusive end date."""
    from datetime import date, timedelta
    first, stop = date.fromisoformat(start), date.fromisoformat(end) + timedelta(days=1)
    years = stop.year - first.year
    try:
        anniversary = first.replace(year=first.year + years)
    except ValueError:
        anniversary = first.replace(year=first.year + years, day=28)
    if years <= 0 or anniversary != stop:
        raise ValueError("Leakage currently supports complete anniversary-year periods; partial years are unsupported.")
    return years


def calculate_frozen_leakage(evidence: dict, bundle: dict | None, period: dict,
                             verification_years: float) -> dict:
    """VMD0054 v1.1 -> VM0042 Eq. 36; no database reads or guessed prior leakage.

    A separate scoped reviewer requirement confirms data coverage, project-wide
    accounting choices, regional evidence, and prior external verification values.
    """
    from datetime import date, timedelta
    import math
    result = {"module_version": "1.1", "integrated": True, "computable": False,
              "leakage_emissions_tco2e": None, "annual_displacement_leakage_tco2e": None,
              "AL_t_ha": 0.0, "blocked_commodities": [], "commodities": {},
              "leakage_block_reason": None,
              "source": "VMD0054 v1.1 §§5.1–5.5; VM0042 v2.2 Eq.36 and June 2026 corrected Eqs.39/42"}
    try:
        assessment = evidence.get("assessment")
        if not assessment:
            raise ValueError("Save a leakage assessment for this project, bundle, and exact reporting period.")
        p = assessment["payload"]
        result["assessment_id"] = assessment["assessment_id"]
        project_fields = {m["field_id"] for m in evidence.get("project_fields", [])}
        if project_fields != {assessment["field_id"]}:
            raise ValueError("VMD0054 §5 requires whole-project accounting. Multi-field/grouped-project aggregation and allocation are unsupported; an individual field result cannot substitute for the project total.")
        if not any(str(m["effective_start_date"])[:10] <= period["start"] and
                   (not m.get("effective_end_date") or str(m["effective_end_date"])[:10] >= period["end"])
                   for m in evidence["project_fields"]):
            raise ValueError("Field membership must cover the complete monitoring period.")
        docs = (bundle or {}).get("documents", [])
        doc_ids = {d.get("document_id") for d in docs}
        if p["module_version"] != "1.1" or not {"vmd0054-v1.1", "vm0042-v2.2", "vm0042-cc-2026-06-11"}.issubset(doc_ids):
            raise ValueError("The selected bundle does not support the implemented VMD0054 v1.1 adapter.")
        if p["bundle_id"] != bundle["bundle_id"] or p["monitoring_period_start"] != period["start"] or p["monitoring_period_end"] != period["end"]:
            raise ValueError("Saved leakage scope differs from this calculation.")
        if p["mitigation_choice"] != "none":
            raise ValueError("Step 2 mitigation activities are not implemented; a mitigation claim cannot be omitted.")
        result["step2"] = {"status": "not_applicable", "choice": "none", "LM": 0, "ELM": 0,
                           "source": "VMD0054 v1.1 §5.2 (optional)", "reason": p["mitigation_reason"]}
        h = _whole_years(p["historical_start"], p["historical_end"])
        w = _whole_years(period["start"], period["end"])
        t = _whole_years(p["project_start"], period["end"])
        if h < 3 or w != verification_years or t != p["years_elapsed"]:
            raise ValueError("History must cover at least three years; monitoring duration and years since project start must match the calculation.")
        if date.fromisoformat(p["historical_end"]) + timedelta(days=1) != date.fromisoformat(p["project_start"]):
            raise ValueError("Historical reference period must immediately precede project start.")
        if len(p["historical_period_labels"]) != h or len(p["project_period_labels"]) != w:
            raise ValueError("Select exactly one annual period label per historical/monitoring year; multiple harvest cycles share that year's label.")
        prior = p.get("prior_cumulative_leakage_tco2e")
        if period["start"] == p["project_start"]:
            if prior not in (None, 0) or p.get("prior_verification_end"):
                raise ValueError("A first verification has no prior leakage event.")
            prior = 0.0
        elif prior is None or not p.get("prior_verification_reference") or not p.get("prior_verification_end") or date.fromisoformat(p["prior_verification_end"]) + timedelta(days=1) != date.fromisoformat(period["start"]):
            raise ValueError("Supply cumulative leakage and the preceding verification reference/end date; no zero default is allowed for later periods.")
        summary = {}
        labels = {"historical_year": set(p["historical_period_labels"]), "project_period": set(p["project_period_labels"])}
        annual_windows = {}
        for kind, start, ordered_labels in (
            ("historical_year", p["historical_start"], p["historical_period_labels"]),
            ("project_period", period["start"], p["project_period_labels"]),
        ):
            first = date.fromisoformat(start)
            def anniversary(offset):
                try:
                    return first.replace(year=first.year + offset)
                except ValueError:
                    return first.replace(year=first.year + offset, day=28)
            for index, label in enumerate(ordered_labels):
                annual_windows[(kind, label)] = (anniversary(index).isoformat(), (anniversary(index + 1) - timedelta(days=1)).isoformat())
        selected = [r for r in evidence.get("production_records", []) if r["period_label"] in labels[r["period_type"]]]
        seen = set()
        for r in selected:
            key = (r["commodity"], r["period_type"], r["period_label"], r["crop_cycle_index"])
            if key in seen:
                raise ValueError("Duplicate commodity/cycle production record; resolve duplicates before calculation.")
            seen.add(key)
            if not r.get("evidence_ref"):
                raise ValueError(f"Production record {r['record_id']} needs an evidence reference.")
            if r.get("production_quantity") is not None and (not math.isfinite(r["production_quantity"]) or r["production_quantity"] < 0):
                raise ValueError("Production quantities must be finite and nonnegative.")
            if r["production_status"] in ("produced", "zero_production"):
                lo, hi = annual_windows[(r["period_type"], r["period_label"])]
                if not r.get("harvest_start_date") or not r.get("harvest_end_date") or not lo <= r["harvest_start_date"] <= r["harvest_end_date"] <= hi:
                    raise ValueError(f"Record {r['record_id']} requires harvest dates within its selected reference/monitoring period.")
            entry = summary.setdefault(r["commodity"], {"historical_year": [], "project_period": []})
            entry[r["period_type"]].append(r)
        for commodity, entry in summary.items():
            for kind, expected in labels.items():
                if {r["period_label"] for r in entry[kind]} != expected:
                    raise ValueError(f"{commodity}: record every selected {kind}, including explicit zero or not-applicable observations.")
        calculation = calculate_summary(summary, p["accounting_mode"], t, p["commodity_params"],
                                        p.get("new_land_carbon_stock_params"), h, w)
        result.update(calculation)
        if calculation["leakage_emissions_tco2e"] is None:
            return result
        if calculation["AL_t_ha"] > 0 and not p.get("regional_land_cover_evidence"):
            raise ValueError("Document the regional forest-conversion assumption or the §5.4 exception and all significant carbon pools.")
        cumulative = calculation["leakage_emissions_tco2e"]
        if not math.isfinite(cumulative) or cumulative < 0:
            raise ValueError("Leakage must be finite and nonnegative.")
        result.update(computable=True, cumulative_leakage_tco2e=cumulative,
                      prior_cumulative_leakage_tco2e=prior,
                      annual_displacement_leakage_tco2e=max(0, cumulative - prior) / w,
                      historical_years=h, monitoring_years=w, years_elapsed=t,
                      step4_status="satisfied" if calculation["AL_t_ha"] > 0 else "not_applicable",
                      prior_verification_reference=p.get("prior_verification_reference"),
                      selected_record_ids=[r["record_id"] for r in selected])
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        result.update(computable=False, leakage_emissions_tco2e=None,
                      annual_displacement_leakage_tco2e=None, leakage_block_reason=str(exc))
    return result
