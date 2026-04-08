from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class ShoppingListItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shopping_list_items"

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("sli"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    shopping_list_id: Mapped[UUID] = mapped_column(ForeignKey("shopping_lists.id"), nullable=False)
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_label: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    household = relationship("Household", back_populates="shopping_list_items")
    shopping_list = relationship("ShoppingList", back_populates="items")
    product = relationship("Product", back_populates="shopping_list_items")
