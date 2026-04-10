from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class ProductIntelligence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_intelligence_records"
    __table_args__ = (
        UniqueConstraint("product_id", name="uq_product_intelligence_records_product"),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("pit"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    classification_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    classification_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_data_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float(), nullable=True)
    rationale_short: Mapped[str | None] = mapped_column(Text(), nullable=True)
    primary_ingredient_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ingredient_families: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    food_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dietary_tags: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    allergen_tags: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    recipe_role_tags: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    substitution_groups: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    pantry_use_tags: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    structured_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON(), nullable=True)

    household = relationship("Household", back_populates="product_intelligence_records")
    product = relationship("Product", back_populates="intelligence_records")
