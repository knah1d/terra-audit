from typing import Any

from pydantic import BaseModel

# The two registry.py keys — kept as a plain tuple here rather than
# importing src.field_types.registry.FIELD_TYPES at schema-definition
# time, so this file has zero import-order dependency on the registry
# being populated yet (see backend/main.py's lifespan).
FIELD_TYPES = ("rice_awd", "cropland_alm_vm0042")


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
    created_at: str | None = None


class FieldDetailOut(FieldOut):
    geojson_geometry: dict[str, Any]
    alm_cumulative_delta_co2_wp: float | None = None
