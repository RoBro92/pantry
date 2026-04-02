from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class Recipe(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recipes"

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("rcp"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    household = relationship("Household", back_populates="recipes")
    ingredients = relationship("RecipeIngredient", back_populates="recipe")
    url_imports = relationship("RecipeURLImport", back_populates="recipe")
