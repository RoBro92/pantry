from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.ai import AI_HEALTH_UNKNOWN
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class AIProviderConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_provider_configs"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_key", name="uq_ai_provider_configs_scope"),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("aic"), unique=True, nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    household_id: Mapped[UUID | None] = mapped_column(ForeignKey("households.id"), nullable=True)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    default_model: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_api_key: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    health_status: Mapped[str] = mapped_column(String(32), nullable=False, default=AI_HEALTH_UNKNOWN)
    health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    available_model_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capabilities: Mapped[dict[str, object]] = mapped_column(JSON(), nullable=False, default=dict)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    household = relationship("Household", back_populates="ai_provider_configs")
