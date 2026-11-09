"""Tasks: the next-step checklist per project (M5).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=None if nullable else sa.func.current_timestamp(),
    )


def upgrade() -> None:
    # The server defaults below only matter for rows written without the app (e.g. by hand
    # in sqlite3); the app always sets these columns. author_id 1 is OWNER_ID from 0001.
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            server_default="1",
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        _timestamp("deleted_at", nullable=True),
    )
    op.create_index("ix_tasks_project", "tasks", ["project_id", "done", "position"])


def downgrade() -> None:
    op.drop_index("ix_tasks_project", table_name="tasks")
    op.drop_table("tasks")
