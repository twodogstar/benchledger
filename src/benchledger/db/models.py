"""ORM models.

  - users:       the author of every entry and change (requirement U1)
  - change_log:  add-only record of every change to any audited record (requirement M2)
  - areas:       the editable list of project areas (Settings -> Lists)
  - projects:    one bench project and its living description (requirement M1)
  - evidence_labels: the editable list of evidence labels (decision D1)
  - entries:     dated notebook entries per project (requirements M2, M3)
  - tasks:       next-step checklist per project (requirement M5)

Models that inherit `Audited` have every insert, update and delete written to change_log
automatically (see db/audit.py). Keep models in step with the Alembic migrations;
tests/test_db.py fails if they drift.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from benchledger.db.base import Base

OWNER_ID = 1  # the single owner account seeded by migration 0001

# Entry kinds (M2, M3). Migration 0003 copies this list into a CHECK constraint.
ENTRY_KINDS = ("observation", "hypothesis", "decision", "note", "question")


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


class EvidenceLabel(Base, Audited):
    """How an entry or fault is known: measured, observed, inferred, suspected (D1).

    Managed like areas in Settings -> Lists. Retired labels stay on old records.
    """

    __tablename__ = "evidence_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )


class Entry(Base, Audited):
    """A dated notebook entry (M2): observation, hypothesis, decision, note or question.

    Hypotheses and questions also carry a status (M3). `occurred_at` is when it happened,
    in UTC; `occurred_offset_min` keeps the UTC offset it was entered in (N7).
    Entries are soft-deleted (`deleted_at`) so history and links stay intact.
    """

    __tablename__ = "entries"
    __table_args__ = (
        Index("ix_entries_project_occurred", "project_id", "occurred_at"),
        CheckConstraint(
            "kind IN ('observation', 'hypothesis', 'decision', 'note', 'question')",
            name="ck_entries_kind",
        ),
        # Real UTC offsets run from -12:00 to +14:00; allow +/-14 h either way.
        CheckConstraint("occurred_offset_min BETWEEN -840 AND 840", name="ck_entries_offset"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    evidence_label_id: Mapped[int | None] = mapped_column(ForeignKey("evidence_labels.id"))
    source: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str | None] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occurred_offset_min: Mapped[int] = mapped_column(Integer, default=0)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), default=OWNER_ID)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship()
    evidence_label: Mapped[EvidenceLabel | None] = relationship()


class Task(Base, Audited):
    """A next-step task on a project's checklist (M5). Soft-deleted like entries."""

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_project", "project_id", "done", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    text: Mapped[str] = mapped_column(String(300))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    due_on: Mapped[date | None] = mapped_column(Date)  # a calendar day; no time or zone
    position: Mapped[int] = mapped_column(Integer, default=0)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), default=OWNER_ID)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship()
