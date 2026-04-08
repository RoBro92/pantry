from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.location import Location
from app.models.product import Product
from app.models.household import Household
from app.models.stock_lot import StockLot
from app.models.base import utc_now
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.pantry_catalog import (
    create_product,
    ensure_product_alias,
    ensure_product_barcode,
    find_alias_conflicts,
    get_location_by_external_id,
    get_product_by_barcode,
    get_product_by_external_id,
    get_product_by_lookup_name,
    merge_manual_ingredient_tags,
)
from app.services.product_enrichment import ProductEnrichmentError, apply_confirmed_product_enrichment
from app.services.pantry_normalization import normalize_unit, require_text


def _validate_positive_quantity(quantity: Decimal) -> Decimal:
    if quantity <= Decimal("0"):
        raise ValueError("Quantity must be greater than zero.")
    return quantity.quantize(Decimal("0.001"))


def _load_stock_lot(
    db: Session,
    *,
    household: Household,
    external_id: str,
) -> StockLot | None:
    return db.scalar(
        select(StockLot)
        .where(StockLot.household_id == household.id)
        .where(StockLot.external_id == external_id)
        .options(
            selectinload(StockLot.product).selectinload(Product.aliases),
            selectinload(StockLot.product).selectinload(Product.barcodes),
            selectinload(StockLot.product).selectinload(Product.enrichments),
            selectinload(StockLot.location).selectinload(Location.location_group),
        )
    )


def get_stock_lot_by_external_id(
    db: Session,
    *,
    household: Household,
    external_id: str,
) -> StockLot | None:
    return _load_stock_lot(db, household=household, external_id=external_id)


def add_stock_lot(
    db: Session,
    *,
    household: Household,
    actor: User,
    product_external_id: str,
    location_external_id: str,
    quantity: Decimal,
    note: str | None,
    purchased_on: date | None,
    expires_on: date | None,
    unit_override: str | None = None,
    commit: bool = True,
) -> StockLot:
    product = get_product_by_external_id(db, household=household, external_id=product_external_id)
    if product is None:
        raise ValueError("Product not found.")

    location = get_location_by_external_id(db, household=household, external_id=location_external_id)
    if location is None:
        raise ValueError("Location not found.")

    normalized_quantity = _validate_positive_quantity(quantity)
    normalized_note = require_text(note, field_name="Note") if note else None
    normalized_unit = normalize_unit(unit_override) if unit_override else product.default_unit
    if purchased_on and expires_on and expires_on < purchased_on:
        raise ValueError("Expiry date cannot be earlier than purchase date.")

    lot = StockLot(
        household_id=household.id,
        product_id=product.id,
        location_id=location.id,
        quantity=normalized_quantity,
        unit=normalized_unit,
        note=normalized_note,
        purchased_on=purchased_on,
        expires_on=expires_on,
    )
    db.add(lot)
    db.flush()
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="stock.added",
        target_type="stock_lot",
        target_external_id=lot.external_id,
        event_metadata={
            "product_name": product.name,
            "location_name": location.name,
            "location_group_name": location.location_group.name,
            "quantity": str(normalized_quantity),
            "unit": normalized_unit,
        },
    )
    if commit:
        db.commit()
        db.refresh(lot)
        return get_stock_lot_by_external_id(db, household=household, external_id=lot.external_id) or lot

    return lot


