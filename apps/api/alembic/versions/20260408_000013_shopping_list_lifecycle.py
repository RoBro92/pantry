"""shopping list lifecycle

Revision ID: 20260408_000013
Revises: 20260408_000012
Create Date: 2026-04-08 00:00:13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260408_000013"
down_revision = "20260408_000012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column(
        "shopping_lists",
        sa.Column("lifecycle_state", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.add_column("shopping_lists", sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shopping_lists", sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shopping_lists", sa.Column("merged_into_list_id", sa.Uuid(), nullable=True))
    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_shopping_lists_merged_into_list_id",
            "shopping_lists",
            "shopping_lists",
            ["merged_into_list_id"],
            ["id"],
        )

    op.add_column("shopping_list_items", sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shopping_list_items", sa.Column("not_purchased_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE shopping_list_items
            SET status = 'purchased',
                purchased_at = completed_at
            WHERE status = 'completed'
            """
        )
    )

    if bind.dialect.name != "sqlite":
        op.alter_column("shopping_lists", "lifecycle_state", server_default=None)


def downgrade() -> None:
    op.drop_column("shopping_list_items", "not_purchased_at")
    op.drop_column("shopping_list_items", "purchased_at")

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("fk_shopping_lists_merged_into_list_id", "shopping_lists", type_="foreignkey")
    op.drop_column("shopping_lists", "merged_into_list_id")
    op.drop_column("shopping_lists", "reconciled_at")
    op.drop_column("shopping_lists", "generated_at")
    op.drop_column("shopping_lists", "lifecycle_state")
