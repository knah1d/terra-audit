from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status

from backend.deps import (
    get_current_user, get_owned_field, get_spatial_engine, require_admin, require_writer,
)
from backend.schemas.fields import (
    AreaResponse, DistrictResponse, FieldCreate, FieldDetailOut, FieldOut, FieldUpdate,
    GeometryParseResponse, LandUseResponse, ParseContentRequest, ParseCoordinatesRequest,
)
from src.persistence.database import (
    create_field, delete_field, get_field, list_fields, update_field_info, update_field_land_use,
)
from src.field_types.registry import FIELD_TYPES
from src.signals.districts import detect_district
from src.signals.land_use import LAND_USE_VALUES, METHOD as LAND_USE_METHOD, detect_land_use
from src.signals.geometry import (
    compute_area_ha, parse_coordinate_text, parse_geojson_upload, parse_kml_upload,
)

router = APIRouter(tags=["fields"])

_field = get_owned_field()


def _resolve_district(geojson: dict, submitted: str) -> str:
    """The district detected from the boundary wins over whatever the client
    sent, so the read-only input can't be bypassed via the API. Manual entry
    is only accepted for boundaries outside Bangladesh."""
    try:
        detected = detect_district(geojson)
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid geometry: {exc}")
    district = detected or submitted.strip()
    if not district:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "District is required for boundaries outside Bangladesh")
    return district


def _resolve_land_use(request: Request, geojson: dict, submitted: str | None):
    """Returns (land_use, source, evidence) to store. The source is decided
    here by re-running detection (cached per geometry per day, so normally
    no second Earth Engine call) — "detected" only if the submitted value
    matches it, "manual" otherwise. The detection evidence is kept even on
    a manual override so the override stays auditable."""
    if submitted is None:
        return None, None, None
    if submitted not in LAND_USE_VALUES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown land_use '{submitted}'. Must be one of {list(LAND_USE_VALUES)}.",
        )
    engine = getattr(request.app.state, "spatial_engine", None)
    try:
        if engine is None:
            raise RuntimeError("Earth Engine is not initialized")
        detected, evidence = detect_land_use(engine, geojson)
    except Exception:
        detected = None
        evidence = {"method": LAND_USE_METHOD,
                    "summary": "Satellite detection was unavailable when this was recorded."}
    source = "detected" if detected == submitted else "manual"
    return submitted, source, evidence


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


@router.post("/geometry/district", response_model=DistrictResponse)
def geometry_district(feature: dict, user: dict = Depends(get_current_user)):
    try:
        return DistrictResponse(district=detect_district(feature))
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid geometry: {exc}")


@router.post("/geometry/land-use", response_model=LandUseResponse)
def geometry_land_use(feature: dict, user: dict = Depends(get_current_user),
                      engine=Depends(get_spatial_engine)):
    """Suggests the observed land use ("Field Type") from WorldCover and
    Sentinel-1 — see src/signals/land_use.py. 503 (via get_spatial_engine)
    when Earth Engine isn't configured; the form then falls back to manual."""
    try:
        land_use, evidence = detect_land_use(engine, feature)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Land-use detection failed: {exc}")
    return LandUseResponse(land_use=land_use, evidence=evidence)


@router.get("/fields", response_model=list[FieldOut])
def list_org_fields(user: dict = Depends(get_current_user)):
    from src.projects.workflow import current_projects
    projects = current_projects(user["org_id"])
    return [FieldOut(**f, current_project=projects.get(f["field_id"])) for f in list_fields(user["org_id"])]


@router.get("/fields/{field_id}", response_model=FieldDetailOut)
def get_org_field(field_id: str, user: dict = Depends(get_current_user),
                  field: dict = Depends(_field)):
    from src.projects.workflow import current_projects
    return FieldDetailOut(**field, current_project=current_projects(user["org_id"]).get(field_id))


@router.post("/fields", response_model=FieldDetailOut, status_code=status.HTTP_201_CREATED)
def register_field(body: FieldCreate, request: Request, user: dict = Depends(require_writer)):
    org_id = user["org_id"]
    # field_type was previously accepted unvalidated (a plain `str` on the
    # schema, with the FIELD_TYPES tuple sitting unused), so any string
    # persisted — into a column that is deliberately immutable after
    # registration, and that build_methodology() later KeyErrors on.
    # Validated here at request time rather than as a schema Literal, so
    # this stays decoupled from whether the registry is populated at
    # schema-definition/import time.
    if body.field_type not in FIELD_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown field_type '{body.field_type}'. Must be one of "
            f"{sorted(FIELD_TYPES)}.",
        )
    if get_field(org_id, body.field_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Field ID '{body.field_id}' already exists")
    try:
        area_ha = compute_area_ha(body.feature)
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid geometry: {exc}")
    district = _resolve_district(body.feature, body.district)
    land_use, land_use_source, land_use_evidence = _resolve_land_use(
        request, body.feature, body.land_use,
    )
    create_field(org_id, body.field_id, body.name.strip(), district,
                 body.feature, area_ha, body.field_type,
                 land_use, land_use_source, land_use_evidence)
    return FieldDetailOut(**get_field(org_id, body.field_id))


@router.patch("/fields/{field_id}", response_model=FieldDetailOut)
def edit_field(field_id: str, body: FieldUpdate, request: Request,
               user: dict = Depends(require_writer), field: dict = Depends(_field)):
    org_id = user["org_id"]
    district = _resolve_district(field["geojson_geometry"], body.district)
    update_field_info(org_id, field_id, body.name.strip(), district)
    if "land_use" in body.model_fields_set and body.land_use != field["land_use"]:
        update_field_land_use(org_id, field_id, *_resolve_land_use(
            request, field["geojson_geometry"], body.land_use,
        ))
    return FieldDetailOut(**get_field(org_id, field_id))


@router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_field(field_id: str, user: dict = Depends(require_admin),
                 field: dict = Depends(_field)):
    """Admin-only, per app.py's own _can_delete() split from _can_write()
    — deletion is irreversible and cascades across many tables.

    Refuses outright if this field has any review history (Phase 3) —
    a submitted, in-review, or internally-approved package must stay
    reproducible; there is no "force delete" escape hatch here."""
    org_id = user["org_id"]
    from src.projects.reviews import field_has_submissions
    if field_has_submissions(org_id, field_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This field has review submissions on record and cannot be deleted — "
            "its calculations and evidence must remain reproducible.",
        )
    delete_field(org_id, field_id)
    return None
