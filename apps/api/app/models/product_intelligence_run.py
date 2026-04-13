from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class ProductIntelligenceRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_intelligence_runs"

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("pir"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    target_product_external_ids: Mapped[list[str]] = mapped_column(JSON(), nullable=False, default=list)
    target_product_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    classified_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    stale_reclassified_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    batch_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    completed_batch_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    items_payload: Mapped[list[dict[str, object]]] = mapped_column(JSON(), nullable=False, default=list)
    events_payload: Mapped[list[dict[str, object]]] = mapped_column(JSON(), nullable=False, default=list)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_progress_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    household = relationship("Household", back_populates="product_intelligence_runs")
    requested_by_user = relationship("User", back_populates="product_intelligence_runs_requested")
