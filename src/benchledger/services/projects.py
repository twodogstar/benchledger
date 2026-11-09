"""Projects (requirement M1)."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from benchledger.db.models import Area, Project
from benchledger.services import InvalidInput, parse_id

STAGES = ["Idea", "Planning", "Active", "Paused", "Blocked", "Done"]
PRIORITIES = ["High", "Medium", "Low"]
TEXT_FIELDS = ["goal", "current_state", "setup", "wiring", "parts"]
FORM_FIELDS = ["name", "area_id", "stage", "priority", *TEXT_FIELDS]
MAX_NAME = 100
RESERVED_SLUGS = {"new"}  # would clash with the /projects/new page


def list_projects(
    session: Session,
    stage: str | None = None,
    include_archived: bool = False,
    limit: int | None = None,
) -> list[Project]:
    query = (
        select(Project)
        .order_by(Project.updated_at.desc(), Project.id.desc())
        .options(selectinload(Project.area))  # every card and tile shows the area
    )
    if stage:
        query = query.where(Project.stage == stage)
    if not include_archived:
        query = query.where(Project.archived_at.is_(None))
    if limit is not None:
        query = query.limit(limit)
    return list(session.scalars(query))


def get_project(session: Session, slug: str) -> Project | None:
    return session.scalar(select(Project).where(Project.slug == slug))


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60].rstrip("-") or "project"


def _unique_slug(session: Session, name: str) -> str:
    base = slugify(name)
    slug, n = base, 2

    def taken(candidate: str) -> bool:
        if candidate in RESERVED_SLUGS:
            return True
        return session.scalar(select(Project.id).where(Project.slug == candidate)) is not None

    while taken(slug):
        slug, n = f"{base}-{n}", n + 1
    return slug


def _validate(session: Session, data: dict[str, str], current: Project | None) -> dict:
    """Check form data and return clean values. Raises InvalidInput with every problem."""
    errors: dict[str, str] = {}
    clean: dict = {}

    name = " ".join(data.get("name", "").split())
    if not name:
        errors["name"] = "Name is required."
    elif len(name) > MAX_NAME:
        errors["name"] = f"Keep it under {MAX_NAME} characters."
    clean["name"] = name

    stage = data.get("stage") or "Idea"
    if stage not in STAGES:
        errors["stage"] = "Pick a stage from the list."
    clean["stage"] = stage

    priority = data.get("priority") or "Medium"
    if priority not in PRIORITIES:
        errors["priority"] = "Pick a priority from the list."
    clean["priority"] = priority

    clean["area_id"] = None
    raw_area = (data.get("area_id") or "").strip()
    if raw_area:
        area_id = parse_id(raw_area)
        area = session.get(Area, area_id) if area_id is not None else None
        keeping_old = current is not None and area is not None and area.id == current.area_id
        if area is None or (area.archived_at is not None and not keeping_old):
            errors["area_id"] = "Pick an area from the list."
        else:
            clean["area_id"] = area.id

    for field in TEXT_FIELDS:
        # Keep the user's line breaks; just normalise Windows line endings and trim.
        clean[field] = data.get(field, "").replace("\r\n", "\n").strip()

    if errors:
        raise InvalidInput(errors)
    return clean


def create_project(session: Session, data: dict[str, str]) -> Project:
    clean = _validate(session, data, current=None)
    project = Project(slug=_unique_slug(session, clean["name"]), **clean)
    session.add(project)
    session.flush()
    return project


def update_project(session: Session, project: Project, data: dict[str, str]) -> Project:
    clean = _validate(session, data, current=project)
    for field, value in clean.items():
        setattr(project, field, value)
    session.flush()
    return project


def archive_project(session: Session, project: Project) -> None:
    if project.archived_at is None:
        project.archived_at = datetime.now(UTC)
        session.flush()


def restore_project(session: Session, project: Project) -> None:
    if project.archived_at is not None:
        project.archived_at = None
        session.flush()
