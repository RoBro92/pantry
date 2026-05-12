"""add active stock merge uniqueness guard

Revision ID: 20260512_000026
Revises: 20260512_000025
Create Date: 2026-05-12 00:00:26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260512_000026"
down_revision = "20260512_000025"
branch_labels = None
depends_on = None


INDEX_NAME = "ux_stock_lots_active_merge_key"
ACTIVE_PREDICATE = "depleted_at IS NULL AND quantity > 0"


def upgrade() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text(
            "SELECT household_id, product_id, location_id, unit, COALESCE(expires_on, '0001-01-01') AS expires_key, COUNT(*) "
            "FROM stock_lots "
            f"WHERE {ACTIVE_PREDICATE} "
            "GROUP BY household_id, product_id, location_id, unit, COALESCE(expires_on, '0001-01-01') "
            "HAVING COUNT(*) > 1 "
            "LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot add active stock merge uniqueness guard while duplicate active stock lots exist. "
            "Merge or deplete duplicate active stock_lots rows with the same household, product, location, unit, and expiry first."
        )

    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                f"CREATE UNIQUE INDEX {INDEX_NAME} "
                "ON stock_lots (household_id, product_id, location_id, unit, COALESCE(expires_on, DATE '0001-01-01')) "
                f"WHERE {ACTIVE_PREDICATE}"
            )
        )
        return

    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX {INDEX_NAME} "
            "ON stock_lots (household_id, product_id, location_id, unit, COALESCE(expires_on, '0001-01-01')) "
            f"WHERE {ACTIVE_PREDICATE}"
        )
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="stock_lots")
