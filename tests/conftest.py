"""Complete synthetic evidence shared by accounting regression tests.

Zero leakage is derived from documented production records, never supplied
as a shortcut around the VMD0054 adapter.
"""
from copy import deepcopy

import pytest

from src.carbon.leakage_vmd0054 import calculate_frozen_leakage
from src.methodology.registry import BUNDLES


@pytest.fixture
def leakage_case():
    def build(*, years=1, area_ha=5.0, baseline_yield=4.0, project_yield=6.0,
              regional=None, field_id="ALM-FIXTURE", project_id="PROJECT-FIXTURE"):
        assert years == int(years)
        years = int(years)
        start, end = "2026-01-01", f"{2025 + years}-12-31"
        bundle_manifest = next(b for b in BUNDLES if b["bundle_id"] == "vm0042-2026-06")
        bundle = {"bundle_id": bundle_manifest["bundle_id"], "documents": [
            {"document_id": document_id, "role": role}
            for document_id, role in bundle_manifest["documents"]]}
        records = []
        for kind, annual_years, yield_t_ha in (
            ("historical_year", range(2023, 2026), baseline_yield),
            ("project_period", range(2026, 2026 + years), project_yield),
        ):
            for year in annual_years:
                records.append({
                    "record_id": f"{field_id}-{year}", "org_id": "testorg", "field_id": field_id,
                    "commodity": "wheat", "period_type": kind, "period_label": str(year),
                    "crop_cycle_index": 1, "production_status": "produced",
                    "production_quantity": yield_t_ha * area_ha, "unit": "t",
                    "harvested_area_ha": area_ha, "area_share_pct": 100.0,
                    "harvest_start_date": f"{year}-05-01", "harvest_end_date": f"{year}-05-31",
                    "evidence_ref": f"fixture:weighbridge-{year}", "notes": "Synthetic regression data",
                })
        payload = {
            "project_id": project_id, "bundle_id": bundle["bundle_id"], "module_version": "1.1",
            "monitoring_period_start": start, "monitoring_period_end": end,
            "historical_start": "2023-01-01", "historical_end": "2025-12-31",
            "project_start": start, "years_elapsed": years,
            "historical_period_labels": [str(y) for y in range(2023, 2026)],
            "project_period_labels": [str(y) for y in range(2026, 2026 + years)],
            "accounting_mode": "leakage_only", "mitigation_choice": "none",
            "mitigation_reason": "No off-site mitigation activities in this synthetic project.",
            "commodity_params": {"wheat": {
                "commodity_type": "agricultural", "unit": "t", "yield_units_per_ha": baseline_yield,
                "yield_source": "fixture:regional-wheat-yield-survey",
                "growth_rate_pct": 0.0, "growth_rate_source": "fixture:stable-regional-yield-series",
            }},
            "new_land_carbon_stock_params": deepcopy(regional),
            "regional_land_cover_evidence": "fixture:regional-carbon-pool-survey" if regional else None,
        }
        evidence = {"assessment": {"assessment_id": "ASSESSMENT-FIXTURE", "field_id": field_id,
                                    "payload": payload}, "production_records": records,
                    "project_fields": [{"field_id": field_id, "effective_start_date": start,
                                        "effective_end_date": None}]}
        period = {"start": start, "end": end}
        return {"evidence": evidence, "bundle": bundle, "period": period,
                "result": calculate_frozen_leakage(evidence, bundle, period, years)}
    return build


@pytest.fixture
def computable_leakage(leakage_case):
    def calculate(**kwargs):
        result = leakage_case(**kwargs)["result"]
        assert result["integrated"] and result["computable"], result["leakage_block_reason"]
        assert result["selected_record_ids"]
        return result
    return calculate
