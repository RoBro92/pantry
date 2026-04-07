"""product enrichment foundation

Revision ID: 20260407_000010
Revises: 20260407_000009
Create Date: 2026-04-07 00:00:10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260407_000010"
down_revision = "20260407_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_enrichments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_product_id", sa.String(length=128), nullable=False),
        sa.Column("source_barcode", sa.String(length=64), nullable=True),
        sa.Column("source_product_name", sa.String(length=255), nullable=True),
        sa.Column("source_product_url", sa.String(length=2048), nullable=True),
        sa.Column("product_image_url", sa.String(length=2048), nullable=True),
        sa.Column("ingredients_text", sa.Text(), nullable=True),
        sa.Column("allergens_text", sa.Text(), nullable=True),
        sa.Column("traces_text", sa.Text(), nullable=True),
        sa.Column("allergen_tags", sa.JSON(), nullable=True),
        sa.Column("trace_tags", sa.JSON(), nullable=True),
        sa.Column("nutrition_summary", sa.JSON(), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=True),
        sa.Column("match_status", sa.String(length=64), nullable=True),
        sa.Column("match_confidence", sa.Float(), nullable=True),
        sa.Column("source_attribution", sa.JSON(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("product_id", "source_name", name="uq_product_enrichments_product_source"),
    )
    op.create_index("ix_product_enrichments_household_id", "product_enrichments", ["household_id"])
    op.create_index("ix_product_enrichments_product_id", "product_enrichments", ["product_id"])
    op.create_index(
        "ix_product_enrichments_source_lookup",
        "product_enrichments",
        ["source_name", "source_product_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_enrichments_source_lookup", table_name="product_enrichments")
    op.drop_index("ix_product_enrichments_product_id", table_name="product_enrichments")
    op.drop_index("ix_product_enrichments_household_id", table_name="product_enrichments")
    op.drop_table("product_enrichments")
