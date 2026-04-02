from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("household_id", "normalized_name", name="uq_products_household_normalized_name"),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("prd"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_unit: Mapped[str] = mapped_column(String(32), nullable=False)

    household = relationship("Household", back_populates="products")
    aliases = relationship("ProductAlias", back_populates="product")
    barcodes = relationship("Barcode", back_populates="product")
    stock_lots = relationship("StockLot", back_populates="product")
    recipe_ingredients = relationship("RecipeIngredient", back_populates="product")
