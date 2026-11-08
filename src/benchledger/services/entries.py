"""Notebook entries (requirements M2, M3).

Entries are add-only in spirit: an edit changes the row, but the change log keeps every old
value, so what was believed on a given date can always be recovered. Deleting only sets
`deleted_at`; restoring clears it.
"""

from __future__ import annotations

from datetime import datetime, tzinfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchledger import timeutil
from benchledger.db.models import ENTRY_KINDS, Entry, EvidenceLabel, Project
from benchledger.services import InvalidInput, parse_id

KINDS = list(ENTRY_KINDS)
HYPOTHESIS_STATUSES = ["Untested", "Testing", "Supported", "Rejected"]
QUESTION_STATUSES = ["Open", "Answered"]
# Kinds that carry a status (M3), with the status a new entry starts at.
STATUSES = {"hypothesis": HYPOTHESIS_STATUSES, "question": QUESTION_STATUSES}
DEFAULT_STATUS = {"hypothesis": "Untested", "question": "Open"}

FORM_FIELDS = ["kind", "title", "body", "evidence_label_id", "source", "occurred_at"]
MAX_TITLE = 200
MAX_SOURCE = 300
MAX_BODY = 100_000  # generous; it's also copied into the change log on every edit


def timeline(
    session: Session,
    project: Project,
    kind: str | None = None,
    include_deleted: bool = False,
) -> list[Entry]:
    """The project's entries, newest first by when they happened."""
    query = (
        select(Entry)
        .where(Entry.project_id == project.id)
        .order_by(Entry.occurred_at.desc(), Entry.id.desc())
    )
    if kind:
        query = query.where(Entry.kind == kind)
    if not include_deleted:
        query = query.where(Entry.deleted_at.is_(None))
    return list(session.scalars(query))


def get_entry(session: Session, project: Project, entry_id: int) -> Entry | None:
    """An entry of this project (deleted ones included), or None."""
    entry = session.get(Entry, entry_id)
    if entry is None or entry.project_id != project.id:
        return None
    return entry


def _validate(
    session: Session,
    data: dict[str, str],
    current: Entry | None,
    tz: tzinfo | None,
) -> dict:
    """Check form data and return clean values. Raises InvalidInput with every problem."""
    errors: dict[str, str] = {}
    clean: dict = {}

    kind = (data.get("kind") or "").strip()
    if kind not in KINDS:
        errors["kind"] = "Pick a kind from the list."
    clean["kind"] = kind

    title = " ".join((data.get("title") or "").split())
    if not title:
        errors["title"] = "Title is required."
    elif len(title) > MAX_TITLE:
        errors["title"] = f"Keep it under {MAX_TITLE} characters."
    clean["title"] = title

    # Keep the user's line breaks (it's Markdown); normalise Windows line endings and trim.
    body = (data.get("body") or "").replace("\r\n", "\n").strip()
    if len(body) > MAX_BODY:
        errors["body"] = f"Keep it under {MAX_BODY:,} characters."
    clean["body"] = body

    source = " ".join((data.get("source") or "").split())
    if len(source) > MAX_SOURCE:
        errors["source"] = f"Keep it under {MAX_SOURCE} characters."
    clean["source"] = source

    clean["evidence_label_id"] = None
    raw_label = (data.get("evidence_label_id") or "").strip()
    if raw_label:
        label_id = parse_id(raw_label)
        label = session.get(EvidenceLabel, label_id) if label_id is not None else None
        keeping_old = (
            current is not None and label is not None and label.id == current.evidence_label_id
        )
        if label is None or (label.archived_at is not None and not keeping_old):
            errors["evidence_label_id"] = "Pick an evidence label from the list."
        else:
            clean["evidence_label_id"] = label.id

    raw_when = (data.get("occurred_at") or "").strip()
    if current is not None and raw_when == timeutil.form_value(current.occurred_at, tz):
        # The edit form sent back the time it was showing. Keep the stored instant and
        # offset as they are: re-reading it could pick the wrong side of a DST change.
        raw_when = ""
    if raw_when:
        try:
            clean["occurred_at"], clean["occurred_offset_min"] = timeutil.parse_local(raw_when, tz)
        except ValueError:
            errors["occurred_at"] = "Use a date and time like 2026-11-01T18:20."
    elif current is None:
        clean["occurred_at"], clean["occurred_offset_min"] = timeutil.now_with_offset(tz)
    # An edit with the time left blank (or unchanged) keeps the entry's existing time.

    if errors:
        raise InvalidInput(errors)
    return clean


def _status_for(kind: str, current_status: str | None) -> str | None:
    """The status an entry of this kind should have, keeping a valid existing one."""
    allowed = STATUSES.get(kind)
    if allowed is None:
        return None
    return current_status if current_status in allowed else DEFAULT_STATUS[kind]


def create_entry(
    session: Session, project: Project, data: dict[str, str], tz: tzinfo | None = None
) -> Entry:
    clean = _validate(session, data, current=None, tz=tz)
    entry = Entry(project_id=project.id, status=_status_for(clean["kind"], None), **clean)
    session.add(entry)
    session.flush()
    return entry


def update_entry(
    session: Session, entry: Entry, data: dict[str, str], tz: tzinfo | None = None
) -> Entry:
    if entry.deleted_at is not None:
        raise InvalidInput({"entry": "Restore this entry before editing it."})
    clean = _validate(session, data, current=entry, tz=tz)
    for field, value in clean.items():
        setattr(entry, field, value)
    entry.status = _status_for(entry.kind, entry.status)
    session.flush()
    return entry


def delete_entry(session: Session, entry: Entry, at: datetime | None = None) -> None:
    """Soft delete: the entry disappears from the timeline but nothing is removed."""
    if at is not None and at.tzinfo is None:
        raise ValueError("delete_entry needs a time-zone-aware time")
    if entry.deleted_at is None:
        entry.deleted_at = timeutil.as_utc(at) if at is not None else timeutil.now_utc()
        session.flush()


def restore_entry(session: Session, entry: Entry) -> None:
    if entry.deleted_at is not None:
        entry.deleted_at = None
        session.flush()
