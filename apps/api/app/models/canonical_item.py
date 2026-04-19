from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class CanonicalItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "canonical_items"
    __table_args__ = (
        UniqueConstraint("household_id", "normalized_name", name="uq_canonical_items_household_normalized_name"),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("can"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ingredient")
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    source_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provenance_payload: Mapped[dict[str, object] | None] = mapped_column(JSON(), nullable=True)

    household = relationship("Household", back_populates="canonical_items")
    aliases = relationship("CanonicalAlias", back_populates="canonical_item")
    product_links = relationship("ProductCanonicalLink", back_populates="canonical_item")
