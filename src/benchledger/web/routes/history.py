"""History view: every recorded change to one record, newest first (requirement M2)."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from benchledger.db.models import Area, Entry, EvidenceLabel, Fault, Project, Task
from benchledger.services.history import HISTORY_TABLES, history_for
from benchledger.web.deps import RecordId, SessionDep, templates

router = APIRouter(prefix="/history")

MODELS = {
    "projects": Project,
    "entries": Entry,
    "tasks": Task,
    "faults": Fault,
    "areas": Area,
    "evidence_labels": EvidenceLabel,
}
# Records that belong to a project: History highlights Projects in the sidebar.
PROJECT_TABLES = {"projects", "entries", "tasks", "faults"}
LIST_TABLES = {"areas", "evidence_labels"}


def _describe(table_name: str, record) -> tuple[str, str | None, str | None]:
    """(record label for the title, back-link URL, back-link text)."""
    if record is None:
        return "", None, None
    if table_name == "projects":
        return record.name, f"/projects/{record.slug}", "Back to project"
    if table_name == "entries":
        back = f"/projects/{record.project.slug}#entry-{record.id}"
        return record.title, back, f"Back to {record.project.name}"
    if table_name == "tasks":
        return (
            record.text,
            f"/projects/{record.project.slug}#tasks",
            f"Back to {record.project.name}",
        )
    if table_name == "faults":
        label = record.symptom if len(record.symptom) <= 80 else record.symptom[:79] + "…"
        back = f"/projects/{record.project.slug}#fault-{record.id}"
        return label, back, f"Back to {record.project.name}"
    if table_name in LIST_TABLES:
        return record.name, "/settings/lists", "Back to lists"
    return "", None, None


@router.get("/{table_name}/{row_id}", response_class=HTMLResponse)
def record_history(request: Request, session: SessionDep, table_name: str, row_id: RecordId):
    if table_name not in HISTORY_TABLES:
        raise HTTPException(status_code=404, detail="No history for that kind of record")
    record = session.get(MODELS[table_name], row_id)
    changes = history_for(session, table_name, row_id)
    if record is None and not changes:
        raise HTTPException(status_code=404, detail="Record not found")
    record_label, back_url, back_text = _describe(table_name, record)
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "active": "projects" if table_name in PROJECT_TABLES else "settings",
            "label": HISTORY_TABLES[table_name],
            "table_name": table_name,
            "record": record,
            "record_label": record_label,
            "back_url": back_url,
            "back_text": back_text,
            "changes": changes,
        },
    )
