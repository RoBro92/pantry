from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from app.models.identifiers import generate_external_id


class ProductCanonicalLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_canonical_links"
    __table_args__ = (
        UniqueConstraint("product_id", name="uq_product_canonical_links_product_id"),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("pcl"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    canonical_item_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_items.id"), nullable=False)
    link_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    match_method: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provenance_payload: Mapped[dict[str, object] | None] = mapped_column(JSON(), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    household = relationship("Household", back_populates="product_canonical_links")
    product = relationship("Product", back_populates="canonical_link")
    canonical_item = relationship("CanonicalItem", back_populates="product_links")
