from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.barcode import Barcode
from app.models.household import Household
from app.models.import_line import ImportLine
from app.models.location import Location
from app.models.location_group import LocationGroup
from app.models.product import Product
from app.models.product_canonical_link import ProductCanonicalLink
from app.models.product_alias import ProductAlias
from app.models.product_enrichment import ProductEnrichment
from app.models.product_intelligence import ProductIntelligence
from app.models.recipe_ingredient import RecipeIngredient
from app.models.shopping_list_item import ShoppingListItem
from app.models.stock_lot import StockLot
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.canonical_knowledge import sync_product_canonical_link
from app.services.pantry_normalization import (
    dedupe_preserving_order,
    normalize_barcode,
    normalize_lookup_name,
    normalize_text_tags,
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
        .options(
            selectinload(Product.aliases),
            selectinload(Product.barcodes),
            selectinload(Product.enrichments),
            selectinload(Product.intelligence_records),
            selectinload(Product.canonical_link).selectinload(ProductCanonicalLink.canonical_item),
        )
    )


def get_product_by_lookup_name(
    db: Session,
    *,
    household: Household,
    lookup_name: str,
) -> Product | None:
    normalized_name = normalize_lookup_name(lookup_name)

    product = db.scalar(
        select(Product)
        .where(Product.household_id == household.id)
        .where(Product.normalized_name == normalized_name)
        .options(
            selectinload(Product.aliases),
            selectinload(Product.barcodes),
            selectinload(Product.enrichments),
            selectinload(Product.intelligence_records),
            selectinload(Product.canonical_link).selectinload(ProductCanonicalLink.canonical_item),
        )
    )
    if product is not None:
        return product

    alias = db.scalar(
        select(ProductAlias)
        .where(ProductAlias.household_id == household.id)
        .where(ProductAlias.normalized_name == normalized_name)
        .options(selectinload(ProductAlias.product).selectinload(Product.aliases))
    )
    if alias is None:
        return None
    return get_product_by_external_id(db, household=household, external_id=alias.product.external_id)


def get_product_by_barcode(
    db: Session,
    *,
    household: Household,
    barcode: str,
) -> Product | None:
    normalized_barcode = normalize_barcode(barcode)
    barcode_record = db.scalar(
        select(Barcode)
        .where(Barcode.household_id == household.id)
        .where(Barcode.normalized_value == normalized_barcode)
        .options(selectinload(Barcode.product).selectinload(Product.aliases))
        .options(selectinload(Barcode.product).selectinload(Product.barcodes))
        .options(selectinload(Barcode.product).selectinload(Product.enrichments))
        .options(selectinload(Barcode.product).selectinload(Product.intelligence_records))
        .options(selectinload(Barcode.product).selectinload(Product.canonical_link).selectinload(ProductCanonicalLink.canonical_item))
    )
    if barcode_record is None:
        return None
    return get_product_by_external_id(db, household=household, external_id=barcode_record.product.external_id)


def find_alias_conflicts(
    db: Session,
    *,
    household: Household,
    aliases: list[str],
    ignore_product_id=None,
) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    seen_normalized: set[str] = set()

    for alias_name in dedupe_preserving_order([require_text(alias, field_name="Alias") for alias in aliases if alias.strip()]):
        normalized_name = normalize_lookup_name(alias_name)
        if normalized_name in seen_normalized:
            continue
        seen_normalized.add(normalized_name)

        product = db.scalar(
        select(Product)
        .where(Product.household_id == household.id)
        .where(Product.normalized_name == normalized_name)
        .options(
            selectinload(Product.aliases),
            selectinload(Product.barcodes),
            selectinload(Product.enrichments),
            selectinload(Product.intelligence_records),
        )
    )
        if product is not None and product.id != ignore_product_id:
            conflicts.append(
                {
                    "alias": alias_name,
                    "product_external_id": product.external_id,
                    "product_name": product.name,
                }
            )
            continue

        existing_alias = db.scalar(
            select(ProductAlias)
            .where(ProductAlias.household_id == household.id)
            .where(ProductAlias.normalized_name == normalized_name)
            .options(selectinload(ProductAlias.product))
        )
        if existing_alias is not None and existing_alias.product_id != ignore_product_id:
            conflicts.append(
                {
                    "alias": alias_name,
                    "product_external_id": existing_alias.product.external_id,
                    "product_name": existing_alias.product.name,
                }
            )

    return conflicts


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
        raise ValueError(f"{existing_product_name.name} already exists.")

    existing_alias = db.scalar(
        select(ProductAlias)
        .where(ProductAlias.household_id == household.id)
        .where(ProductAlias.normalized_name.in_(normalized_names))
    )
    if existing_alias is not None:
        raise ValueError(f"{existing_alias.product.name} already uses that name or alias.")


