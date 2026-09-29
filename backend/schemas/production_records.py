from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductionRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    commodity: str = Field(min_length=1, max_length=200)
    period_type: Literal["historical_year", "project_period"]
    period_label: str = Field(min_length=1, max_length=100)
    crop_cycle_index: int = Field(default=0, ge=0)
    harvest_start_date: date | None = None
    harvest_end_date: date | None = None
    harvested_area_ha: float | None = Field(default=None, gt=0)
    area_share_pct: float = Field(default=100.0, gt=0, le=100)
    production_status: Literal["produced", "zero_production", "missing", "not_applicable"]
    production_quantity: float | None = Field(default=None, ge=0)
    unit: str = Field(default="", max_length=50)
    evidence_ref: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def dates(self):
        if self.harvest_start_date and self.harvest_end_date and self.harvest_end_date < self.harvest_start_date:
            raise ValueError("harvest_end_date must not be before harvest_start_date")
        return self


class ProductionRecordsImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[ProductionRecordCreate] = Field(min_length=1, max_length=500)


class CommodityLeakageParams(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=50)
    cross_commodity_evidence: str = Field(default="", max_length=4000)
    commodity_type: Literal["agricultural", "fuelwood"] = "agricultural"
    growth_rate_pct: float | None = Field(default=None, ge=0)
    growth_rate_source: str | None = Field(default=None, max_length=1000)
    yield_units_per_ha: float | None = Field(default=None, gt=0)
    yield_source: str | None = Field(default=None, max_length=1000)
    is_override_pct: float | None = Field(default=None, gt=0, le=100)
    nl_override_pct: float | None = Field(default=None, gt=0, le=100)
    override_justification: str | None = Field(default=None, max_length=2000)


class NewLandCarbonStockParams(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    delta_cbiomass_t_c_ha: float = Field(ge=0)
    soc_ref_t_c_ha: float = Field(ge=0)
    f_lu: float = Field(gt=0)
    f_mg: float = Field(gt=0)
    f_in: float = Field(gt=0)
    factors_source: str = Field(min_length=1, max_length=2000)


class Vmd0054LeakageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    accounting_mode: Literal["leakage_only", "cross_commodity"]
    years_elapsed: float = Field(gt=0)
    commodity_params: dict[str, CommodityLeakageParams] = Field(default_factory=dict)
    new_land_carbon_stock_params: NewLandCarbonStockParams | None = None


class LeakageAssessmentSave(Vmd0054LeakageRequest):
    project_id: str = Field(min_length=1)
    bundle_id: str = Field(min_length=1)
    module_version: Literal["1.1"] = "1.1"
    monitoring_period_start: date
    monitoring_period_end: date
    project_start: date
    historical_start: date
    historical_end: date
    historical_period_labels: list[str] = Field(min_length=3)
    project_period_labels: list[str] = Field(min_length=1)
    mitigation_choice: Literal["none", "claimed"]
    mitigation_reason: str = Field(min_length=1, max_length=4000)
    scope_evidence: str = Field(min_length=1, max_length=4000)
    regional_land_cover_evidence: str = Field(default="", max_length=4000)
    prior_cumulative_leakage_tco2e: float | None = Field(default=None, ge=0)
    prior_verification_end: date | None = None
    prior_verification_reference: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def scope_dates(self):
        if not self.historical_start <= self.historical_end < self.project_start <= self.monitoring_period_start <= self.monitoring_period_end:
            raise ValueError("Historical, project-start, and monitoring dates must be chronologically ordered")
        for labels in (self.historical_period_labels, self.project_period_labels):
            if any(not label.strip() for label in labels) or len(set(labels)) != len(labels):
                raise ValueError("Period labels must be nonempty and unique")
        return self
