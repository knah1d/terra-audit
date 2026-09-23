from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FarmCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    contact_name: str = Field(default="", max_length=200)
    contact_phone: str = Field(default="", max_length=40)
    contact_email: str = Field(default="", max_length=200)
    consent_given: bool = False
    consent_reference: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=4000)


class FarmUpdate(FarmCreate):
    pass


class FarmOut(BaseModel):
    farm_id: str
    name: str
    contact_name: str
    contact_phone: str
    contact_email: str
    consent_given: bool
    consent_reference: str
    notes: str
    created_by: str | None
    created_at: datetime | None
