"""add user session version

Revision ID: 20260505_000022
Revises: 20260419_000021
Create Date: 2026-05-05 00:00:22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260505_000022"
down_revision = "20260419_000021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "session_version")