def create_or_add_pantry_entry(
    db: Session,
    *,
    household: Household,
    actor: User,
    name: str,
    quantity: Decimal,
    unit: str,
    location_external_id: str,
    barcode: str | None,
    aliases: list[str],
    manual_ingredient_tags: list[str],
    note: str | None,
    purchased_on: date | None,
    expires_on: date | None,
    existing_product_external_id: str | None = None,
    confirmed_enrichment=None,
    allow_create_product: bool = True,
) -> dict[str, object]:
    display_name = require_text(name, field_name="Product name")
    matched_product, match_message = _find_existing_product(
        db,
        household=household,
        display_name=display_name,
        barcode=barcode,
    )

    if matched_product is not None:
        if existing_product_external_id != matched_product.external_id:
            return {
                "status": "existing_product",
                "message": match_message,
                "matched_product": matched_product,
                "alias_conflicts": [],
            }

        alias_conflicts = find_alias_conflicts(
            db,
            household=household,
            aliases=aliases,
            ignore_product_id=matched_product.id,
        )
        if alias_conflicts:
            conflict_names = ", ".join(conflict["alias"] for conflict in alias_conflicts)
            return {
                "status": "alias_conflict",
                "message": f"These aliases are already in use: {conflict_names}.",
                "alias_conflicts": alias_conflicts,
            }

        metadata_message = _merge_existing_product_metadata(
            db,
            household=household,
            actor=actor,
            product=matched_product,
            aliases=aliases,
            barcode=barcode,
            manual_ingredient_tags=manual_ingredient_tags,
        )
        lot = add_stock_lot(
            db,
            household=household,
            actor=actor,
            product_external_id=matched_product.external_id,
            location_external_id=location_external_id,
            quantity=quantity,
            note=note,
            purchased_on=purchased_on,
            expires_on=expires_on,
            unit_override=None,
            commit=False,
        )
        enrichment_message = _try_apply_confirmed_enrichment(
            db,
            household=household,
            actor=actor,
            product=matched_product,
            confirmed_enrichment=confirmed_enrichment,
        )
        db.commit()
        db.expire_all()
        refreshed_product = get_product_by_external_id(
            db,
            household=household,
            external_id=matched_product.external_id,
        ) or matched_product
        refreshed_lot = get_stock_lot_by_external_id(db, household=household, external_id=lot.external_id) or lot
        return {
            "status": "added_to_existing",
            "message": _build_enrichment_message(
                _build_metadata_message(
                    f"Added another stock lot to {matched_product.name}.",
                    metadata_message,
                ),
                enrichment_message,
            ),
            "product": refreshed_product,
            "lot": refreshed_lot,
            "matched_product": refreshed_product,
            "alias_conflicts": [],
        }

    alias_conflicts = find_alias_conflicts(db, household=household, aliases=aliases)
    if alias_conflicts:
        conflict_names = ", ".join(conflict["alias"] for conflict in alias_conflicts)
        return {
            "status": "alias_conflict",
            "message": f"These aliases are already in use: {conflict_names}.",
            "alias_conflicts": alias_conflicts,
        }

    if not allow_create_product:
        return {
            "status": "creation_not_allowed",
            "message": "Ask a household admin to create this product or choose an existing one.",
            "alias_conflicts": [],
        }

    product = create_product(
        db,
        household=household,
        actor=actor,
        name=display_name,
        default_unit=unit,
        aliases=aliases,
        barcodes=[barcode] if barcode and barcode.strip() else [],
        manual_ingredient_tags=manual_ingredient_tags,
        commit=False,
    )
    lot = add_stock_lot(
        db,
        household=household,
        actor=actor,
        product_external_id=product.external_id,
        location_external_id=location_external_id,
        quantity=quantity,
        note=note,
        purchased_on=purchased_on,
        expires_on=expires_on,
        unit_override=None,
        commit=False,
    )
    enrichment_message = _try_apply_confirmed_enrichment(
        db,
        household=household,
        actor=actor,
        product=product,
        confirmed_enrichment=confirmed_enrichment,
    )
    db.commit()
    db.expire_all()
    refreshed_product = get_product_by_external_id(db, household=household, external_id=product.external_id) or product
    refreshed_lot = get_stock_lot_by_external_id(db, household=household, external_id=lot.external_id) or lot
    return {
        "status": "created",
        "message": _build_enrichment_message(
            f"Created {product.name} and added the first stock lot.",
            enrichment_message,
        ),
        "product": refreshed_product,
        "lot": refreshed_lot,
        "matched_product": None,
        "alias_conflicts": [],
    }


def _find_existing_product(
    db: Session,
    *,
    household: Household,
    display_name: str,
    barcode: str | None,
) -> tuple[Product | None, str]:
    barcode_product = None
    if barcode and barcode.strip():
        barcode_product = get_product_by_barcode(db, household=household, barcode=barcode)

    name_product = get_product_by_lookup_name(db, household=household, lookup_name=display_name)
    matched_product = barcode_product or name_product
    if matched_product is None:
        return None, ""

    if barcode_product is not None and name_product is not None and barcode_product.id != name_product.id:
        return barcode_product, (
            f"The barcode entered here already belongs to {barcode_product.name}. "
            "Add this as another stock lot to that product or clear the barcode."
        )
    if barcode_product is not None:
        return barcode_product, f"{barcode_product.name} already exists for this barcode."
    return name_product, f"{name_product.name} already exists."


def _merge_existing_product_metadata(
    db: Session,
    *,
    household: Household,
    actor: User,
    product: Product,
    aliases: list[str],
    barcode: str | None,
    manual_ingredient_tags: list[str],
) -> str | None:
    added_aliases = [
        alias_name
        for alias_name in aliases
        if ensure_product_alias(db, household=household, product=product, alias_name=alias_name)
    ]

    added_barcodes: list[str] = []
    if barcode and barcode.strip():
        barcode_product = get_product_by_barcode(db, household=household, barcode=barcode)
        if barcode_product is not None and barcode_product.id != product.id:
            raise ValueError(f"The barcode entered here already belongs to {barcode_product.name}.")
        if ensure_product_barcode(db, household=household, product=product, barcode_value=barcode):
            added_barcodes.append(barcode.strip())

    manual_ingredients_updated = merge_manual_ingredient_tags(
        product,
        manual_ingredient_tags=manual_ingredient_tags,
    )
    if manual_ingredients_updated:
        db.add(product)

    if not added_aliases and not added_barcodes and not manual_ingredients_updated:
        return None

    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="product.metadata_updated",
        target_type="product",
        target_external_id=product.external_id,
        event_metadata={
            "product_name": product.name,
            "aliases_added": added_aliases,
            "barcodes_added": added_barcodes,
            "manual_ingredient_tags": list(product.manual_ingredient_tags or []),
        },
    )

    parts: list[str] = []
    if added_aliases:
        parts.append(f"saved aliases: {', '.join(added_aliases)}")
    if added_barcodes:
        parts.append("saved barcode")
    if manual_ingredients_updated:
        parts.append("saved manual ingredients")
    return "; ".join(parts)


