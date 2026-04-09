"""shopping reconciliation fields

Revision ID: 20260409_000015
Revises: 20260409_000014
Create Date: 2026-04-09 00:00:15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_000015"
down_revision = "20260409_000014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column(
        "shopping_list_items",
        sa.Column("requested_quantity", sa.Numeric(12, 3), nullable=True),
    )
    op.add_column(
        "shopping_list_items",
        sa.Column("requested_unit", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "shopping_list_items",
        sa.Column("pantry_location_id", sa.Uuid(), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE shopping_list_items
            SET requested_quantity = quantity,
                requested_unit = unit
            WHERE requested_quantity IS NULL
            """
        )
    )

    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_shopping_list_items_pantry_location_id",
            "shopping_list_items",
            "locations",
            ["pantry_location_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint(
            "fk_shopping_list_items_pantry_location_id",
            "shopping_list_items",
            type_="foreignkey",
        )

    op.drop_column("shopping_list_items", "pantry_location_id")
    op.drop_column("shopping_list_items", "requested_unit")
    op.drop_column("shopping_list_items", "requested_quantity")
