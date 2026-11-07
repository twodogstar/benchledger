"""Areas (editable list) and projects.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_AREAS = [
    "Retro computing",
    "Embedded",
    "Metrology",
    "Instrumentation",
    "Tool building",
    "RF/SDR",
    "Test equipment",
    "Other",
]


def _timestamp(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=None if nullable else sa.func.current_timestamp(),
    )


def upgrade() -> None:
    areas = op.create_table(
        "areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=60), nullable=False, unique=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        _timestamp("archived_at", nullable=True),
        _timestamp("created_at"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=80), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("stage", sa.String(length=20), nullable=False, server_default="Idea"),
        sa.Column("priority", sa.String(length=10), nullable=False, server_default="Medium"),
        sa.Column("goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("current_state", sa.Text(), nullable=False, server_default=""),
        sa.Column("setup", sa.Text(), nullable=False, server_default=""),
        sa.Column("wiring", sa.Text(), nullable=False, server_default=""),
        sa.Column("parts", sa.Text(), nullable=False, server_default=""),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        _timestamp("archived_at", nullable=True),
    )

    op.bulk_insert(
        areas,
        [{"name": name, "position": i} for i, name in enumerate(DEFAULT_AREAS, start=1)],
    )


def downgrade() -> None:
    op.drop_table("projects")
    op.drop_table("areas")
