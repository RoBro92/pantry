from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class ProductAlias(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_aliases"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "normalized_name",
            name="uq_product_aliases_household_normalized_name",
        ),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("pal"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)

    household = relationship("Household", back_populates="product_aliases")
    product = relationship("Product", back_populates="aliases")