def _validate_barcodes(
    db: Session,
    *,
    household: Household,
    normalized_barcodes: list[str],
    ignore_product_id=None,
) -> None:
    if not normalized_barcodes:
        return

    existing_barcode = db.scalar(
        select(Barcode)
        .where(Barcode.household_id == household.id)
        .where(Barcode.normalized_value.in_(normalized_barcodes))
    )
    if existing_barcode is not None and existing_barcode.product_id != ignore_product_id:
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
    notes: str | None = None,
    manual_ingredient_tags: list[str] | None = None,
    commit: bool = True,
) -> Product:
    display_name = require_text(name, field_name="Product name")
    normalized_name = normalize_lookup_name(display_name)
    normalized_unit = normalize_unit(default_unit)
    normalized_notes = require_text(notes, field_name="Product notes") if notes else None

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
    ingredient_tags = normalize_text_tags(manual_ingredient_tags or [], field_name="Ingredient")

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
        notes=normalized_notes,
        manual_ingredient_tags=ingredient_tags or None,
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
            "notes": normalized_notes,
            "manual_ingredient_tags": ingredient_tags,
        },
    )
    sync_product_canonical_link(
        db,
        household=household,
        actor=actor,
        product=product,
    )
    if commit:
        db.commit()
        db.refresh(product)
        return get_product_by_external_id(db, household=household, external_id=product.external_id) or product

    return product


