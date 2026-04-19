from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class CanonicalAlias(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "canonical_aliases"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "alias_type",
            "normalized_value",
            name="uq_canonical_aliases_household_type_normalized_value",
        ),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("cal"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    canonical_item_id: Mapped[UUID] = mapped_column(ForeignKey("canonical_items.id"), nullable=False)
    alias_type: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    source_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provenance_payload: Mapped[dict[str, object] | None] = mapped_column(JSON(), nullable=True)

    household = relationship("Household", back_populates="canonical_aliases")
    canonical_item = relationship("CanonicalItem", back_populates="aliases")
