"""pantry core

Revision ID: 20260402_000002
Revises: 20260402_000001
Create Date: 2026-04-02 00:00:02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_000002"
down_revision = "20260402_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "location_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_location_groups_household_normalized_name"),
    )
    op.create_index("ix_location_groups_household_id", "location_groups", ["household_id"])

    op.create_table(
        "locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("location_group_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["location_group_id"], ["location_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("household_id", "location_group_id", "normalized_name", name="uq_locations_group_normalized_name"),
    )
    op.create_index("ix_locations_household_id", "locations", ["household_id"])
    op.create_index("ix_locations_location_group_id", "locations", ["location_group_id"])

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("default_unit", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_products_household_normalized_name"),
    )
    op.create_index("ix_products_household_id", "products", ["household_id"])

    op.create_table(
        "product_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_product_aliases_household_normalized_name"),
    )
    op.create_index("ix_product_aliases_household_id", "product_aliases", ["household_id"])
    op.create_index("ix_product_aliases_product_id", "product_aliases", ["product_id"])

    op.create_table(
        "barcodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.String(length=64), nullable=False),
        sa.Column("normalized_value", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("household_id", "normalized_value", name="uq_barcodes_household_normalized_value"),
    )
    op.create_index("ix_barcodes_household_id", "barcodes", ["household_id"])
    op.create_index("ix_barcodes_product_id", "barcodes", ["product_id"])

    op.create_table(
        "stock_lots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("purchased_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("depleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_stock_lots_household_id", "stock_lots", ["household_id"])
    op.create_index("ix_stock_lots_location_id", "stock_lots", ["location_id"])
    op.create_index("ix_stock_lots_product_id", "stock_lots", ["product_id"])
    op.create_index("ix_stock_lots_expires_on", "stock_lots", ["expires_on"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_external_id", sa.String(length=64), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_audit_events_household_occurred_at", "audit_events", ["household_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_household_occurred_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_stock_lots_expires_on", table_name="stock_lots")
    op.drop_index("ix_stock_lots_product_id", table_name="stock_lots")
    op.drop_index("ix_stock_lots_location_id", table_name="stock_lots")
    op.drop_index("ix_stock_lots_household_id", table_name="stock_lots")
    op.drop_table("stock_lots")
    op.drop_index("ix_barcodes_product_id", table_name="barcodes")
    op.drop_index("ix_barcodes_household_id", table_name="barcodes")
    op.drop_table("barcodes")
    op.drop_index("ix_product_aliases_product_id", table_name="product_aliases")
    op.drop_index("ix_product_aliases_household_id", table_name="product_aliases")
    op.drop_table("product_aliases")
    op.drop_index("ix_products_household_id", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_locations_location_group_id", table_name="locations")
    op.drop_index("ix_locations_household_id", table_name="locations")
    op.drop_table("locations")
    op.drop_index("ix_location_groups_household_id", table_name="location_groups")
    op.drop_table("location_groups")
