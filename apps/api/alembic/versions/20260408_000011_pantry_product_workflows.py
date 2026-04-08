"""pantry product workflows

Revision ID: 20260408_000011
Revises: 20260407_000010
Create Date: 2026-04-08 00:00:11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260408_000011"
down_revision = "20260407_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("manual_ingredient_tags", sa.JSON(), nullable=True))

    op.add_column("product_enrichments", sa.Column("enrichment_status", sa.String(length=32), nullable=True))
    op.add_column("product_enrichments", sa.Column("ingredient_tags", sa.JSON(), nullable=True))
    op.add_column("product_enrichments", sa.Column("ingredient_tokens", sa.JSON(), nullable=True))
    op.add_column("product_enrichments", sa.Column("dietary_tags", sa.JSON(), nullable=True))
    op.add_column("product_enrichments", sa.Column("nutriments_payload", sa.JSON(), nullable=True))
    op.add_column("product_enrichments", sa.Column("nutrition_summary_text", sa.Text(), nullable=True))

    op.create_table(
        "shopping_lists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_shopping_lists_household_normalized_name"),
    )
    op.create_index("ix_shopping_lists_household_id", "shopping_lists", ["household_id"])

    op.create_table(
        "shopping_list_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("shopping_list_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("normalized_label", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["shopping_list_id"], ["shopping_lists.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_shopping_list_items_household_id", "shopping_list_items", ["household_id"])
    op.create_index("ix_shopping_list_items_product_id", "shopping_list_items", ["product_id"])
    op.create_index("ix_shopping_list_items_shopping_list_id", "shopping_list_items", ["shopping_list_id"])
    op.create_index(
        "ix_shopping_list_items_status",
        "shopping_list_items",
        ["shopping_list_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_shopping_list_items_status", table_name="shopping_list_items")
    op.drop_index("ix_shopping_list_items_shopping_list_id", table_name="shopping_list_items")
    op.drop_index("ix_shopping_list_items_product_id", table_name="shopping_list_items")
    op.drop_index("ix_shopping_list_items_household_id", table_name="shopping_list_items")
    op.drop_table("shopping_list_items")

    op.drop_index("ix_shopping_lists_household_id", table_name="shopping_lists")
    op.drop_table("shopping_lists")

    op.drop_column("product_enrichments", "nutrition_summary_text")
    op.drop_column("product_enrichments", "nutriments_payload")
    op.drop_column("product_enrichments", "dietary_tags")
    op.drop_column("product_enrichments", "ingredient_tokens")
    op.drop_column("product_enrichments", "ingredient_tags")
    op.drop_column("product_enrichments", "enrichment_status")

    op.drop_column("products", "manual_ingredient_tags")