def update_product(
    db: Session,
    *,
    household: Household,
    actor: User,
    product: Product,
    name: str,
    default_unit: str,
    aliases: list[str],
    barcodes: list[str],
    notes: str | None = None,
    manual_ingredient_tags: list[str] | None = None,
    commit: bool = True,
) -> Product:
    display_name = require_text(name, field_name="Product name")
    normalized_name = normalize_lookup_name(display_name)
    normalized_unit = normalize_unit(default_unit)
    normalized_notes = require_text(notes, field_name="Product notes") if notes else None
    ingredient_tags = normalize_text_tags(manual_ingredient_tags or [], field_name="Ingredient")

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

    existing_name_owner = db.scalar(
        select(Product)
        .where(Product.household_id == household.id)
        .where(Product.normalized_name == normalized_name)
    )
    if existing_name_owner is not None and existing_name_owner.id != product.id:
        raise ValueError(f"{existing_name_owner.name} already exists.")

    alias_conflicts = find_alias_conflicts(
        db,
        household=household,
        aliases=[display_name, *alias_display_names],
        ignore_product_id=product.id,
    )
    if alias_conflicts:
        raise ValueError(f"{alias_conflicts[0]['product_name']} already uses that name or alias.")

    _validate_barcodes(
        db,
        household=household,
        normalized_barcodes=barcode_display_values,
        ignore_product_id=product.id,
    )

    product.name = display_name
    product.normalized_name = normalized_name
    product.default_unit = normalized_unit
    product.notes = normalized_notes
    product.manual_ingredient_tags = ingredient_tags or None

    next_alias_pairs = {
        normalize_lookup_name(alias_name): alias_name
        for alias_name in alias_display_names
        if normalize_lookup_name(alias_name) != normalized_name
    }
    existing_aliases = {alias.normalized_name: alias for alias in list(product.aliases)}
    for alias_normalized, alias_model in existing_aliases.items():
        if alias_normalized not in next_alias_pairs:
            db.delete(alias_model)
    for alias_normalized, alias_name in next_alias_pairs.items():
        alias_model = existing_aliases.get(alias_normalized)
        if alias_model is None:
            db.add(
                ProductAlias(
                    household_id=household.id,
                    product_id=product.id,
                    name=alias_name,
                    normalized_name=alias_normalized,
                )
            )
        else:
            alias_model.name = alias_name
            db.add(alias_model)

    next_barcodes = {barcode_value for barcode_value in barcode_display_values}
    existing_barcodes = {barcode.normalized_value: barcode for barcode in list(product.barcodes)}
    for barcode_value, barcode_model in existing_barcodes.items():
        if barcode_value not in next_barcodes:
            db.delete(barcode_model)
    for barcode_value in next_barcodes:
        barcode_model = existing_barcodes.get(barcode_value)
        if barcode_model is None:
            db.add(
                Barcode(
                    household_id=household.id,
                    product_id=product.id,
                    value=barcode_value,
                    normalized_value=barcode_value,
                )
            )
        else:
            barcode_model.value = barcode_value
            barcode_model.normalized_value = barcode_value
            db.add(barcode_model)

    db.add(product)
    sync_product_canonical_link(
        db,
        household=household,
        actor=actor,
        product=product,
    )
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="product.updated",
        target_type="product",
        target_external_id=product.external_id,
        event_metadata={
            "name": display_name,
            "default_unit": normalized_unit,
            "aliases": list(next_alias_pairs.values()),
            "barcodes": list(next_barcodes),
            "notes": normalized_notes,
            "manual_ingredient_tags": ingredient_tags,
        },
    )
    if commit:
        db.commit()
        db.refresh(product)
        return get_product_by_external_id(db, household=household, external_id=product.external_id) or product

    return product


def delete_product(
    db: Session,
    *,
    household: Household,
    actor: User,
    product: Product,
    commit: bool = True,
) -> None:
    stock_lots = db.scalars(
        select(StockLot)
        .where(StockLot.household_id == household.id)
        .where(StockLot.product_id == product.id)
    ).all()
    stock_lot_ids = [lot.id for lot in stock_lots]

    if stock_lot_ids:
        import_lines_with_lots = db.scalars(
            select(ImportLine)
            .where(ImportLine.household_id == household.id)
            .where(ImportLine.confirmed_stock_lot_id.in_(stock_lot_ids))
        ).all()
        for import_line in import_lines_with_lots:
            import_line.confirmed_stock_lot_id = None
            import_line.confirmed_stock_lot = None
            db.add(import_line)

    shopping_items = db.scalars(
        select(ShoppingListItem)
        .where(ShoppingListItem.household_id == household.id)
        .where(ShoppingListItem.product_id == product.id)
    ).all()
    for item in shopping_items:
        item.product_id = None
        item.product = None
        db.add(item)

    recipe_ingredients = db.scalars(
        select(RecipeIngredient)
        .where(RecipeIngredient.household_id == household.id)
        .where(RecipeIngredient.product_id == product.id)
    ).all()
    for ingredient in recipe_ingredients:
        ingredient.product_id = None
        ingredient.product = None
        db.add(ingredient)

    import_lines = db.scalars(
        select(ImportLine)
        .where(ImportLine.household_id == household.id)
        .where(
            (ImportLine.product_id == product.id)
            | (ImportLine.suggested_product_id == product.id)
        )
    ).all()
    for import_line in import_lines:
        if import_line.product_id == product.id:
            import_line.product_id = None
            import_line.product = None
        if import_line.suggested_product_id == product.id:
            import_line.suggested_product_id = None
            import_line.suggested_product = None
        db.add(import_line)

    aliases = db.scalars(
        select(ProductAlias)
        .where(ProductAlias.household_id == household.id)
        .where(ProductAlias.product_id == product.id)
    ).all()
    barcodes = db.scalars(
        select(Barcode)
        .where(Barcode.household_id == household.id)
        .where(Barcode.product_id == product.id)
    ).all()
    enrichments = db.scalars(
        select(ProductEnrichment)
        .where(ProductEnrichment.household_id == household.id)
        .where(ProductEnrichment.product_id == product.id)
    ).all()
    intelligence_records = db.scalars(
        select(ProductIntelligence)
        .where(ProductIntelligence.household_id == household.id)
        .where(ProductIntelligence.product_id == product.id)
    ).all()
    canonical_link = db.scalar(select(ProductCanonicalLink).where(ProductCanonicalLink.product_id == product.id))

    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="product.deleted",
        target_type="product",
        target_external_id=product.external_id,
        event_metadata={
            "name": product.name,
            "stock_lot_count": len(stock_lots),
            "alias_count": len(aliases),
            "barcode_count": len(barcodes),
            "enrichment_count": len(enrichments),
            "intelligence_count": len(intelligence_records),
            "canonical_linked": canonical_link is not None,
            "shopping_item_reference_count": len(shopping_items),
            "recipe_reference_count": len(recipe_ingredients),
            "import_line_reference_count": len(import_lines),
        },
    )

    for alias in aliases:
        db.delete(alias)
    for barcode in barcodes:
        db.delete(barcode)
    for enrichment in enrichments:
        db.delete(enrichment)
    for intelligence in intelligence_records:
        db.delete(intelligence)
    if canonical_link is not None:
        db.delete(canonical_link)
    for lot in stock_lots:
        db.delete(lot)

    db.delete(product)

    if commit:
        db.commit()


