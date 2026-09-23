"""Farm/farmer records — minimal contact info plus consent/reference
fields, and explicit field <-> farm assignment (never inferred)."""
from fastapi import APIRouter, Depends, HTTPException, status

from backend.deps import get_current_user, require_writer
from backend.schemas.farms import FarmCreate, FarmOut, FarmUpdate
from backend.schemas.projects import FieldMembershipAssign, FieldMembershipEnd, FieldMembershipOut
from src.database import get_field
from src import projects as projects_db

router = APIRouter(tags=["farms"])


def _owned_farm(org_id: str, farm_id: str) -> dict:
    farm = projects_db.get_farm(org_id, farm_id)
    if farm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Farm not found")
    return farm


@router.get("/farms", response_model=list[FarmOut])
def list_farms(user=Depends(get_current_user)):
    return [FarmOut(**f) for f in projects_db.list_farms(user["org_id"])]


@router.post("/farms", response_model=FarmOut, status_code=status.HTTP_201_CREATED)
def create_farm(body: FarmCreate, user=Depends(require_writer)):
    farm_id = projects_db.create_farm(
        user["org_id"], body.name, body.contact_name, body.contact_phone, body.contact_email,
        body.consent_given, body.consent_reference, body.notes, user["user_id"],
    )
    return FarmOut(**projects_db.get_farm(user["org_id"], farm_id))


@router.get("/farms/{farm_id}", response_model=FarmOut)
def get_farm(farm_id: str, user=Depends(get_current_user)):
    return FarmOut(**_owned_farm(user["org_id"], farm_id))


@router.patch("/farms/{farm_id}", response_model=FarmOut)
def update_farm(farm_id: str, body: FarmUpdate, user=Depends(require_writer)):
    _owned_farm(user["org_id"], farm_id)
    projects_db.update_farm(
        user["org_id"], farm_id, body.name, body.contact_name, body.contact_phone,
        body.contact_email, body.consent_given, body.consent_reference, body.notes,
    )
    return FarmOut(**projects_db.get_farm(user["org_id"], farm_id))


@router.get("/farms/{farm_id}/fields", response_model=list[FieldMembershipOut])
def get_farm_fields(farm_id: str, user=Depends(get_current_user)):
    _owned_farm(user["org_id"], farm_id)
    return [FieldMembershipOut(**m) for m in projects_db.list_farm_fields(user["org_id"], farm_id)]


@router.post("/farms/{farm_id}/fields", response_model=FieldMembershipOut, status_code=status.HTTP_201_CREATED)
def assign_field(farm_id: str, body: FieldMembershipAssign, user=Depends(require_writer)):
    _owned_farm(user["org_id"], farm_id)
    if get_field(user["org_id"], body.field_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    membership_id = projects_db.assign_field_to_farm(
        user["org_id"], farm_id, body.field_id, body.effective_start_date.isoformat(), user["user_id"],
    )
    matches = [m for m in projects_db.list_farm_fields(user["org_id"], farm_id) if m["membership_id"] == membership_id]
    return FieldMembershipOut(**matches[0])


@router.post("/farms/{farm_id}/fields/{membership_id}/end", response_model=FieldMembershipOut)
def end_field_membership(farm_id: str, membership_id: str, body: FieldMembershipEnd, user=Depends(require_writer)):
    _owned_farm(user["org_id"], farm_id)
    ok = projects_db.end_farm_field_membership(
        user["org_id"], membership_id, body.effective_end_date.isoformat(), body.reason,
    )
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active field membership not found")
    matches = [m for m in projects_db.list_farm_fields(user["org_id"], farm_id) if m["membership_id"] == membership_id]
    return FieldMembershipOut(**matches[0])


@router.get("/fields/{field_id}/farms", response_model=list[FieldMembershipOut])
def get_farms_for_field(field_id: str, user=Depends(get_current_user)):
    if get_field(user["org_id"], field_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    return [FieldMembershipOut(**m) for m in projects_db.list_farms_for_field(user["org_id"], field_id)]
