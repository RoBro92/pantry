from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class SetupState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "setup_states"
    __table_args__ = (UniqueConstraint("scope_key", name="uq_setup_states_scope_key"),)

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("stp"), unique=True, nullable=False
    )
    scope_key: Mapped[str] = mapped_column(String(32), nullable=False, default="instance")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    payload: Mapped[dict[str, object]] = mapped_column(JSON(), nullable=False, default=dict)
    encrypted_ai_api_key: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    encrypted_smtp_password: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
