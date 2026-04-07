"""admin lifecycle foundation

Revision ID: 20260407_000009
Revises: 20260406_000008
Create Date: 2026-04-07 00:00:09.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260407_000009"
down_revision = "20260406_000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instance_settings", sa.Column("release_notes_seen_version", sa.String(length=64), nullable=True))
    op.add_column("instance_settings", sa.Column("release_notes_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("instance_settings", "release_notes_seen_at")
    op.drop_column("instance_settings", "release_notes_seen_version")
