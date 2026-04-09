"""product notes

Revision ID: 20260409_000017
Revises: 20260409_000016
Create Date: 2026-04-09 00:00:17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_000017"
down_revision = "20260409_000016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("notes", sa.String(length=2000), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "notes")
