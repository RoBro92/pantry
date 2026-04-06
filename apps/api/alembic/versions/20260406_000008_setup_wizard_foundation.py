"""setup wizard foundation

Revision ID: 20260406_000008
Revises: 20260403_000007
Create Date: 2026-04-06 00:00:08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260406_000008"
down_revision = "20260403_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "setup_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="in_progress"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("encrypted_ai_api_key", sa.String(length=4096), nullable=True),
        sa.Column("encrypted_smtp_password", sa.String(length=4096), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("scope_key", name="uq_setup_states_scope_key"),
    )
    op.add_column("users", sa.Column("dietary_preferences", sa.JSON(), nullable=True))
    op.add_column("households", sa.Column("dietary_preferences", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("households", "dietary_preferences")
    op.drop_column("users", "dietary_preferences")
    op.drop_table("setup_states")
