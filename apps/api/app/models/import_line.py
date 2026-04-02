from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class ImportLine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_lines"

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("iml"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    import_job_id: Mapped[UUID] = mapped_column(ForeignKey("import_jobs.id"), nullable=False)
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    suggested_product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    confirmed_stock_lot_id: Mapped[UUID | None] = mapped_column(ForeignKey("stock_lots.id"), nullable=True)
    position: Mapped[int] = mapped_column(Integer(), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_label: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_label: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    purchased_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="needs_review")
    match_basis: Mapped[str] = mapped_column(String(32), nullable=False, default="none")

    household = relationship("Household", back_populates="import_lines")
    import_job = relationship("ImportJob", back_populates="lines")
    product = relationship("Product", back_populates="import_lines", foreign_keys=[product_id])
    suggested_product = relationship(
        "Product",
        back_populates="suggested_import_lines",
        foreign_keys=[suggested_product_id],
    )
    confirmed_stock_lot = relationship("StockLot", back_populates="import_lines")
