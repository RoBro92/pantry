from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.barcode import Barcode
from app.models.household import Household
from app.models.location import Location
from app.models.location_group import LocationGroup
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.pantry_normalization import (
    dedupe_preserving_order,
    normalize_barcode,
    normalize_lookup_name,
    normalize_unit,
    require_text,
)


def get_location_group_by_external_id(
    db: Session,
    *,
    household: Household,
    external_id: str,
) -> LocationGroup | None:
    return db.scalar(
        select(LocationGroup)
        .where(LocationGroup.household_id == household.id)
        .where(LocationGroup.external_id == external_id)
    )


def get_location_by_external_id(
    db: Session,
    *,
    household: Household,
    external_id: str,
) -> Location | None:
    return db.scalar(
        select(Location)
        .where(Location.household_id == household.id)
        .where(Location.external_id == external_id)
        .options(selectinload(Location.location_group))
    )


def get_product_by_external_id(
    db: Session,
    *,
    household: Household,
    external_id: str,
) -> Product | None:
    return db.scalar(
        select(Product)
        .where(Product.household_id == household.id)
        .where(Product.external_id == external_id)
        .options(selectinload(Product.aliases), selectinload(Product.barcodes))
    )


def create_location_group(
    db: Session,
    *,
    household: Household,
    actor: User,
    name: str,
) -> LocationGroup:
    normalized_name = normalize_lookup_name(name)
    display_name = require_text(name, field_name="Location group name")

    existing = db.scalar(
        select(LocationGroup)
        .where(LocationGroup.household_id == household.id)
        .where(LocationGroup.normalized_name == normalized_name)
    )
    if existing is not None:
        raise ValueError("A location group with that name already exists.")

    group = LocationGroup(
        household_id=household.id,
        name=display_name,
        normalized_name=normalized_name,
    )
    db.add(group)
    db.flush()
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="location_group.created",
        target_type="location_group",
        target_external_id=group.external_id,
        event_metadata={"name": display_name},
    )
    db.commit()
    db.refresh(group)
    return group


def create_location(
    db: Session,
    *,
    household: Household,
    actor: User,
    location_group_external_id: str,
    name: str,
) -> Location:
    group = get_location_group_by_external_id(
        db,
        household=household,
        external_id=location_group_external_id,
    )
    if group is None:
        raise ValueError("Location group not found.")

    normalized_name = normalize_lookup_name(name)
    display_name = require_text(name, field_name="Location name")

    existing = db.scalar(
        select(Location)
        .where(Location.household_id == household.id)
        .where(Location.location_group_id == group.id)
        .where(Location.normalized_name == normalized_name)
    )
    if existing is not None:
        raise ValueError("A location with that name already exists in this group.")

    location = Location(
        household_id=household.id,
        location_group_id=group.id,
        name=display_name,
        normalized_name=normalized_name,
    )
    db.add(location)
    db.flush()
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="location.created",
        target_type="location",
        target_external_id=location.external_id,
        event_metadata={"name": display_name, "location_group_name": group.name},
    )
    db.commit()
    db.refresh(location)
    return get_location_by_external_id(db, household=household, external_id=location.external_id) or location


def _validate_product_names(
    db: Session,
    *,
    household: Household,
    normalized_names: list[str],
) -> None:
    existing_product_name = db.scalar(
        select(Product).where(Product.household_id == household.id).where(Product.normalized_name.in_(normalized_names))
    )
    if existing_product_name is not None:
        raise ValueError("A product with the same name or alias already exists.")

    existing_alias = db.scalar(
        select(ProductAlias)
        .where(ProductAlias.household_id == household.id)
        .where(ProductAlias.normalized_name.in_(normalized_names))
    )
    if existing_alias is not None:
        raise ValueError("A product with the same name or alias already exists.")


def _validate_barcodes(
    db: Session,
    *,
    household: Household,
    normalized_barcodes: list[str],
) -> None:
    if not normalized_barcodes:
        return

    existing_barcode = db.scalar(
        select(Barcode)
        .where(Barcode.household_id == household.id)
        .where(Barcode.normalized_value.in_(normalized_barcodes))
    )
    if existing_barcode is not None:
        raise ValueError("A product with one of those barcodes already exists.")


def create_product(
    db: Session,
    *,
    household: Household,
    actor: User,
    name: str,
    default_unit: str,
    aliases: list[str],
    barcodes: list[str],
) -> Product:
    display_name = require_text(name, field_name="Product name")
    normalized_name = normalize_lookup_name(display_name)
    normalized_unit = normalize_unit(default_unit)

    alias_display_names = dedupe_preserving_order(
        [require_text(alias, field_name="Alias") for alias in aliases if alias.strip()]
    )
    alias_normalized_names = dedupe_preserving_order(
        [
            normalized
            for normalized in [normalize_lookup_name(alias_name) for alias_name in alias_display_names]
            if normalized != normalized_name
        ]
    )
    barcode_display_values = dedupe_preserving_order([normalize_barcode(value) for value in barcodes if value.strip()])

    _validate_product_names(
        db,
        household=household,
        normalized_names=[normalized_name, *alias_normalized_names],
    )
    _validate_barcodes(db, household=household, normalized_barcodes=barcode_display_values)

    product = Product(
        household_id=household.id,
        name=display_name,
        normalized_name=normalized_name,
        default_unit=normalized_unit,
    )
    db.add(product)
    db.flush()

    alias_models: list[ProductAlias] = []
    for alias_name, alias_normalized in zip(
        [alias for alias in alias_display_names if normalize_lookup_name(alias) != normalized_name],
        alias_normalized_names,
        strict=False,
    ):
        alias_model = ProductAlias(
            household_id=household.id,
            product_id=product.id,
            name=alias_name,
            normalized_name=alias_normalized,
        )
        alias_models.append(alias_model)
        db.add(alias_model)

    barcode_models: list[Barcode] = []
    for barcode_value in barcode_display_values:
        barcode_model = Barcode(
            household_id=household.id,
            product_id=product.id,
            value=barcode_value,
            normalized_value=barcode_value,
        )
        barcode_models.append(barcode_model)
        db.add(barcode_model)

    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="product.created",
        target_type="product",
        target_external_id=product.external_id,
        event_metadata={
            "name": display_name,
            "default_unit": normalized_unit,
            "aliases": [alias.name for alias in alias_models],
            "barcodes": [barcode.value for barcode in barcode_models],
        },
    )
    db.commit()
    db.refresh(product)
    return get_product_by_external_id(db, household=household, external_id=product.external_id) or product
