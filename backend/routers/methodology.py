"""Methodology registry, project applicability, quantification units,
and guided enrollment — Phase 1/2 of docs/RESEARCH_IMPLEMENTATION_PLAN_
2026-09-23.md.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from backend.access import require_project_lead
from backend.deps import get_current_user, get_owned_field, require_admin, require_writer
from backend.schemas.methodology import ProjectApplicabilityRequest, QuantificationUnitCreate
from src import methodology_registry as registry
from src import projects as projects_db
from src import quantification
from src import readiness as readiness_engine

router = APIRouter(tags=["methodology"])
_field = get_owned_field()


@router.get("/methodology/documents")
def list_documents(user=Depends(get_current_user)):
    return registry.list_documents()


@router.get("/methodology/bundles")
def list_bundles(accounting_pathway: str | None = None, user=Depends(get_current_user)):
    return registry.list_bundles(accounting_pathway)


@router.get("/methodology/bundles/{bundle_id}")
def get_bundle(bundle_id: str, user=Depends(get_current_user)):
    bundle = registry.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Methodology bundle not found")
    return bundle


@router.get("/methodology/bundles/{bundle_id}/requirements")
def get_requirements(bundle_id: str, user=Depends(get_current_user)):
    if registry.get_bundle(bundle_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Methodology bundle not found")
    return registry.list_requirements(bundle_id)


@router.get("/projects/{project_id}/methodology-applicability")
def get_project_applicability(project_id: str, accounting_pathway: str, user=Depends(get_current_user)):
    if projects_db.get_project(user["org_id"], project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    explicit = registry.get_project_applicability(user["org_id"], project_id, accounting_pathway)
    resolved = registry.resolve_bundle_for_project(user["org_id"], project_id, accounting_pathway)
    return {"explicit_decision": explicit, "resolved_bundle": resolved}


@router.post("/projects/{project_id}/methodology-applicability", status_code=status.HTTP_201_CREATED)
def set_project_applicability(project_id: str, body: ProjectApplicabilityRequest, user=Depends(require_writer)):
    """Project-lead/admin only — pins a project to a specific methodology
    bundle (e.g. VM0051 v1.0 transition eligibility) rather than always
    "whatever is current." See src.methodology_registry's BUNDLES."""
    if projects_db.get_project(user["org_id"], project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    require_project_lead(user["org_id"], project_id, user)
    try:
        return registry.set_project_applicability(
            user["org_id"], project_id, body.accounting_pathway, body.bundle_id, user["user_id"],
            body.reason, body.applicable_from, body.applicable_until,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/fields/{field_id}/quantification-units")
def list_quantification_units(field_id: str, user=Depends(get_current_user), field=Depends(_field)):
    return quantification.list_units(user["org_id"], field_id)


@router.post("/fields/{field_id}/quantification-units", status_code=status.HTTP_201_CREATED)
def create_quantification_unit(field_id: str, body: QuantificationUnitCreate,
                                user=Depends(require_writer), field=Depends(_field)):
    try:
        unit_id = quantification.create_unit(
            user["org_id"], field_id, body.name, body.area_ha, body.eligibility_status,
            body.exclusion_reason, user["user_id"],
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return next(u for u in quantification.list_units(user["org_id"], field_id) if u["unit_id"] == unit_id)


@router.get("/projects/{project_id}/eligible-area")
def get_project_eligible_area(project_id: str, user=Depends(get_current_user)):
    if projects_db.get_project(user["org_id"], project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return quantification.project_eligible_area(user["org_id"], project_id)


@router.get("/fields/{field_id}/guided-enrollment")
def get_guided_enrollment(field_id: str, user=Depends(get_current_user), field=Depends(_field)):
    return readiness_engine.guided_enrollment(user["org_id"], field)


# --------------------------------------------------------------------------
# Methodology knowledge library (Phase 4A) — see src/methodology_library.py
# --------------------------------------------------------------------------

@router.post("/methodology/library/ingest", status_code=status.HTTP_202_ACCEPTED)
def ingest_library(user=Depends(require_admin)):
    """Queues (re)indexing of every registered local methodology PDF.
    Idempotent per document sha256 — unchanged PDFs are skipped."""
    from src.jobs import create_job
    return {"job_id": create_job(user["org_id"], "methodology_ingest", {"requested_by": user["user_id"]})}


@router.get("/methodology/library/status")
def library_status(user=Depends(get_current_user)):
    from src import methodology_library
    return methodology_library.index_status()


@router.get("/methodology/library/ingest/jobs/{job_id}")
def library_ingest_job(job_id: str, user=Depends(require_admin)):
    from src.jobs import get_job_row
    job = get_job_row(user["org_id"], job_id)
    if job is None or job["job_type"] != "methodology_ingest":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Methodology ingestion job not found")
    return {"job_id": job_id, "status": job["status"], "error": job.get("error")}


@router.get("/methodology/library/search")
def search_library(q: str, bundle_id: str, limit: int = 8, user=Depends(get_current_user)):
    """Full-text search limited to one bundle's documents."""
    from src import methodology_library
    bundle = registry.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Methodology bundle not found")
    return methodology_library.search(q, [d["document_id"] for d in bundle["documents"]],
                                      min(max(limit, 1), 25), org_id=user["org_id"])


@router.get("/methodology/corrections")
def get_corrections(document_id: str | None = None, user=Depends(get_current_user)):
    """Public reference mappings with this organization's confirmation status."""
    from src import methodology_library
    if document_id and not any(d["document_id"] == document_id for d in registry.list_documents()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Methodology document not found")
    return methodology_library.list_corrections(document_id, org_id=user["org_id"])


@router.post("/methodology/corrections/{correction_id}/confirm")
def confirm_correction(correction_id: str, user=Depends(require_admin)):
    """Confirm the reference mapping for this org; never a readiness decision."""
    from src import methodology_library
    try:
        return methodology_library.confirm_correction(correction_id, user["org_id"], user["user_id"])
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/methodology/documents/{document_id}/file")
def get_document_file(document_id: str, user=Depends(get_current_user)):
    """Serves a registered methodology PDF so a citation can open it
    (the client appends #page=N)."""
    from fastapi.responses import FileResponse
    doc = next((d for d in registry.list_documents() if d["document_id"] == document_id), None)
    path = registry.METHODOLOGIES_DIR / doc["file_path"] if doc and doc.get("file_path") else None
    if path is None or not path.resolve().is_relative_to(registry.METHODOLOGIES_DIR.resolve()) or not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Methodology document file not available")
    return FileResponse(path, media_type="application/pdf", filename=path.name)
