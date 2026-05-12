"""add pantry query indexes

Revision ID: 20260512_000024
Revises: 20260512_000023
Create Date: 2026-05-12 00:00:24
"""

from __future__ import annotations

from alembic import op


revision = "20260512_000024"
down_revision = "20260512_000023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_stock_lots_household_active_expiry",
        "stock_lots",
        ["household_id", "depleted_at", "expires_on", "created_at"],
    )
    op.create_index(
        "ix_stock_lots_household_location_active",
        "stock_lots",
        ["household_id", "location_id", "depleted_at", "expires_on"],
    )
    op.create_index(
        "ix_stock_lots_household_product_active",
        "stock_lots",
        ["household_id", "product_id", "depleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_lots_household_product_active", table_name="stock_lots")
    op.drop_index("ix_stock_lots_household_location_active", table_name="stock_lots")
    op.drop_index("ix_stock_lots_household_active_expiry", table_name="stock_lots")
