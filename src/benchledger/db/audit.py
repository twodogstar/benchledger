"""Automatic change log (requirement M2: nothing changes without a trace).

A SQLAlchemy `after_flush` hook looks at every audited object the session just wrote and
adds change_log rows in the same transaction:

  insert  one row per field that has a value
  update  one row per field whose value actually changed (old and new)
  delete  one row for the record

Because it hooks the session itself, no service code has to remember to log anything.
The author comes from `session.info["author_id"]` (the owner until logins exist).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import event, insert, inspect
from sqlalchemy.orm import Session

from benchledger.db.models import OWNER_ID, Audited, ChangeLog
from benchledger.timeutil import as_utc

# Bookkeeping columns that change on every write and would only add noise.
SKIP_FIELDS = {"id", "created_at", "updated_at"}


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _change_rows(session: Session) -> list[dict]:
    author_id = session.info.get("author_id", OWNER_ID)
    rows: list[dict] = []

    def add(obj, action: str, field=None, old=None, new=None) -> None:
        rows.append(
            {
                "author_id": author_id,
                "action": action,
                "table_name": obj.__tablename__,
                "row_id": str(obj.id),
                "field": field,
                "old_value": _as_text(old),
                "new_value": _as_text(new),
            }
        )

    for obj in session.new:
        if not isinstance(obj, Audited):
            continue
        state = inspect(obj)
        for attr in state.mapper.column_attrs:
            if attr.key in SKIP_FIELDS:
                continue
            # Read from the instance dict, never getattr(): getattr could trigger a
            # database load in the middle of a flush.
            value = state.dict.get(attr.key)
            if value not in (None, ""):
                add(obj, "insert", attr.key, None, value)

    for obj in session.dirty:
        if not isinstance(obj, Audited):
            continue
        state = inspect(obj)
        for attr in state.mapper.column_attrs:
            if attr.key in SKIP_FIELDS:
                continue
            history = state.attrs[attr.key].history
            if not history.has_changes():
                continue
            old = history.deleted[0] if history.deleted else None
            new = history.added[0] if history.added else None
            # Compare as logged text: SQLite hands datetimes back naive (UTC), while new
            # values are aware, and a naive datetime never equals an aware one.
            if _as_text(old) != _as_text(new):
                add(obj, "update", attr.key, old, new)

    for obj in session.deleted:
        if isinstance(obj, Audited):
            add(obj, "delete")

    return rows


@event.listens_for(Session, "after_flush")
def _record_changes(session: Session, _flush_context) -> None:
    # In after_flush the new rows have their ids, and attribute history still shows
    # what changed. Writing with a plain INSERT keeps it inside the same transaction
    # without starting a second flush.
    rows = _change_rows(session)
    if rows:
        session.connection().execute(insert(ChangeLog.__table__), rows)
