from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, utc_now
from app.models.identifiers import generate_external_id


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("evt"), unique=True, nullable=False
    )
    household_id: Mapped[UUID | None] = mapped_column(ForeignKey("households.id"), nullable=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_metadata: Mapped[dict[str, object]] = mapped_column(JSON(), default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    household = relationship("Household", back_populates="audit_events")
    actor_user = relationship("User", back_populates="audit_events")
