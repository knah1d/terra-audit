from datetime import datetime
from typing import Any

from pydantic import BaseModel

# NOTE: field_type validation deliberately does NOT live here. Declaring
# it as a Literal (or checking against a tuple copied from the registry)
# would either duplicate the registry or depend on it being populated at
# schema-definition time. backend/routers/fields.py validates against
# src.field_types.registry.FIELD_TYPES at request time instead, so the
# registry stays the single source of truth.


class ParseContentRequest(BaseModel):
    content: str


class ParseCoordinatesRequest(BaseModel):
    text: str


class GeometryParseResponse(BaseModel):
    feature: dict[str, Any] | None = None
    error: str | None = None


class AreaResponse(BaseModel):
    area_ha: float


class FieldCreate(BaseModel):
    field_id: str
    name: str
    district: str
    field_type: str
    feature: dict[str, Any]


class FieldUpdate(BaseModel):
    name: str
    district: str


class FieldOut(BaseModel):
    field_id: str
    name: str
    district: str
    area_ha: float | None
    field_type: str
    created_at: datetime | None = None


class FieldDetailOut(FieldOut):
    geojson_geometry: dict[str, Any]
    alm_cumulative_delta_co2_wp: float | None = None
