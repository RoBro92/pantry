from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class Household(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "households"

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("hse"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    memberships = relationship("Membership", back_populates="household")

