from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class RecipeURLImport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recipe_url_imports"

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("rim"), unique=True, nullable=False
    )
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    recipe_id: Mapped[UUID | None] = mapped_column(ForeignKey("recipes.id"), nullable=True)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="captured")
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)

    household = relationship("Household", back_populates="recipe_url_imports")
    recipe = relationship("Recipe", back_populates="url_imports")
    requested_by_user = relationship("User", back_populates="recipe_url_imports_requested")
