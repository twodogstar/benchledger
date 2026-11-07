"""ORM models.

  - users:       the author of every entry and change (requirement U1)
  - change_log:  add-only record of every change to any audited record (requirement M2)
  - areas:       the editable list of project areas (Settings -> Lists)
  - projects:    one bench project and its living description (requirement M1)

Models that inherit `Audited` have every insert, update and delete written to change_log
automatically (see db/audit.py). Keep models in step with the Alembic migrations;
tests/test_db.py fails if they drift.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from benchledger.db.base import Base

OWNER_ID = 1  # the single owner account seeded by migration 0001


class Audited:
    """Marker: changes to models that inherit this are recorded in change_log."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), server_default="owner")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )


class ChangeLog(Base):
    """One row per changed field. Rows are only ever added, never edited or deleted."""

    __tablename__ = "change_log"
    __table_args__ = (Index("ix_change_log_record", "table_name", "row_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(10))  # insert | update | delete
    table_name: Mapped[str] = mapped_column(String(64))
    row_id: Mapped[str] = mapped_column(String(64))
    field: Mapped[str | None] = mapped_column(String(64))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)


class Area(Base, Audited):
    """A project area such as Metrology. Retired areas stay on old projects."""

    __tablename__ = "areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )


class Project(Base, Audited):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)  # used in URLs; never changes
    name: Mapped[str] = mapped_column(String(100))
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"))
    stage: Mapped[str] = mapped_column(String(20), default="Idea")
    priority: Mapped[str] = mapped_column(String(10), default="Medium")
    goal: Mapped[str] = mapped_column(Text, default="")
    current_state: Mapped[str] = mapped_column(Text, default="")
    setup: Mapped[str] = mapped_column(Text, default="")
    wiring: Mapped[str] = mapped_column(Text, default="")
    parts: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    area: Mapped[Area | None] = relationship()
