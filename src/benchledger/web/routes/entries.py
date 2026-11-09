"""Notebook entries on the project page: quick-add, edit, delete, restore (M2).

Requests sent by htmx (header HX-Request) get the notebook fragment back so the page
updates in place. Plain form posts (no JavaScript) get a redirect, as everywhere else.
"""

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from benchledger import timeutil
from benchledger.services import InvalidInput
from benchledger.services import entries as entry_service
from benchledger.web.deps import RecordId, SessionDep, form_data, redirect, templates
from benchledger.web.project_page import (
    is_htmx,
    label_choices,
    notebook_context,
    project_or_404,
    project_page_context,
    valid_filter,
)

router = APIRouter(prefix="/projects/{slug}/entries")

# Hidden fields on the notebook's forms that say which view the user is on (kind filter,
# show deleted), so adding or deleting an entry doesn't reset it.
VIEW_FIELDS = ["view_kind", "view_deleted"]


def entry_or_404(session, project, entry_id: int):
    entry = entry_service.get_entry(session, project, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


def _notebook_response(request: Request, context: dict, status_code: int = 200):
    return templates.TemplateResponse(
        request, "projects/_notebook.html", context, status_code=status_code
    )


def _view(data: dict[str, str]) -> tuple[str, bool]:
    return valid_filter(data.get("view_kind", "")), data.get("view_deleted") == "1"


def _project_url(
    project, kind: str = "", show_deleted: bool = False, anchor: str = "notebook"
) -> str:
    params = {}
    if kind:
        params["kind"] = kind
    if show_deleted:
        params["deleted"] = "1"
    query = f"?{urlencode(params)}" if params else ""
    return f"/projects/{project.slug}{query}#{anchor}"


def _after_change(request: Request, session, project, view: dict[str, str]):
    """htmx: send back the refreshed notebook. Plain form: back to the project page.

    Either way the user stays on the view (kind filter, show deleted) they were on.
    """
    kind, show_deleted = _view(view)
    if is_htmx(request):
        return _notebook_response(
            request, notebook_context(session, project, kind=kind, show_deleted=show_deleted)
        )
    return redirect(_project_url(project, kind, show_deleted))


@router.post("")
async def create_entry(request: Request, session: SessionDep, slug: str):
    project = project_or_404(session, slug)
    data = await form_data(request, entry_service.FORM_FIELDS + VIEW_FIELDS)
    try:
        entry_service.create_entry(session, project, data)
    except InvalidInput as exc:
        session.rollback()
        kind, show_deleted = _view(data)
        if is_htmx(request):
            # htmx only swaps 2xx responses by default; the errors are in the fragment.
            context = notebook_context(
                session,
                project,
                kind=kind,
                show_deleted=show_deleted,
                values=data,
                errors=exc.errors,
            )
            return _notebook_response(request, context)
        context = project_page_context(
            session, project, kind=kind, show_deleted=show_deleted, values=data, errors=exc.errors
        )
        return templates.TemplateResponse(request, "projects/detail.html", context, status_code=400)
    session.commit()
    return _after_change(request, session, project, data)


def _form_page(request: Request, session, project, entry, values, errors, status_code=200):
    return templates.TemplateResponse(
        request,
        "entries/form.html",
        {
            "active": "projects",
            "project": project,
            "entry": entry,
            "values": values,
            "errors": errors,
            "kinds": entry_service.KINDS,
            "labels": label_choices(session, entry.evidence_label_id),
        },
        status_code=status_code,
    )


@router.get("/{entry_id}/edit", response_class=HTMLResponse)
def edit_entry_form(request: Request, session: SessionDep, slug: str, entry_id: RecordId):
    project = project_or_404(session, slug)
    entry = entry_or_404(session, project, entry_id)
    if entry.deleted_at is not None:
        # Don't offer a form that can't be saved; show it where it can be restored.
        return redirect(_project_url(project, show_deleted=True, anchor=f"entry-{entry.id}"))
    values = {
        "kind": entry.kind,
        "title": entry.title,
        "body": entry.body,
        "source": entry.source,
        "evidence_label_id": str(entry.evidence_label_id or ""),
        "occurred_at": timeutil.form_value(entry.occurred_at),
    }
    return _form_page(request, session, project, entry, values, {})


@router.post("/{entry_id}/edit")
async def update_entry(request: Request, session: SessionDep, slug: str, entry_id: RecordId):
    project = project_or_404(session, slug)
    entry = entry_or_404(session, project, entry_id)
    data = await form_data(request, entry_service.FORM_FIELDS)
    try:
        entry_service.update_entry(session, entry, data)
    except InvalidInput as exc:
        session.rollback()
        return _form_page(request, session, project, entry, data, exc.errors, status_code=400)
    session.commit()
    return redirect(f"/projects/{project.slug}#entry-{entry.id}")


@router.post("/{entry_id}/delete")
async def delete_entry(request: Request, session: SessionDep, slug: str, entry_id: RecordId):
    project = project_or_404(session, slug)
    view = await form_data(request, VIEW_FIELDS)
    entry_service.delete_entry(session, entry_or_404(session, project, entry_id))
    session.commit()
    return _after_change(request, session, project, view)


@router.post("/{entry_id}/restore")
async def restore_entry(request: Request, session: SessionDep, slug: str, entry_id: RecordId):
    project = project_or_404(session, slug)
    view = await form_data(request, VIEW_FIELDS)
    entry_service.restore_entry(session, entry_or_404(session, project, entry_id))
    session.commit()
    return _after_change(request, session, project, view)


@router.post("/{entry_id}/status")
async def set_status(request: Request, session: SessionDep, slug: str, entry_id: RecordId):
    """Change a hypothesis's or question's status from the timeline (M3)."""
    project = project_or_404(session, slug)
    entry = entry_or_404(session, project, entry_id)
    data = await form_data(request, ["status", *VIEW_FIELDS])
    try:
        entry_service.set_status(session, entry, data["status"])
    except InvalidInput as exc:
        session.rollback()
        # The picker only offers valid choices, so this is usually a stale page (the entry
        # was deleted or its kind changed in another tab); the page script shows a message.
        raise HTTPException(status_code=400, detail="; ".join(exc.errors.values())) from exc
    session.commit()
    return _after_change(request, session, project, data)
