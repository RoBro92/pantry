from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class Household(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "households"

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("hse"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dietary_preferences: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)

    memberships = relationship("Membership", back_populates="household")
    location_groups = relationship("LocationGroup", back_populates="household")
    locations = relationship("Location", back_populates="household")
    products = relationship("Product", back_populates="household")
    product_enrichments = relationship("ProductEnrichment", back_populates="household")
    product_intelligence_records = relationship("ProductIntelligence", back_populates="household")
    product_intelligence_runs = relationship("ProductIntelligenceRun", back_populates="household")
    product_aliases = relationship("ProductAlias", back_populates="household")
    canonical_items = relationship("CanonicalItem", back_populates="household")
    canonical_aliases = relationship("CanonicalAlias", back_populates="household")
    product_canonical_links = relationship("ProductCanonicalLink", back_populates="household")
    barcodes = relationship("Barcode", back_populates="household")
    stock_lots = relationship("StockLot", back_populates="household")
    shopping_lists = relationship("ShoppingList", back_populates="household")
    shopping_list_items = relationship("ShoppingListItem", back_populates="household")
    recipes = relationship("Recipe", back_populates="household")
    recipe_ingredients = relationship("RecipeIngredient", back_populates="household")
    recipe_url_imports = relationship("RecipeURLImport", back_populates="household")
    import_jobs = relationship("ImportJob", back_populates="household")
    import_source_files = relationship("ImportSourceFile", back_populates="household")
    import_lines = relationship("ImportLine", back_populates="household")
    ai_provider_configs = relationship("AIProviderConfig", back_populates="household")
    audit_events = relationship("AuditEvent", back_populates="household")
