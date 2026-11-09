"""The fault tracker (requirement M4).

A fault records a symptom, how sure we are of it (evidence label), its status, the next
test that would tell the possible explanations apart, and finally the resolution.
A fault can only be Resolved with a resolution written down (also enforced by the
database). Deleting only sets `deleted_at`.
"""

from __future__ import annotations

from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from benchledger import timeutil
from benchledger.db.models import FAULT_STATUSES, EvidenceLabel, Fault, Project
from benchledger.services import InvalidInput, parse_id

STATUSES = list(FAULT_STATUSES)
OPEN_STATUSES = ("Open", "Investigating")
FORM_FIELDS = ["symptom", "status", "evidence_label_id", "next_test", "resolution"]
MAX_TEXT = 20_000  # per field; generous, and copied into the change log on each edit

# Open first, then Investigating, then Resolved; newest first within each.
_STATUS_ORDER = case({"Open": 0, "Investigating": 1, "Resolved": 2}, value=Fault.status)


def list_faults(session: Session, project: Project, include_deleted: bool = False) -> list[Fault]:
    query = (
        select(Fault)
        .where(Fault.project_id == project.id)
        .order_by(_STATUS_ORDER, Fault.created_at.desc(), Fault.id.desc())
    )
    if not include_deleted:
        query = query.where(Fault.deleted_at.is_(None))
    return list(session.scalars(query))


def open_faults(session: Session, limit: int | None = None) -> list[Fault]:
    """Unresolved faults across all non-archived projects (for the dashboard)."""
    query = (
        select(Fault)
        .join(Project, Project.id == Fault.project_id)
        .where(
            Fault.deleted_at.is_(None),
            Fault.status.in_(OPEN_STATUSES),
            Project.archived_at.is_(None),
        )
        .order_by(_STATUS_ORDER, Fault.created_at.desc(), Fault.id.desc())
        .options(selectinload(Fault.project), selectinload(Fault.evidence_label))
    )
    if limit is not None:
        query = query.limit(limit)
    return list(session.scalars(query))


def get_fault(session: Session, project: Project, fault_id: int) -> Fault | None:
    fault = session.get(Fault, fault_id)
    if fault is None or fault.project_id != project.id:
        return None
    return fault


def _text(data: dict[str, str], field: str) -> str:
    # Keep line breaks; normalise Windows line endings and trim.
    return (data.get(field) or "").replace("\r\n", "\n").strip()


def _validate(session: Session, data: dict[str, str], current: Fault | None) -> dict:
    errors: dict[str, str] = {}
    clean: dict = {}

    clean["symptom"] = _text(data, "symptom")
    if not clean["symptom"]:
        errors["symptom"] = "Describe what goes wrong."

    clean["status"] = (data.get("status") or "Open").strip()
    if clean["status"] not in STATUSES:
        errors["status"] = "Pick a status from the list."

    clean["next_test"] = _text(data, "next_test")
    clean["resolution"] = _text(data, "resolution")
    if clean["status"] == "Resolved" and not clean["resolution"]:
        errors["resolution"] = "Say how it was resolved before marking it Resolved."

    for field in ("symptom", "next_test", "resolution"):
        if len(clean[field]) > MAX_TEXT:
            errors[field] = f"Keep it under {MAX_TEXT:,} characters."

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

    if errors:
        raise InvalidInput(errors)
    return clean


def create_fault(session: Session, project: Project, data: dict[str, str]) -> Fault:
    fault = Fault(project_id=project.id, **_validate(session, data, current=None))
    session.add(fault)
    session.flush()
    return fault


def update_fault(session: Session, fault: Fault, data: dict[str, str]) -> Fault:
    if fault.deleted_at is not None:
        raise InvalidInput({"fault": "Restore this fault before editing it."})
    for field, value in _validate(session, data, current=fault).items():
        setattr(fault, field, value)
    session.flush()
    return fault


def delete_fault(session: Session, fault: Fault) -> None:
    if fault.deleted_at is None:
        fault.deleted_at = timeutil.now_utc()
        session.flush()


def restore_fault(session: Session, fault: Fault) -> None:
    if fault.deleted_at is not None:
        fault.deleted_at = None
        session.flush()
