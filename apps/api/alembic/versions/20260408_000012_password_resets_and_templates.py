"""password resets and smtp templates

Revision ID: 20260408_000012
Revises: 20260408_000011
Create Date: 2026-04-08 15:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260408_000012"
down_revision = "20260408_000011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instance_settings",
        sa.Column("password_reset_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "instance_settings",
        sa.Column("password_reset_subject_template", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "instance_settings",
        sa.Column("password_reset_body_template", sa.Text(), nullable=True),
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index(
        "ix_password_reset_tokens_expires_at",
        "password_reset_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

    op.drop_column("instance_settings", "password_reset_body_template")
    op.drop_column("instance_settings", "password_reset_subject_template")
    op.drop_column("instance_settings", "password_reset_enabled")
