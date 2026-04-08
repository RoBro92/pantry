from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class ShoppingList(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shopping_lists"
    __table_args__ = (
        UniqueConstraint("household_id", "normalized_name", name="uq_shopping_lists_household_normalized_name"),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("shl"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    merged_into_list_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("shopping_lists.id"),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    household = relationship("Household", back_populates="shopping_lists")
    items = relationship("ShoppingListItem", back_populates="shopping_list")
    merged_into_list = relationship("ShoppingList", remote_side="ShoppingList.id")
