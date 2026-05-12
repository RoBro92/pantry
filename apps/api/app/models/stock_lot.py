from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class StockLot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stock_lots"
    __table_args__ = (CheckConstraint("quantity >= 0", name="ck_stock_lots_quantity_non_negative"),)

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("lot"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("locations.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    purchased_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    depleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    household = relationship("Household", back_populates="stock_lots")
    product = relationship("Product", back_populates="stock_lots")
    location = relationship("Location", back_populates="stock_lots")
    import_lines = relationship("ImportLine", back_populates="confirmed_stock_lot")
