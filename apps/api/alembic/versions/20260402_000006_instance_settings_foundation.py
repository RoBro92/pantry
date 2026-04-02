"""instance settings foundation

Revision ID: 20260402_000006
Revises: 20260402_000005
Create Date: 2026-04-02 00:00:06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260402_000006"
down_revision = "20260402_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instance_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=32), nullable=False),
        sa.Column("public_base_url", sa.String(length=2048), nullable=True),
        sa.Column("smtp_host", sa.String(length=255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=True),
        sa.Column("smtp_username", sa.String(length=255), nullable=True),
        sa.Column("encrypted_smtp_password", sa.String(length=4096), nullable=True),
        sa.Column("smtp_from_email", sa.String(length=320), nullable=True),
        sa.Column("smtp_from_name", sa.String(length=255), nullable=True),
        sa.Column("smtp_security", sa.String(length=16), nullable=True),
        sa.Column("smtp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("smtp_last_test_status", sa.String(length=32), nullable=False, server_default="never"),
        sa.Column("smtp_last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("smtp_last_test_error", sa.String(length=512), nullable=True),
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
        sa.UniqueConstraint("scope_key", name="uq_instance_settings_scope_key"),
    )


def downgrade() -> None:
    op.drop_table("instance_settings")
