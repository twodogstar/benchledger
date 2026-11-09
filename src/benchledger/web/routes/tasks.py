"""The next-step checklist on the project page: add, tick, reorder, delete (M5).

Like the notebook: htmx requests get the #tasks fragment back, plain form posts a redirect.
"""

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session

from benchledger import timeutil
from benchledger.db.models import Project, Task
from benchledger.services import InvalidInput
from benchledger.services import tasks as task_service
from benchledger.web.deps import RecordId, SessionDep, form_data, redirect, templates
from benchledger.web.project_page import (
    is_htmx,
    notebook_context,
    project_or_404,
    tasks_context,
)

router = APIRouter(prefix="/projects/{slug}/tasks")


def _due_for_form(raw: str) -> str:
    """The typed due date to show back after an error.

    A valid date goes back as ISO, because a date field discards any other shape and would
    look empty. An invalid one goes back as typed (capped) for the text box to correct.
    """
    try:
        return timeutil.parse_date(raw).isoformat() if raw.strip() else ""
    except ValueError:
        return raw.strip()[:40]


def task_or_404(session: Session, project: Project, task_id: int) -> Task:
    task = task_service.get_task(session, project, task_id)
    if task is None or task.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _after_change(request: Request, session, project):
    if is_htmx(request):
        return templates.TemplateResponse(
            request, "projects/_tasks.html", tasks_context(session, project)
        )
    return redirect(f"/projects/{project.slug}#tasks")


@router.post("")
async def add_task(request: Request, session: SessionDep, slug: str):
    project = project_or_404(session, slug)
    data = await form_data(request, ["text", "due_on"])
    try:
        task_service.create_task(session, project, data)
    except InvalidInput as exc:
        session.rollback()
        values = {**data, "due_on": _due_for_form(data["due_on"])}
        context = tasks_context(session, project, values=values, errors=exc.errors)
        if is_htmx(request):
            return templates.TemplateResponse(request, "projects/_tasks.html", context)
        context.update(notebook_context(session, project), active="projects")
        return templates.TemplateResponse(request, "projects/detail.html", context, status_code=400)
    session.commit()
    return _after_change(request, session, project)


@router.post("/{task_id}/done")
async def set_done(request: Request, session: SessionDep, slug: str, task_id: RecordId):
    project = project_or_404(session, slug)
    task = task_or_404(session, project, task_id)
    data = await form_data(request, ["done"])
    if data["done"] not in ("1", ""):
        raise HTTPException(status_code=400, detail="done must be 1 (done) or empty (not done)")
    task_service.set_done(session, task, data["done"] == "1")
    session.commit()
    return _after_change(request, session, project)


@router.post("/{task_id}/move")
async def move_task(request: Request, session: SessionDep, slug: str, task_id: RecordId):
    project = project_or_404(session, slug)
    task = task_or_404(session, project, task_id)
    data = await form_data(request, ["direction"])
    try:
        task_service.move_task(session, task, data["direction"])
    except InvalidInput as exc:
        raise HTTPException(status_code=400, detail=exc.errors["direction"]) from exc
    session.commit()
    return _after_change(request, session, project)


@router.post("/{task_id}/delete")
def delete_task(request: Request, session: SessionDep, slug: str, task_id: RecordId):
    project = project_or_404(session, slug)
    task_service.delete_task(session, task_or_404(session, project, task_id))
    session.commit()
    return _after_change(request, session, project)
