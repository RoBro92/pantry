"""identity foundation

Revision ID: 20260402_000001
Revises:
Create Date: 2026-04-02 00:00:01
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260402_000001"
down_revision = None
branch_labels = None
depends_on = None


ROLE_PLATFORM_ADMIN_ID = uuid.UUID("d8758991-df70-4aa1-b6b7-311a3dc30b32")
ROLE_HOUSEHOLD_ADMIN_ID = uuid.UUID("ddfc0f87-df8a-4810-966c-c7ea9d0b49d6")
ROLE_HOUSEHOLD_USER_ID = uuid.UUID("4ca065a8-bb63-4898-a658-3361f28418f1")


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("platform_role_id", sa.Uuid(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["platform_role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("external_id"),
    )

    op.create_table(
        "households",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )

    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
        sa.UniqueConstraint("user_id", "household_id", name="uq_memberships_user_household"),
    )

    role_table = sa.table(
        "roles",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("scope", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
    )

    op.bulk_insert(
        role_table,
        [
            {
                "id": ROLE_PLATFORM_ADMIN_ID,
                "code": "platform_admin",
                "scope": "platform",
                "name": "Platform Admin",
                "description": "Installation-wide administrator with cross-household visibility.",
            },
            {
                "id": ROLE_HOUSEHOLD_ADMIN_ID,
                "code": "household_admin",
                "scope": "household",
                "name": "Household Admin",
                "description": "Household administrator with member and settings management rights.",
            },
            {
                "id": ROLE_HOUSEHOLD_USER_ID,
                "code": "household_user",
                "scope": "household",
                "name": "Household User",
                "description": "Standard household member.",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("memberships")
    op.drop_table("households")
    op.drop_table("users")
    op.drop_table("roles")

