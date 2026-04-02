from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class Barcode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "barcodes"
    __table_args__ = (
        UniqueConstraint("household_id", "normalized_value", name="uq_barcodes_household_normalized_value"),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("brc"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    value: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(64), nullable=False)

    household = relationship("Household", back_populates="barcodes")
    product = relationship("Product", back_populates="barcodes")
