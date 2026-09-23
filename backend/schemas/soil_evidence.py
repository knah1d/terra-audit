from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SamplingPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    measurement_method: Literal["dry_combustion", "wet_oxidation", "loss_on_ignition", "other"]
    remeasurement_interval_years: float | None = Field(default=None, gt=0)


class StratumCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    area_ha: float | None = Field(default=None, gt=0)


class SampleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stratum_id: str | None = None
    site_type: Literal["project", "control"]
    timepoint: Literal["t_start", "t_final"]
    sample_date: date
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    depth_top_cm: float = Field(ge=0)
    depth_bottom_cm: float = Field(gt=0)
    bulk_density_g_cm3: float | None = Field(default=None, gt=0)
    soc_percent: float | None = Field(default=None, ge=0, le=100)
    soc_value_tco2e_ha: float | None = None
    lab_name: str = Field(default="", max_length=200)
    lab_method: str = Field(default="", max_length=200)
    chain_of_custody_ref: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def depths(self):
        if self.depth_bottom_cm <= self.depth_top_cm:
            raise ValueError("depth_bottom_cm must be greater than depth_top_cm")
        return self
