"""The editable list of project areas (Settings -> Lists)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from benchledger.db.models import Area
from benchledger.services import InvalidInput

MAX_NAME = 60


def list_areas(session: Session, include_archived: bool = False) -> list[Area]:
    query = select(Area).order_by(Area.archived_at.is_not(None), Area.position, Area.name)
    if not include_archived:
        query = query.where(Area.archived_at.is_(None))
    return list(session.scalars(query))


def get_area(session: Session, area_id: int) -> Area | None:
    return session.get(Area, area_id)


def _clean_name(session: Session, name: str, current: Area | None = None) -> str:
    name = " ".join(name.split())  # trim and collapse inner spaces
    if not name:
        raise InvalidInput({"name": "Name is required."})
    if len(name) > MAX_NAME:
        raise InvalidInput({"name": f"Keep it under {MAX_NAME} characters."})
    clash = session.scalar(select(Area).where(func.lower(Area.name) == name.lower()))
    if clash is not None and clash is not current:
        raise InvalidInput({"name": f"An area called {clash.name!r} already exists."})
    return name


def create_area(session: Session, name: str) -> Area:
    name = _clean_name(session, name)
    last = session.scalar(select(func.max(Area.position))) or 0
    area = Area(name=name, position=last + 1)
    session.add(area)
    session.flush()
    return area


def rename_area(session: Session, area: Area, name: str) -> Area:
    area.name = _clean_name(session, name, current=area)
    session.flush()
    return area


def move_area(session: Session, area: Area, direction: str) -> None:
    """Swap with the neighbouring active area. direction is 'up' or 'down'."""
    active = list_areas(session)
    if area not in active:
        return
    i = active.index(area)
    j = i - 1 if direction == "up" else i + 1
    if not 0 <= j < len(active):
        return
    # Renumber the whole list first so positions are always unique and in order.
    for n, a in enumerate(active, start=1):
        a.position = n
    active[i].position, active[j].position = active[j].position, active[i].position
    session.flush()


def archive_area(session: Session, area: Area) -> None:
    """Retire an area: hidden from new choices, kept on projects that already use it."""
    if area.archived_at is None:
        area.archived_at = datetime.now(UTC)
        session.flush()


def restore_area(session: Session, area: Area) -> None:
    if area.archived_at is not None:
        area.archived_at = None
        session.flush()
