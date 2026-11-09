"""Faults on the project page, with their own new/edit page (M4).

Faults are longer write-ups than notebook entries, so they use a full form page and
ordinary post/redirect/get, without htmx.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from benchledger.db.models import Fault, Project
from benchledger.services import InvalidInput
from benchledger.services import faults as fault_service
from benchledger.web.deps import RecordId, SessionDep, form_data, redirect, templates
from benchledger.web.project_page import label_choices, project_or_404

router = APIRouter(prefix="/projects/{slug}/faults")


def fault_or_404(session: Session, project: Project, fault_id: int) -> Fault:
    fault = fault_service.get_fault(session, project, fault_id)
    if fault is None:
        raise HTTPException(status_code=404, detail="Fault not found")
    return fault


def _form_page(request: Request, session, project, fault, values, errors, status_code=200):
    return templates.TemplateResponse(
        request,
        "faults/form.html",
        {
            "active": "projects",
            "project": project,
            "fault": fault,
            "values": values,
            "errors": errors,
            "statuses": fault_service.STATUSES,
            "labels": label_choices(session, fault.evidence_label_id if fault else None),
        },
        status_code=status_code,
    )


@router.get("/new", response_class=HTMLResponse)
def new_fault_form(request: Request, session: SessionDep, slug: str):
    project = project_or_404(session, slug)
    return _form_page(request, session, project, None, {"status": "Open"}, {})


@router.post("/new")
async def create_fault(request: Request, session: SessionDep, slug: str):
    project = project_or_404(session, slug)
    data = await form_data(request, fault_service.FORM_FIELDS)
    try:
        fault = fault_service.create_fault(session, project, data)
    except InvalidInput as exc:
        session.rollback()
        return _form_page(request, session, project, None, data, exc.errors, status_code=400)
    session.commit()
    return redirect(f"/projects/{project.slug}#fault-{fault.id}")


@router.get("/{fault_id}/edit", response_class=HTMLResponse)
def edit_fault_form(request: Request, session: SessionDep, slug: str, fault_id: RecordId):
    project = project_or_404(session, slug)
    fault = fault_or_404(session, project, fault_id)
    if fault.deleted_at is not None:
        return redirect(f"/projects/{project.slug}?faults=all#fault-{fault.id}")
    values = {field: getattr(fault, field) for field in fault_service.FORM_FIELDS}
    values["evidence_label_id"] = str(fault.evidence_label_id or "")
    return _form_page(request, session, project, fault, values, {})


@router.post("/{fault_id}/edit")
async def update_fault(request: Request, session: SessionDep, slug: str, fault_id: RecordId):
    project = project_or_404(session, slug)
    fault = fault_or_404(session, project, fault_id)
    data = await form_data(request, fault_service.FORM_FIELDS)
    try:
        fault_service.update_fault(session, fault, data)
    except InvalidInput as exc:
        session.rollback()
        return _form_page(request, session, project, fault, data, exc.errors, status_code=400)
    session.commit()
    return redirect(f"/projects/{project.slug}#fault-{fault.id}")


@router.post("/{fault_id}/delete")
def delete_fault(session: SessionDep, slug: str, fault_id: RecordId):
    project = project_or_404(session, slug)
    fault_service.delete_fault(session, fault_or_404(session, project, fault_id))
    session.commit()
    return redirect(f"/projects/{project.slug}#faults")


@router.post("/{fault_id}/restore")
def restore_fault(session: SessionDep, slug: str, fault_id: RecordId):
    project = project_or_404(session, slug)
    fault = fault_or_404(session, project, fault_id)
    fault_service.restore_fault(session, fault)
    session.commit()
    return redirect(f"/projects/{project.slug}#fault-{fault.id}")
