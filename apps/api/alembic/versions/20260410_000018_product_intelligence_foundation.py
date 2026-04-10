"""product intelligence foundation

Revision ID: 20260410_000018
Revises: 20260409_000017
Create Date: 2026-04-10 00:00:18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260410_000018"
down_revision = "20260409_000017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_intelligence_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("source_provider", sa.String(length=64), nullable=False),
        sa.Column("source_model", sa.String(length=128), nullable=True),
        sa.Column("classification_scope", sa.String(length=64), nullable=False),
        sa.Column("classification_version", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("source_data_hash", sa.String(length=128), nullable=False),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale_short", sa.Text(), nullable=True),
        sa.Column("primary_ingredient_type", sa.String(length=128), nullable=True),
        sa.Column("ingredient_families", sa.JSON(), nullable=True),
        sa.Column("food_category", sa.String(length=128), nullable=True),
        sa.Column("dietary_tags", sa.JSON(), nullable=True),
        sa.Column("allergen_tags", sa.JSON(), nullable=True),
        sa.Column("recipe_role_tags", sa.JSON(), nullable=True),
        sa.Column("substitution_groups", sa.JSON(), nullable=True),
        sa.Column("pantry_use_tags", sa.JSON(), nullable=True),
        sa.Column("structured_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("product_id", name="uq_product_intelligence_records_product"),
    )
    op.create_index(
        "ix_product_intelligence_records_household_id",
        "product_intelligence_records",
        ["household_id"],
    )
    op.create_index(
        "ix_product_intelligence_records_product_id",
        "product_intelligence_records",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_intelligence_records_product_id", table_name="product_intelligence_records")
    op.drop_index("ix_product_intelligence_records_household_id", table_name="product_intelligence_records")
    op.drop_table("product_intelligence_records")