def ensure_product_alias(
    db: Session,
    *,
    household: Household,
    product: Product,
    alias_name: str,
) -> bool:
    display_name = require_text(alias_name, field_name="Alias")
    normalized_name = normalize_lookup_name(display_name)

    if normalized_name == product.normalized_name:
        return False

    existing_product = db.scalar(
        select(Product)
        .where(Product.household_id == household.id)
        .where(Product.normalized_name == normalized_name)
    )
    if existing_product is not None:
        return existing_product.id == product.id and False

    existing_alias = db.scalar(
        select(ProductAlias)
        .where(ProductAlias.household_id == household.id)
        .where(ProductAlias.normalized_name == normalized_name)
    )
    if existing_alias is not None:
        return False

    db.add(
        ProductAlias(
            household_id=household.id,
            product_id=product.id,
            name=display_name,
            normalized_name=normalized_name,
        )
    )
    db.flush()
    return True


def ensure_product_barcode(
    db: Session,
    *,
    household: Household,
    product: Product,
    barcode_value: str,
) -> bool:
    normalized_value = normalize_barcode(barcode_value)

    existing_barcode = db.scalar(
        select(Barcode)
        .where(Barcode.household_id == household.id)
        .where(Barcode.normalized_value == normalized_value)
    )
    if existing_barcode is not None:
        return existing_barcode.product_id == product.id and False

    db.add(
        Barcode(
            household_id=household.id,
            product_id=product.id,
            value=normalized_value,
            normalized_value=normalized_value,
        )
    )
    db.flush()
    return True


def merge_manual_ingredient_tags(
    product: Product,
    *,
    manual_ingredient_tags: list[str],
) -> bool:
    next_tags = normalize_text_tags(manual_ingredient_tags, field_name="Ingredient")
    existing_tags = normalize_text_tags(list(product.manual_ingredient_tags or []), field_name="Ingredient")
    if not next_tags:
        return False

    merged_tags = normalize_text_tags([*existing_tags, *next_tags], field_name="Ingredient")
    if merged_tags == existing_tags:
        return False
    product.manual_ingredient_tags = merged_tags
    return True
