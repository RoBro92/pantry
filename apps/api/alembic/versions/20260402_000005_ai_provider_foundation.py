"""ai provider foundation

Revision ID: 20260402_000005
Revises: 20260402_000004
Create Date: 2026-04-02 00:00:05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_000005"
down_revision = "20260402_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=64), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=True),
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("default_model", sa.String(length=255), nullable=False),
        sa.Column("encrypted_api_key", sa.String(length=4096), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("health_status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("health_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("health_error", sa.String(length=512), nullable=True),
        sa.Column("available_model_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("scope_type", "scope_key", name="uq_ai_provider_configs_scope"),
    )
    op.create_index("ix_ai_provider_configs_household_id", "ai_provider_configs", ["household_id"])
    op.create_index(
        "ix_ai_provider_configs_provider_type_scope",
        "ai_provider_configs",
        ["provider_type", "scope_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_provider_configs_provider_type_scope", table_name="ai_provider_configs")
    op.drop_index("ix_ai_provider_configs_household_id", table_name="ai_provider_configs")
    op.drop_table("ai_provider_configs")
