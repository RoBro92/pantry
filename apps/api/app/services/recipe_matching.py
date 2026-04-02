from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.household import Household
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.services.pantry_normalization import normalize_lookup_name


def resolve_ingredient_product_match(
    db: Session,
    *,
    household: Household,
    ingredient_name: str,
    product_external_id: str | None,
) -> tuple[Product | None, str]:
    if product_external_id:
        product = db.scalar(
            select(Product)
            .where(Product.household_id == household.id)
            .where(Product.external_id == product_external_id)
            .options(selectinload(Product.aliases), selectinload(Product.barcodes))
        )
        if product is None:
            raise ValueError("Linked pantry product not found.")
        return product, "manual"

    normalized_name = normalize_lookup_name(ingredient_name)
    product = db.scalar(
        select(Product)
        .where(Product.household_id == household.id)
        .where(Product.normalized_name == normalized_name)
        .options(selectinload(Product.aliases), selectinload(Product.barcodes))
    )
    if product is not None:
        return product, "automatic"

    alias = db.scalar(
        select(ProductAlias)
        .where(ProductAlias.household_id == household.id)
        .where(ProductAlias.normalized_name == normalized_name)
        .options(selectinload(ProductAlias.product))
    )
    if alias is None:
        return None, "none"

    return alias.product, "automatic"
