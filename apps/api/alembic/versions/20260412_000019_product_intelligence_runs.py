"""product intelligence background runs

Revision ID: 20260412_000019
Revises: 20260410_000018
Create Date: 2026-04-12 00:00:19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260412_000019"
down_revision = "20260410_000018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_intelligence_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("source_model", sa.String(length=128), nullable=True),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("target_product_external_ids", sa.JSON(), nullable=False),
        sa.Column("target_product_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("classified_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stale_reclassified_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("batch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_batch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_payload", sa.JSON(), nullable=False),
        sa.Column("events_payload", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.String(length=512), nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_progress_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(
        "ix_product_intelligence_runs_household_id",
        "product_intelligence_runs",
        ["household_id"],
    )
    op.create_index(
        "ix_product_intelligence_runs_status",
        "product_intelligence_runs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_intelligence_runs_status", table_name="product_intelligence_runs")
    op.drop_index("ix_product_intelligence_runs_household_id", table_name="product_intelligence_runs")
    op.drop_table("product_intelligence_runs")
