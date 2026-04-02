from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "location_group_id",
            "normalized_name",
            name="uq_locations_group_normalized_name",
        ),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("loc"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    location_group_id: Mapped[UUID] = mapped_column(ForeignKey("location_groups.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)

    household = relationship("Household", back_populates="locations")
    location_group = relationship("LocationGroup", back_populates="locations")
    stock_lots = relationship("StockLot", back_populates="location")
