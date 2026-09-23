from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SeasonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    crops: list[str] = Field(min_length=1, max_length=20)
    start_date: date
    end_date: date
    notes: str = Field(default="", max_length=2000)

    @field_validator("crops")
    @classmethod
    def normalize_crops(cls, values):
        crops = list(dict.fromkeys(v.strip().lower() for v in values))
        if any(not v or len(v) > 80 for v in crops):
            raise ValueError("Each crop must contain 1–80 characters")
        return crops

    @model_validator(mode="after")
    def dates(self):
        if self.end_date < self.start_date:
            raise ValueError("Season end must be on or after its start")
        if (self.end_date - self.start_date).days > 730:
            raise ValueError("Use monitoring periods of at most two years, including perennial crops")
        return self


class ObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    observed_at: datetime
    kind: Literal["crop_identity", "water_level", "irrigation", "planting", "harvest", "residue_cover", "practice"]
    source: Literal["field_measurement", "expert_observation", "farmer_report", "document"]
    value: str = Field(min_length=1, max_length=500)
    numeric_value: float | None = None
    evidence_reference: str = Field(min_length=1, max_length=1000)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def measurement(self):
        if self.observed_at.tzinfo is None:
            raise ValueError("Observation time must include a timezone")
        if self.kind in {"water_level", "residue_cover"} and self.numeric_value is None:
            raise ValueError("A numeric measurement is required")
        if self.kind == "residue_cover" and not 0 <= self.numeric_value <= 100:
            raise ValueError("Residue cover must be between 0 and 100 percent")
        if self.kind == "crop_identity":
            self.value = self.value.lower()
        return self


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: Literal["accepted", "rejected"]
    reason: str = Field(min_length=1, max_length=2000)


class BenchmarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    split: Literal["field", "year", "district"] = "field"
    models: list[Literal["random_forest", "xgboost"]] = Field(
        default=["random_forest", "xgboost"], min_length=1, max_length=2
    )
