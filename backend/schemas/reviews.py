from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SubmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calculation_id: str
    previous_submission_id: str | None = None


class AssignReviewerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer_id: str | None = None
    reason: str = Field(min_length=1, max_length=2000)


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    if_version: int
    to_status: Literal["in_review", "changes_requested", "internally_approved", "rejected", "withdrawn"]
    reason: str | None = Field(default=None, max_length=4000)


class FindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    severity: Literal["blocking", "major", "minor", "info"]
    description: str = Field(min_length=1, max_length=4000)
    requested_action: str = Field(default="", max_length=2000)
    requirement_id: str | None = Field(default=None, max_length=200)
    input_ref: str | None = Field(default=None, max_length=200)
    evidence_ref: str | None = Field(default=None, max_length=200)


class FindingClose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=4000)
    is_proposed_resolution: bool = False
