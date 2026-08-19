from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from backend.deps import get_current_user, require_admin, require_writer
from backend.schemas.fields import (
    AreaResponse, FieldCreate, FieldDetailOut, FieldOut, FieldUpdate,
    GeometryParseResponse, ParseContentRequest, ParseCoordinatesRequest,
)
from src.database import create_field, delete_field, get_field, list_fields, update_field_info
from src.geo_utils import (
    compute_area_ha, parse_coordinate_text, parse_geojson_upload, parse_kml_upload,
)

router = APIRouter(tags=["fields"])


@router.post("/fields/parse/geojson", response_model=GeometryParseResponse)
def parse_geojson(body: ParseContentRequest, user: dict = Depends(get_current_user)):
    feature, error = parse_geojson_upload(body.content)
    return GeometryParseResponse(feature=feature, error=error)


@router.post("/fields/parse/kml", response_model=GeometryParseResponse)
def parse_kml(body: ParseContentRequest, user: dict = Depends(get_current_user)):
    feature, error = parse_kml_upload(body.content)
    return GeometryParseResponse(feature=feature, error=error)


@router.post("/fields/parse/upload", response_model=GeometryParseResponse)
async def parse_upload(file: UploadFile, user: dict = Depends(get_current_user)):
    """Convenience endpoint mirroring app.py's single file_uploader
    (.geojson/.json/.kml) — dispatches on filename extension exactly like
    app.py:591-594 does, so the frontend can hand over the raw upload
    without deciding geojson-vs-kml itself."""
    content = (await file.read()).decode("utf-8")
    if (file.filename or "").lower().endswith(".kml"):
        feature, error = parse_kml_upload(content)
    else:
        feature, error = parse_geojson_upload(content)
    return GeometryParseResponse(feature=feature, error=error)


@router.post("/fields/parse/coordinates", response_model=GeometryParseResponse)
def parse_coordinates(body: ParseCoordinatesRequest, user: dict = Depends(get_current_user)):
    feature, error = parse_coordinate_text(body.text)
    return GeometryParseResponse(feature=feature, error=error)


@router.post("/geometry/area", response_model=AreaResponse)
def geometry_area(feature: dict, user: dict = Depends(get_current_user)):
    """compute_area_ha raises (no error-tuple convention) on malformed
    input — translated to a 422 here rather than letting an unhandled
    exception surface as a 500."""
    try:
        return AreaResponse(area_ha=compute_area_ha(feature))
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid geometry: {exc}")


@router.get("/fields", response_model=list[FieldOut])
def list_org_fields(user: dict = Depends(get_current_user)):
    return [FieldOut(**f) for f in list_fields(user["org_id"])]


@router.get("/fields/{field_id}", response_model=FieldDetailOut)
def get_org_field(field_id: str, user: dict = Depends(get_current_user)):
    field = get_field(user["org_id"], field_id)
    if field is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    return FieldDetailOut(**field)


@router.post("/fields", response_model=FieldDetailOut, status_code=status.HTTP_201_CREATED)
def register_field(body: FieldCreate, user: dict = Depends(require_writer)):
    org_id = user["org_id"]
    if get_field(org_id, body.field_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Field ID '{body.field_id}' already exists")
    try:
        area_ha = compute_area_ha(body.feature)
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid geometry: {exc}")
    create_field(org_id, body.field_id, body.name.strip(), body.district.strip(),
                 body.feature, area_ha, body.field_type)
    return FieldDetailOut(**get_field(org_id, body.field_id))


@router.patch("/fields/{field_id}", response_model=FieldDetailOut)
def edit_field(field_id: str, body: FieldUpdate, user: dict = Depends(require_writer)):
    org_id = user["org_id"]
    if get_field(org_id, field_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    update_field_info(org_id, field_id, body.name.strip(), body.district.strip())
    return FieldDetailOut(**get_field(org_id, field_id))


@router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_field(field_id: str, user: dict = Depends(require_admin)):
    """Admin-only, per app.py's own _can_delete() split from _can_write()
    — deletion is irreversible and cascades across 6 tables."""
    org_id = user["org_id"]
    if get_field(org_id, field_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    delete_field(org_id, field_id)
    return None
