"""The editable list of project areas (Settings -> Lists). See services/lists.py."""

from __future__ import annotations

from sqlalchemy.orm import Session

from benchledger.db.models import Area
from benchledger.services import lists

MAX_NAME = lists.MAX_NAME


def list_areas(session: Session, include_archived: bool = False) -> list[Area]:
    return lists.list_items(session, Area, include_archived=include_archived)


def get_area(session: Session, area_id: int) -> Area | None:
    return session.get(Area, area_id)


def create_area(session: Session, name: str) -> Area:
    return lists.create_item(session, Area, name)


def rename_area(session: Session, area: Area, name: str) -> Area:
    return lists.rename_item(session, area, name)


def move_area(session: Session, area: Area, direction: str) -> None:
    lists.move_item(session, area, direction)


def archive_area(session: Session, area: Area) -> None:
    lists.archive_item(session, area)


def restore_area(session: Session, area: Area) -> None:
    lists.restore_item(session, area)
