"""household restore and smtp test recipient

Revision ID: 20260409_000014
Revises: 20260408_000013
Create Date: 2026-04-09 11:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260409_000014"
down_revision = "20260408_000013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instance_settings",
        sa.Column("smtp_test_recipient_email", sa.String(length=320), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("instance_settings", "smtp_test_recipient_email")
