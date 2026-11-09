"""What the project page shows, shared by the project, entry and task routes.

The project page is built from fragments (projects/_notebook.html, projects/_tasks.html)
that are also returned on their own to htmx. Their contexts live here, outside any route
module, so each route module can render the full page without importing the others.
"""

from fastapi import HTTPException, Request

from benchledger.db.models import EvidenceLabel
from benchledger.services import entries as entry_service
from benchledger.services import faults as fault_service
from benchledger.services import lists as list_service
from benchledger.services import projects as project_service
from benchledger.services import tasks as task_service


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def project_or_404(session, slug: str):
    project = project_service.get_project(session, slug)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def valid_filter(kind: str) -> str:
    """A kind filter from the URL or a form, or '' (show all) if it isn't one we know."""
    return kind if kind in entry_service.KINDS or kind == entry_service.OPEN_FILTER else ""


def label_choices(session, current_id: int | None = None) -> list:
    """Active evidence labels, plus a retired one already on the entry being edited."""
    labels = list_service.list_items(session, EvidenceLabel)
    if current_id is not None and all(label.id != current_id for label in labels):
        current = session.get(EvidenceLabel, current_id)
        if current is not None:
            labels.append(current)
    return labels


def notebook_context(
    session,
    project,
    *,
    kind: str = "",
    show_deleted: bool = False,
    values: dict | None = None,
    errors: dict | None = None,
) -> dict:
    """Everything the notebook fragment (projects/_notebook.html) needs."""
    kind = valid_filter(kind)
    return {
        "project": project,
        "entries": entry_service.timeline(
            session, project, kind=kind or None, include_deleted=show_deleted
        ),
        "kinds": entry_service.KINDS,
        "plurals": entry_service.PLURALS,
        "statuses": entry_service.STATUSES,
        "open_filter": entry_service.OPEN_FILTER,
        "kind": kind,
        "show_deleted": show_deleted,
        "labels": label_choices(session),
        "values": values or {"kind": "observation"},
        "errors": errors or {},
    }


def tasks_context(session, project, *, values=None, errors=None) -> dict:
    """Everything the checklist fragment (projects/_tasks.html) needs."""
    tasks = task_service.checklist(session, project)
    return {
        "project": project,
        "tasks": tasks,
        "overdue": {t.id for t in tasks if task_service.is_overdue(t)},
        "task_values": values or {},
        "task_errors": errors or {},
    }


def faults_context(session, project, *, show_all: bool = False) -> dict:
    """What the fault panel (projects/_faults.html) needs."""
    return {
        "faults": fault_service.list_faults(session, project, include_deleted=show_all),
        "show_all_faults": show_all,
    }


def project_page_context(session, project, *, show_all_faults: bool = False, **notebook) -> dict:
    """The full project page: notebook, checklist and faults. notebook: kind, show_deleted, …"""
    context = notebook_context(session, project, **notebook)
    context.update(tasks_context(session, project))
    context.update(faults_context(session, project, show_all=show_all_faults), active="projects")
    return context
