"""Initial schema: users and change_log.

Revision ID: 0001
Revises:
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    users = op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="owner"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )

    op.create_table(
        "change_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("table_name", sa.String(length=64), nullable=False),
        sa.Column("row_id", sa.String(length=64), nullable=False),
        sa.Column("field", sa.String(length=64), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
    )
    op.create_index("ix_change_log_record", "change_log", ["table_name", "row_id"])

    # The single owner account for v1. Logins for other users come later (C1).
    op.bulk_insert(users, [{"id": 1, "name": "Owner", "role": "owner"}])


def downgrade() -> None:
    op.drop_index("ix_change_log_record", table_name="change_log")
    op.drop_table("change_log")
    op.drop_table("users")
