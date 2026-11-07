"""ORM models.

Iteration 0 has only the two tables everything else will depend on:
  - users:       the author of every entry and change (requirement U1)
  - change_log:  add-only record of every change to any record (requirement M2)

Keep these in step with the Alembic migrations; tests/test_db.py fails if they drift.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from benchledger.db.base import Base


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
