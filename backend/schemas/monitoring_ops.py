from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FieldSeasonPair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_id: str
    season_id: str


class BulkMonitoringRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_seasons: list[FieldSeasonPair] = Field(min_length=1)
    force_refresh: bool = False


class RetryFailedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = None


class IssueDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=2000)


class IssueResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)
