from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class ProductEnrichment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_enrichments"
    __table_args__ = (
        UniqueConstraint("product_id", "source_name", name="uq_product_enrichments_product_source"),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("pen"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_product_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    product_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    ingredients_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    allergens_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    traces_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    allergen_tags: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    trace_tags: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    nutrition_summary: Mapped[list[dict[str, object]] | None] = mapped_column(JSON(), nullable=True)
    labels: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    categories: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    match_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    match_confidence: Mapped[float | None] = mapped_column(Float(), nullable=True)
    source_attribution: Mapped[dict[str, object] | None] = mapped_column(JSON(), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    household = relationship("Household", back_populates="product_enrichments")
    product = relationship("Product", back_populates="enrichments")
