"""Editable lists shown in Settings -> Lists: project areas and evidence labels (D1).

Every list works the same way: items have a unique name (ignoring case), a position the
owner can change, and can be retired (hidden from new choices, kept on records that
already use them) and restored. Nothing is ever deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from benchledger.db.models import Area, EvidenceLabel
from benchledger.services import InvalidInput

MAX_NAME = 60

ListModel = type[Area] | type[EvidenceLabel]
ListItem = Area | EvidenceLabel


@dataclass(frozen=True)
class ListSpec:
    model: ListModel
    noun: str  # used in messages: "An area called ... already exists."
    title: str  # heading on the settings page


# URL name -> list. The URL name appears in /settings/<name>/... routes.
LISTS: dict[str, ListSpec] = {
    "areas": ListSpec(Area, "area", "Project areas"),
    "evidence-labels": ListSpec(EvidenceLabel, "evidence label", "Evidence labels"),
}


def _noun(model: ListModel) -> str:
    return next(spec.noun for spec in LISTS.values() if spec.model is model)


def list_items(
    session: Session, model: ListModel, include_archived: bool = False
) -> list[ListItem]:
    query = select(model).order_by(model.archived_at.is_not(None), model.position, model.name)
    if not include_archived:
        query = query.where(model.archived_at.is_(None))
    return list(session.scalars(query))


def get_item(session: Session, model: ListModel, item_id: int) -> ListItem | None:
    return session.get(model, item_id)


def _clean_name(
    session: Session, model: ListModel, name: str, current: ListItem | None = None
) -> str:
    name = " ".join(name.split())  # trim and collapse inner spaces
    if not name:
        raise InvalidInput({"name": "Name is required."})
    if len(name) > MAX_NAME:
        raise InvalidInput({"name": f"Keep it under {MAX_NAME} characters."})
    clash = session.scalar(select(model).where(func.lower(model.name) == name.lower()))
    if clash is not None and clash is not current:
        noun = _noun(model)
        article = "An" if noun[0] in "aeiou" else "A"
        raise InvalidInput({"name": f"{article} {noun} called {clash.name!r} already exists."})
    return name


def create_item(session: Session, model: ListModel, name: str) -> ListItem:
    name = _clean_name(session, model, name)
    last = session.scalar(select(func.max(model.position))) or 0
    item = model(name=name, position=last + 1)
    session.add(item)
    session.flush()
    return item


def rename_item(session: Session, item: ListItem, name: str) -> ListItem:
    item.name = _clean_name(session, type(item), name, current=item)
    session.flush()
    return item


def move_item(session: Session, item: ListItem, direction: str) -> None:
    """Swap with the neighbouring active item. direction is 'up' or 'down'."""
    if direction not in ("up", "down"):
        raise InvalidInput({"direction": "Move up or down."})
    active = list_items(session, type(item))
    if item not in active:
        return
    i = active.index(item)
    j = i - 1 if direction == "up" else i + 1
    if not 0 <= j < len(active):
        return
    # Renumber the whole list first so positions are always unique and in order.
    for n, other in enumerate(active, start=1):
        other.position = n
    active[i].position, active[j].position = active[j].position, active[i].position
    session.flush()


def archive_item(session: Session, item: ListItem) -> None:
    """Retire an item: hidden from new choices, kept on records that already use it."""
    if item.archived_at is None:
        item.archived_at = datetime.now(UTC)
        session.flush()


def restore_item(session: Session, item: ListItem) -> None:
    if item.archived_at is not None:
        item.archived_at = None
        session.flush()
