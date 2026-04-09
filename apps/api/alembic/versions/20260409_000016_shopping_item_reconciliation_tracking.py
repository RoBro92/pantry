"""shopping item reconciliation tracking

Revision ID: 20260409_000016
Revises: 20260409_000015
Create Date: 2026-04-09 00:00:16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_000016"
down_revision = "20260409_000015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shopping_list_items", sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("shopping_list_items", "reconciled_at")
