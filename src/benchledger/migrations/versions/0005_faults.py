"""Faults: the fault tracker per project (M4).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
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
    # Server defaults only matter for rows written without the app; author_id 1 is OWNER_ID.
    op.create_table(
        "faults",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("symptom", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Open"),
        sa.Column(
            "evidence_label_id",
            sa.Integer(),
            sa.ForeignKey("evidence_labels.id"),
            nullable=True,
        ),
        sa.Column("next_test", sa.Text(), nullable=False, server_default=""),
        sa.Column("resolution", sa.Text(), nullable=False, server_default=""),
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
        sa.CheckConstraint(
            "status IN ('Open', 'Investigating', 'Resolved')", name="ck_faults_status"
        ),
        # Resolving requires saying how (M4); the database refuses it otherwise. trim() is
        # given tab, LF and CR too: by default SQLite's trim() strips spaces only.
        sa.CheckConstraint(
            "status != 'Resolved' OR "
            "trim(resolution, ' ' || char(9) || char(10) || char(13)) != ''",
            name="ck_faults_resolution",
        ),
    )
    op.create_index("ix_faults_project", "faults", ["project_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_faults_project", table_name="faults")
    op.drop_table("faults")
