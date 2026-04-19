"""canonical knowledge base groundwork

Revision ID: 20260419_000021
Revises: 20260416_000020
Create Date: 2026-04-19 00:00:21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_000021"
down_revision = "20260416_000020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_items",
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("item_type", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=True),
        sa.Column("provenance_payload", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_canonical_items_household_normalized_name"),
    )
    op.create_table(
        "canonical_aliases",
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_item_id", sa.Uuid(), nullable=False),
        sa.Column("alias_type", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=True),
        sa.Column("provenance_payload", sa.JSON(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["canonical_item_id"], ["canonical_items.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint(
            "household_id",
            "alias_type",
            "normalized_value",
            name="uq_canonical_aliases_household_type_normalized_value",
        ),
    )
    op.create_table(
        "product_canonical_links",
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_item_id", sa.Uuid(), nullable=False),
        sa.Column("link_status", sa.String(length=32), nullable=False),
        sa.Column("match_method", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=64), nullable=True),
        sa.Column("provenance_payload", sa.JSON(), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["canonical_item_id"], ["canonical_items.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("product_id", name="uq_product_canonical_links_product_id"),
    )


def downgrade() -> None:
    op.drop_table("product_canonical_links")
    op.drop_table("canonical_aliases")
    op.drop_table("canonical_items")