def _try_apply_confirmed_enrichment(
    db: Session,
    *,
    household: Household,
    actor: User,
    product: Product,
    confirmed_enrichment,
) -> str | None:
    if confirmed_enrichment is None:
        return None
    try:
        apply_confirmed_product_enrichment(
            db,
            household=household,
            actor=actor,
            product=product,
            confirmed_enrichment=confirmed_enrichment,
        )
        return "Open Food Facts details linked."
    except ProductEnrichmentError as exc:
        return f"Open Food Facts details were not linked: {exc}"


def _build_metadata_message(base_message: str, metadata_message: str | None) -> str:
    if not metadata_message:
        return base_message
    return f"{base_message} Pantry also {metadata_message}."


def _build_enrichment_message(base_message: str, enrichment_message: str | None) -> str:
    if not enrichment_message:
        return base_message
    return f"{base_message} {enrichment_message}"


def remove_stock_from_lot(
    db: Session,
    *,
    household: Household,
    actor: User,
    lot_external_id: str,
    quantity: Decimal,
) -> StockLot:
    lot = get_stock_lot_by_external_id(db, household=household, external_id=lot_external_id)
    if lot is None or lot.depleted_at is not None:
        raise ValueError("Stock lot not found.")

    normalized_quantity = _validate_positive_quantity(quantity)
    if normalized_quantity > lot.quantity:
        raise ValueError("Cannot remove more stock than remains in the lot.")

    lot.quantity = (lot.quantity - normalized_quantity).quantize(Decimal("0.001"))
    if lot.quantity == Decimal("0.000"):
        lot.depleted_at = utc_now()

    db.add(lot)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="stock.removed",
        target_type="stock_lot",
        target_external_id=lot.external_id,
        event_metadata={
            "product_name": lot.product.name,
            "location_name": lot.location.name,
            "location_group_name": lot.location.location_group.name,
            "quantity": str(normalized_quantity),
            "unit": lot.unit,
            "remaining_quantity": str(lot.quantity),
        },
    )
    db.commit()
    db.refresh(lot)
    return get_stock_lot_by_external_id(db, household=household, external_id=lot.external_id) or lot


def move_stock_lot(
    db: Session,
    *,
    household: Household,
    actor: User,
    lot_external_id: str,
    quantity: Decimal,
    destination_location_external_id: str,
) -> tuple[StockLot, StockLot | None]:
    lot = get_stock_lot_by_external_id(db, household=household, external_id=lot_external_id)
    if lot is None or lot.depleted_at is not None:
        raise ValueError("Stock lot not found.")

    destination = get_location_by_external_id(
        db,
        household=household,
        external_id=destination_location_external_id,
    )
    if destination is None:
        raise ValueError("Destination location not found.")
    if destination.id == lot.location_id:
        raise ValueError("Destination location must be different from the current location.")

    normalized_quantity = _validate_positive_quantity(quantity)
    if normalized_quantity > lot.quantity:
        raise ValueError("Cannot move more stock than remains in the lot.")

    created_lot: StockLot | None = None
    source_location = lot.location

    if normalized_quantity == lot.quantity:
        lot.location_id = destination.id
        lot.location = destination
        db.add(lot)
        target_external_id = lot.external_id
        created_external_id = None
    else:
        lot.quantity = (lot.quantity - normalized_quantity).quantize(Decimal("0.001"))
        created_lot = StockLot(
            household_id=household.id,
            product_id=lot.product_id,
            location_id=destination.id,
            quantity=normalized_quantity,
            unit=lot.unit,
            note=lot.note,
            purchased_on=lot.purchased_on,
            expires_on=lot.expires_on,
        )
        db.add(lot)
        db.add(created_lot)
        db.flush()
        target_external_id = lot.external_id
        created_external_id = created_lot.external_id

    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="stock.moved",
        target_type="stock_lot",
        target_external_id=target_external_id,
        event_metadata={
            "product_name": lot.product.name,
            "from_location_name": source_location.name,
            "from_location_group_name": source_location.location_group.name,
            "to_location_name": destination.name,
            "to_location_group_name": destination.location_group.name,
            "quantity": str(normalized_quantity),
            "unit": lot.unit,
            "preserved_lot_identity": created_lot is None,
            "created_lot_external_id": created_external_id,
        },
    )
    db.commit()
    refreshed_lot = get_stock_lot_by_external_id(db, household=household, external_id=lot.external_id) or lot
    refreshed_created_lot = (
        get_stock_lot_by_external_id(db, household=household, external_id=created_lot.external_id)
        if created_lot is not None
        else None
    )
    return refreshed_lot, refreshed_created_lot
