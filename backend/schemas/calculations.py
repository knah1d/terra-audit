from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EngineInputsRice(BaseModel):
    """Same engine parameters as CarbonCalcRequestRice (backend/schemas/
    carbon.py) MINUS area_ha — a Phase-2 calculation always uses the
    field's own registered area_ha (frozen into the snapshot), never a
    client-resupplied duplicate that could silently drift from it."""
    model_config = ConfigDict(extra="forbid")
    awd_events: int
    season_length_days: int
    q_n_kg_per_ha: float = 100.0
    preseason_category: str = "short"
    baseline_amendments: list[tuple[str, float]] | None = None
    project_amendments: list[tuple[str, float]] | None = None


class EngineInputsAlm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verification_years: float = 1.0
    non_permanence_risk_pct: float = 20.0


class CalculationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str | None = None
    accounting_pathway: Literal["vm0051_rice_awd", "vm0042_alm"]
    season_ids: list[str] = Field(min_length=1, max_length=50)
    monitoring_period_start: date
    monitoring_period_end: date
    engine_inputs: dict

    @model_validator(mode="after")
    def dates(self):
        if self.monitoring_period_end < self.monitoring_period_start:
            raise ValueError("Monitoring period end must be on or after its start")
        return self


class CalculationCommitRequest(CalculationContext):
    monitoring_run_ids: list[str] = Field(default_factory=list, max_length=50)
    attachment_ids: list[str] = Field(default_factory=list, max_length=100)
    supersedes_calculation_id: str | None = None


class ReadinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str | None = None
    accounting_pathway: Literal["vm0051_rice_awd", "vm0042_alm"]
    season_ids: list[str] = Field(min_length=1, max_length=50)
    monitoring_period_start: date
    monitoring_period_end: date


class DeterminationRequest(BaseModel):
    """Scoped to the exact project, methodology bundle (resolved
    server-side from project_id + accounting_pathway), reporting period,
    AND the evidence in scope at the moment of decision (season_ids,
    hashed server-side into an evidence fingerprint) — a determination
    outside this exact scope, or recorded against evidence that has
    since changed, is never honored (see
    src.calculations.latest_determinations). Restricted, at the write
    path, to requirements the methodology registry marks reviewable/
    expert_required — see src.calculations.record_determination."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    project_id: str | None = None
    accounting_pathway: Literal["vm0051_rice_awd", "vm0042_alm"]
    season_ids: list[str] = Field(min_length=1, max_length=50)
    requirement_id: str = Field(min_length=1, max_length=200)
    monitoring_period_start: date
    monitoring_period_end: date
    status: Literal["satisfied", "missing", "needs_review", "not_applicable", "unsupported"]
    reason: str = Field(min_length=1, max_length=2000)
