"""Read the change log for one record (the History view)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchledger.db.models import ChangeLog

# Tables whose history can be shown, with a label for page titles.
HISTORY_TABLES = {
    "projects": "Project",
    "entries": "Entry",
    "areas": "Area",
    "evidence_labels": "Evidence label",
}


def history_for(session: Session, table_name: str, row_id: int | str) -> list[ChangeLog]:
    """Newest change first."""
    query = (
        select(ChangeLog)
        .where(ChangeLog.table_name == table_name, ChangeLog.row_id == str(row_id))
        .order_by(ChangeLog.id.desc())
    )
    return list(session.scalars(query))
