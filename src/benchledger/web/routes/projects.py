"""Project pages: list, create, view, edit, archive (requirement M1)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from benchledger.services import InvalidInput
from benchledger.services import areas as area_service
from benchledger.services import projects as project_service
from benchledger.web.deps import SessionDep, form_data, redirect, templates
from benchledger.web.project_page import project_or_404, project_page_context

router = APIRouter(prefix="/projects")


def _form_page(request: Request, session, *, project, values, errors, status_code=200):
    current_area = project.area if project is not None else None
    choices = area_service.list_areas(session)
    if current_area is not None and current_area not in choices:
        choices.append(current_area)  # keep a retired area selectable on its own project
    return templates.TemplateResponse(
        request,
        "projects/form.html",
        {
            "active": "projects",
            "project": project,
            "values": values,
            "errors": errors,
            "areas": choices,
            "stages": project_service.STAGES,
            "priorities": project_service.PRIORITIES,
        },
        status_code=status_code,
    )


@router.get("", response_class=HTMLResponse)
def project_list(request: Request, session: SessionDep, stage: str = "", archived: bool = False):
    stage = stage if stage in project_service.STAGES else ""
    projects = project_service.list_projects(
        session, stage=stage or None, include_archived=archived
    )
    return templates.TemplateResponse(
        request,
        "projects/list.html",
        {
            "active": "projects",
            "projects": projects,
            "stages": project_service.STAGES,
            "stage": stage,
            "archived": archived,
        },
    )


@router.get("/new", response_class=HTMLResponse)
def new_project_form(request: Request, session: SessionDep):
    values = {"stage": "Idea", "priority": "Medium"}
    return _form_page(request, session, project=None, values=values, errors={})


@router.post("/new")
async def create_project(request: Request, session: SessionDep):
    data = await form_data(request, project_service.FORM_FIELDS)
    try:
        project = project_service.create_project(session, data)
    except InvalidInput as exc:
        session.rollback()
        return _form_page(
            request, session, project=None, values=data, errors=exc.errors, status_code=400
        )
    session.commit()
    return redirect(f"/projects/{project.slug}")


@router.get("/{slug}", response_class=HTMLResponse)
def project_detail(
    request: Request,
    session: SessionDep,
    slug: str,
    kind: str = "",
    deleted: bool = False,
    faults: str = "",
):
    project = project_or_404(session, slug)
    context = project_page_context(
        session, project, kind=kind, show_deleted=deleted, show_all_faults=faults == "all"
    )
    return templates.TemplateResponse(request, "projects/detail.html", context)


@router.get("/{slug}/edit", response_class=HTMLResponse)
def edit_project_form(request: Request, session: SessionDep, slug: str):
    project = project_or_404(session, slug)
    values = {field: getattr(project, field) for field in project_service.FORM_FIELDS}
    values["area_id"] = str(project.area_id or "")
    return _form_page(request, session, project=project, values=values, errors={})


@router.post("/{slug}/edit")
async def update_project(request: Request, session: SessionDep, slug: str):
    project = project_or_404(session, slug)
    data = await form_data(request, project_service.FORM_FIELDS)
    try:
        project_service.update_project(session, project, data)
    except InvalidInput as exc:
        session.rollback()
        return _form_page(
            request, session, project=project, values=data, errors=exc.errors, status_code=400
        )
    session.commit()
    return redirect(f"/projects/{project.slug}")


@router.post("/{slug}/archive")
def archive_project(session: SessionDep, slug: str):
    project = project_or_404(session, slug)
    project_service.archive_project(session, project)
    session.commit()
    return redirect(f"/projects/{project.slug}")


@router.post("/{slug}/restore")
def restore_project(session: SessionDep, slug: str):
    project = project_or_404(session, slug)
    project_service.restore_project(session, project)
    session.commit()
    return redirect(f"/projects/{project.slug}")
