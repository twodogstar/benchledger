"""History view: every recorded change to one record, newest first (requirement M2)."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from benchledger.db.models import Area, Entry, EvidenceLabel, Project
from benchledger.services.history import HISTORY_TABLES, history_for
from benchledger.web.deps import RecordId, SessionDep, templates

router = APIRouter(prefix="/history")

MODELS = {
    "projects": Project,
    "entries": Entry,
    "areas": Area,
    "evidence_labels": EvidenceLabel,
}
# Records that belong to a project: History highlights Projects in the sidebar.
PROJECT_TABLES = {"projects", "entries"}


@router.get("/{table_name}/{row_id}", response_class=HTMLResponse)
def record_history(request: Request, session: SessionDep, table_name: str, row_id: RecordId):
    if table_name not in HISTORY_TABLES:
        raise HTTPException(status_code=404, detail="No history for that kind of record")
    record = session.get(MODELS[table_name], row_id)
    changes = history_for(session, table_name, row_id)
    if record is None and not changes:
        raise HTTPException(status_code=404, detail="Record not found")
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "active": "projects" if table_name in PROJECT_TABLES else "settings",
            "label": HISTORY_TABLES[table_name],
            "table_name": table_name,
            "record": record,
            "changes": changes,
        },
    )
