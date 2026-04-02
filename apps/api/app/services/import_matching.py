from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.barcode import Barcode
from app.models.household import Household
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.services.pantry_normalization import normalize_barcode, normalize_lookup_name


@dataclass(frozen=True)
class ImportMatchResult:
    product: Product | None
    status: str
    match_basis: str


def _load_product_for_household(
    db: Session,
    *,
    household: Household,
    product_external_id: str,
) -> Product | None:
    return db.scalar(
        select(Product)
        .where(Product.household_id == household.id)
        .where(Product.external_id == product_external_id)
        .options(selectinload(Product.aliases), selectinload(Product.barcodes))
    )


def resolve_import_line_match(
    db: Session,
    *,
    household: Household,
    raw_label: str,
    barcode: str | None,
    product_external_id: str | None = None,
) -> ImportMatchResult:
    if product_external_id:
        product = _load_product_for_household(
            db,
            household=household,
            product_external_id=product_external_id,
        )
        if product is None:
            raise ValueError("Linked pantry product not found.")
        return ImportMatchResult(product=product, status="matched", match_basis="manual")

    normalized_barcode = None
    if barcode:
        normalized_barcode = normalize_barcode(barcode)
        product = db.scalar(
            select(Product)
            .join(Barcode, Barcode.product_id == Product.id)
            .where(Product.household_id == household.id)
            .where(Barcode.household_id == household.id)
            .where(Barcode.normalized_value == normalized_barcode)
            .options(selectinload(Product.aliases), selectinload(Product.barcodes))
        )
        if product is not None:
            return ImportMatchResult(product=product, status="matched", match_basis="barcode_exact")

    normalized_label = normalize_lookup_name(raw_label)
    product = db.scalar(
        select(Product)
        .where(Product.household_id == household.id)
        .where(Product.normalized_name == normalized_label)
        .options(selectinload(Product.aliases), selectinload(Product.barcodes))
    )
    if product is not None:
        return ImportMatchResult(product=product, status="matched", match_basis="product_exact")

    alias = db.scalar(
        select(ProductAlias)
        .where(ProductAlias.household_id == household.id)
        .where(ProductAlias.normalized_name == normalized_label)
        .options(selectinload(ProductAlias.product).selectinload(Product.aliases))
    )
    if alias is not None and alias.product is not None:
        return ImportMatchResult(product=alias.product, status="matched", match_basis="alias_exact")

    return ImportMatchResult(product=None, status="unresolved", match_basis="none")
