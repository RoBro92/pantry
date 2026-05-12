"""lock setup for upgraded installs with users

Revision ID: 20260512_000023
Revises: 20260505_000022
Create Date: 2026-05-12 00:00:23
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "20260512_000023"
down_revision = "20260505_000022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    has_users = bind.scalar(sa.text("SELECT 1 FROM users LIMIT 1")) is not None
    has_setup_state = bind.scalar(sa.text("SELECT 1 FROM setup_states WHERE scope_key = 'instance' LIMIT 1")) is not None
    if not has_users or has_setup_state:
        return

    setup_states = sa.table(
        "setup_states",
        sa.column("id", sa.Uuid()),
        sa.column("external_id", sa.String()),
        sa.column("scope_key", sa.String()),
        sa.column("status", sa.String()),
        sa.column("payload", sa.JSON()),
        sa.column("encrypted_ai_api_key", sa.String()),
        sa.column("encrypted_smtp_password", sa.String()),
        sa.column("completed_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        setup_states,
        [
            {
                "id": uuid4(),
                "external_id": f"stp_upgrade_{uuid4().hex[:12]}",
                "scope_key": "instance",
                "status": "completed",
                "payload": {},
                "encrypted_ai_api_key": None,
                "encrypted_smtp_password": None,
                "completed_at": now,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM setup_states "
        "WHERE scope_key = 'instance' "
        "AND status = 'completed' "
        "AND external_id LIKE 'stp_upgrade_%'"
    )
