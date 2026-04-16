"""product intelligence run diagnostics

Revision ID: 20260416_000020
Revises: 20260412_000019
Create Date: 2026-04-16 00:00:20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260416_000020"
down_revision = "20260412_000019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_intelligence_runs",
        sa.Column("diagnostics_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("product_intelligence_runs", "diagnostics_payload")
