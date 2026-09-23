from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    geography: str = Field(default="", max_length=2000)
    monitoring_start_date: date | None = None
    monitoring_end_date: date | None = None
    status: Literal["planning", "active", "completed", "archived"] = "planning"

    @model_validator(mode="after")
    def dates(self):
        if self.monitoring_start_date and self.monitoring_end_date and self.monitoring_end_date < self.monitoring_start_date:
            raise ValueError("Monitoring end date must be on or after its start date")
        return self


class ProjectUpdate(ProjectCreate):
    pass


class ProjectOut(BaseModel):
    project_id: str
    name: str
    description: str
    geography: str
    monitoring_start_date: date | None
    monitoring_end_date: date | None
    status: str
    created_by: str | None
    created_at: datetime | None


class ProjectMemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    project_role: Literal["lead", "contributor", "viewer"] = "contributor"
    reason: str | None = Field(default=None, max_length=2000)


class ProjectMemberOut(BaseModel):
    user_id: str
    email: str
    project_role: str
    added_at: datetime | None


class FieldMembershipAssign(BaseModel):
    """Explicit assignment of an already-registered field — never inferred
    from a crop declaration or anything else. effective_start_date
    defaults to today only for caller convenience; it is still an
    explicit field on every request."""
    model_config = ConfigDict(extra="forbid")
    field_id: str
    effective_start_date: date = Field(default_factory=date.today)


class FieldMembershipEnd(BaseModel):
    model_config = ConfigDict(extra="forbid")
    effective_end_date: date = Field(default_factory=date.today)
    reason: str = Field(min_length=1, max_length=2000)


class FieldMembershipOut(BaseModel):
    membership_id: str
    field_id: str
    effective_start_date: date
    effective_end_date: date | None
    assigned_by: str | None
    assigned_at: datetime | None
    removed_at: datetime | None
    removed_reason: str | None
