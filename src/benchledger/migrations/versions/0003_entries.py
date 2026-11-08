"""Evidence labels (editable list) and notebook entries.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Decision D1 in docs/BACKLOG.md. The owner can rename, reorder or add to these later.
DEFAULT_EVIDENCE_LABELS = ["measured", "observed", "inferred", "suspected"]


def _timestamp(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=None if nullable else sa.func.current_timestamp(),
    )


def upgrade() -> None:
    labels = op.create_table(
        "evidence_labels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=60), nullable=False, unique=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        _timestamp("archived_at", nullable=True),
        _timestamp("created_at"),
    )

    op.create_table(
        "entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "evidence_label_id",
            sa.Integer(),
            sa.ForeignKey("evidence_labels.id"),
            nullable=True,
        ),
        sa.Column("source", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurred_offset_min", sa.Integer(), nullable=False, server_default="0"),
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
        # A typo in a service can't store an unknown kind or an impossible UTC offset.
        sa.CheckConstraint(
            "kind IN ('observation', 'hypothesis', 'decision', 'note', 'question')",
            name="ck_entries_kind",
        ),
        sa.CheckConstraint("occurred_offset_min BETWEEN -840 AND 840", name="ck_entries_offset"),
    )
    op.create_index("ix_entries_project_occurred", "entries", ["project_id", "occurred_at"])

    op.bulk_insert(
        labels,
        [{"name": name, "position": i} for i, name in enumerate(DEFAULT_EVIDENCE_LABELS, start=1)],
    )


def downgrade() -> None:
    op.drop_index("ix_entries_project_occurred", table_name="entries")
    op.drop_table("entries")
    op.drop_table("evidence_labels")
