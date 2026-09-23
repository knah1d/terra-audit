from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CropSequenceEntry(BaseModel):
    """One crop's own sub-period within a `rotation`-type season — e.g.
    Boro rice Jan-Apr followed by jute May-Aug within a single annual
    season record."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    crop: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def dates(self):
        if self.end_date < self.start_date:
            raise ValueError("A crop-sequence entry's end must be on or after its start")
        return self


class SeasonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    crops: list[str] = Field(min_length=0, max_length=20, default_factory=list)
    start_date: date
    end_date: date
    notes: str = Field(default="", max_length=2000)
    # Additive multi-crop evidence fields (docs/RESEARCH_IMPLEMENTATION_
    # PLAN_2026-09-23.md Phase 2) — all optional with backward-compatible
    # defaults so an existing pre-Phase-2 SeasonCreate payload (or a
    # historical row read back without these keys) keeps working exactly
    # as before. `season_type='single_crop'` is still the ordinary case.
    season_type: Literal["single_crop", "rotation", "intercrop", "cover_crop", "fallow"] = "single_crop"
    is_historical: bool = Field(
        default=False,
        description="Marks this as a pre-project historical activity record (baseline evidence), not a "
                    "monitored project-period season.",
    )
    crop_sequence: list[CropSequenceEntry] = Field(default_factory=list, max_length=20)
    intercrop_arrangement: str = Field(default="", max_length=200)
    fallow_reason: str = Field(default="", max_length=500)

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
        if self.season_type == "fallow":
            if self.crops:
                raise ValueError("A fallow season records no crop — leave 'crops' empty")
        elif not self.crops:
            raise ValueError("At least one crop is required unless season_type is 'fallow'")
        if self.season_type == "rotation" and not self.crop_sequence:
            raise ValueError("A rotation season requires at least one crop_sequence entry")
        for entry in self.crop_sequence:
            if entry.start_date < self.start_date or entry.end_date > self.end_date:
                raise ValueError("Each crop_sequence entry must fall within the season's own start/end dates")
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


class SeasonCorrection(SeasonCreate):
    """Same fields as SeasonCreate plus a mandatory reason — creates a new
    *version* of an existing season rather than a new season. The season's
    id/season_id never changes, so observations/reviews/runs recorded
    against earlier versions keep their original season context."""
    reason: str = Field(min_length=1, max_length=2000)


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: Literal["accepted", "rejected"]
    reason: str = Field(min_length=1, max_length=2000)


class PracticeEventCreate(BaseModel):
    """A dated, structured operational practice event — distinct from
    ObservationCreate: an observation is *evidence* about the field
    (farmer report / measurement / expert / document, independently
    reviewed); a practice event is the org's own operational record of
    what was done and when, with quantities/units as typed fields
    (mirrors src.database.ALM_PRACTICE_COLUMNS's unit-in-name convention)
    rather than one free-text `value` string."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    kind: Literal["planting", "harvest", "irrigation", "fertilizer_application",
                  "tillage", "residue_management", "cover_cropping"]
    event_date: date
    source: Literal["farmer_declared", "field_team_recorded"] = "field_team_recorded"
    evidence_reference: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=2000)

    crop: str | None = Field(default=None, max_length=80)
    seeding_rate_kg_ha: float | None = Field(default=None, ge=0)
    yield_t_ha: float | None = Field(default=None, ge=0)
    # Generalization of yield_t_ha for a commodity whose customary unit
    # isn't t/ha (e.g. bunches, bags, per-tree counts) — yield_t_ha is
    # kept as-is for backward compatibility with existing callers/rows
    # that already rely on it; a new harvest record may use EITHER or
    # both. Neither is inferred from the other.
    yield_quantity: float | None = Field(default=None, ge=0)
    yield_unit: str | None = Field(default=None, max_length=40)

    irrigation_method: Literal["flood", "awd", "drip", "sprinkler", "rainfed"] | None = None
    water_applied_mm: float | None = Field(default=None, ge=0)

    fertilizer_product: str | None = Field(default=None, max_length=120)
    n_kg_ha: float | None = Field(default=None, ge=0)
    p_kg_ha: float | None = Field(default=None, ge=0)
    k_kg_ha: float | None = Field(default=None, ge=0)

    tillage_method: Literal["conventional", "reduced", "no_till"] | None = None
    tillage_depth_cm: float | None = Field(default=None, ge=0)

    residue_action: Literal["removed", "burned", "incorporated", "retained"] | None = None
    residue_percent: float | None = Field(default=None, ge=0, le=100)

    cover_crop_species: str | None = Field(default=None, max_length=80)
    cover_crop_coverage_percent: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def required_fields_for_kind(self):
        required = {
            "planting": ["crop"],
            "harvest": ["crop"],
            "irrigation": ["irrigation_method"],
            "fertilizer_application": ["fertilizer_product"],
            "tillage": ["tillage_method"],
            "residue_management": ["residue_action"],
            "cover_cropping": ["cover_crop_species"],
        }[self.kind]
        missing = [f for f in required if getattr(self, f) is None]
        if missing:
            raise ValueError(f"'{self.kind}' events require: {', '.join(missing)}")
        if (self.yield_quantity is None) != (self.yield_unit is None):
            raise ValueError("yield_quantity and yield_unit must be supplied together")
        return self


class BenchmarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    split: Literal["field", "year", "district"] = "field"
    models: list[Literal["random_forest", "xgboost"]] = Field(
        default=["random_forest", "xgboost"], min_length=1, max_length=2
    )
