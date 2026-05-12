"""stock and import integrity constraints

Revision ID: 20260512_000025
Revises: 20260512_000024
Create Date: 2026-05-12 00:00:25
"""

from __future__ import annotations

from alembic import op


revision = "20260512_000025"
down_revision = "20260512_000024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stock_lots") as batch_op:
        batch_op.create_check_constraint("ck_stock_lots_quantity_non_negative", "quantity >= 0")


def downgrade() -> None:
    with op.batch_alter_table("stock_lots") as batch_op:
        batch_op.drop_constraint("ck_stock_lots_quantity_non_negative", type_="check")
