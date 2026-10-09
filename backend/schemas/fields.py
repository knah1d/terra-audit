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


class DistrictResponse(BaseModel):
    # None when the boundary lies outside Bangladesh — the client then
    # falls back to manual entry.
    district: str | None


class LandUseResponse(BaseModel):
    # None when there isn't enough satellite data to decide (reason in
    # evidence["summary"]).
    land_use: str | None
    evidence: dict[str, Any]


class FieldCreate(BaseModel):
    field_id: str
    name: str
    # Ignored when the district can be detected from `feature`; only used
    # for boundaries outside Bangladesh.
    district: str = ""
    field_type: str
    feature: dict[str, Any]
    # Observed land use ("Field Type" in the UI) — distinct from field_type,
    # which is the methodology. Optional; whether it matches satellite
    # detection is decided server-side, never taken from the client.
    land_use: str | None = None


class FieldUpdate(BaseModel):
    name: str
    # Ignored when the district can be detected from the stored boundary.
    district: str = ""
    # Omitted = leave unchanged (backend/routers/fields.py checks
    # model_fields_set), so older clients can't clear it by accident.
    land_use: str | None = None


class FieldOut(BaseModel):
    field_id: str
    name: str
    district: str
    area_ha: float | None
    field_type: str
    created_at: datetime | None = None
    land_use: str | None = None
    land_use_source: str | None = None  # "detected" | "manual"


class FieldDetailOut(FieldOut):
    geojson_geometry: dict[str, Any]
    land_use_evidence: dict[str, Any] | None = None
    alm_cumulative_delta_co2_wp: float | None = None
