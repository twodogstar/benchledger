"""The dashboard: what's happening on the bench (M15, partly; design "Screens").

Active projects, recent notebook entries, open faults and next tasks across every
non-archived project. Recent runs and backup status join it in iterations 2 and 3.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import SQLAlchemyError

from benchledger.services import entries as entry_service
from benchledger.services import faults as fault_service
from benchledger.services import projects as project_service
from benchledger.services import tasks as task_service
from benchledger.web.deps import SessionDep, templates

router = APIRouter()

TILE_LIMIT = 8  # rows per tile


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: SessionDep):
    revision = request.app.state.schema_revision()
    context = {
        "active": "dashboard",
        "data_dir": request.app.state.settings.data_dir,
        "revision": revision,
        "active_projects": [],
        "more_projects": False,
        "recent_entries": [],
        "open_faults": [],
        "next_tasks": [],
        "overdue": set(),
    }
    # An unmigrated (or only partly migrated) database lacks tables: show the
    # "run db upgrade" hint instead of a 500.
    if revision is not None:
        try:
            # One extra row tells us whether to offer "All projects".
            active = project_service.list_projects(session, stage="Active", limit=TILE_LIMIT + 1)
            tasks = task_service.next_tasks(session, limit=TILE_LIMIT)
            context.update(
                active_projects=active[:TILE_LIMIT],
                more_projects=len(active) > TILE_LIMIT,
                recent_entries=entry_service.recent_entries(session, limit=TILE_LIMIT),
                open_faults=fault_service.open_faults(session, limit=TILE_LIMIT),
                next_tasks=tasks,
                overdue={t.id for t in tasks if task_service.is_overdue(t)},
            )
        except SQLAlchemyError:
            session.rollback()
            context["revision"] = None  # shows the upgrade hint
    return templates.TemplateResponse(request, "dashboard.html", context)
