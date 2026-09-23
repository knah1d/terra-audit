from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectApplicabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    accounting_pathway: Literal["vm0051_rice_awd", "vm0042_alm"]
    bundle_id: str
    reason: str = Field(min_length=1, max_length=2000)
    applicable_from: str | None = None
    applicable_until: str | None = None


class QuantificationUnitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    area_ha: float = Field(gt=0)
    eligibility_status: Literal["eligible", "excluded", "needs_review"] = "needs_review"
    exclusion_reason: str | None = Field(default=None, max_length=2000)
