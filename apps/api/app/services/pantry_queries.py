from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.audit_event import AuditEvent
from app.models.location import Location
from app.models.location_group import LocationGroup
from app.models.product import Product
from app.models.stock_lot import StockLot
from app.schemas.pantry import (
    AuditEventSummary,
    LocationGroupSummary,
    LocationSummary,
    NearExpiryResponse,
    PantryCounts,
    PantryFilters,
    PantryOverviewResponse,
    PantryProductSummary,
    ProductLocationSummary,
    StockLotSummary,
)
from app.services.location_links import serialize_location_link
from app.services.pantry_normalization import normalize_barcode, normalize_lookup_name
from app.services.pantry_serialization import serialize_product_enrichment_summary
from app.services.shopping_lists import list_open_shopping_product_ids
from app.services.tenancy import HouseholdAccess


@dataclass(frozen=True)
class PantryFilterOptions:
    q: str | None = None
    location_group_external_id: str | None = None
    location_external_id: str | None = None
    near_expiry_only: bool = False


def _today() -> date:
    return date.today()


def _is_near_expiry(lot: StockLot, *, days: int) -> bool:
    if lot.expires_on is None:
        return False
    return lot.expires_on <= (_today() + timedelta(days=days))


def _stock_lot_summary(lot: StockLot, *, near_expiry_days: int) -> StockLotSummary:
    return StockLotSummary(
        external_id=lot.external_id,
        product_external_id=lot.product.external_id,
        product_name=lot.product.name,
        location_external_id=lot.location.external_id,
        location_name=lot.location.name,
        location_group_name=lot.location.location_group.name,
        quantity=lot.quantity,
        unit=lot.unit,
        note=lot.note,
        purchased_on=lot.purchased_on,
        expires_on=lot.expires_on,
        depleted_at=lot.depleted_at,
        is_depleted=lot.depleted_at is not None or lot.quantity <= Decimal("0"),
        is_near_expiry=_is_near_expiry(lot, days=near_expiry_days),
    )


def _format_quantity_display(value: str | Decimal | None) -> str:
    if value is None:
        return "0"
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    formatted = format(decimal_value, "f").rstrip("0").rstrip(".")
    return formatted or "0"


def build_stock_lot_summary(lot: StockLot, *, near_expiry_days: int = 14) -> StockLotSummary:
    return _stock_lot_summary(lot, near_expiry_days=near_expiry_days)


def _event_summary(event: AuditEvent) -> AuditEventSummary:
    metadata = event.event_metadata
    action = event.action

    if action == "stock.added":
        summary = (
            f"Added {_format_quantity_display(metadata['quantity'])} {metadata['unit']} {metadata['product_name']} "
            f"to {metadata['location_group_name']} / {metadata['location_name']}"
        )
    elif action == "stock.removed":
        if metadata.get("remaining_quantity") == "0.000":
            summary = (
                f"Depleted {metadata['product_name']} from "
                f"{metadata['location_group_name']} / {metadata['location_name']}"
            )
        else:
            summary = (
                f"Removed {_format_quantity_display(metadata['quantity'])} {metadata['unit']} {metadata['product_name']} "
                f"from {metadata['location_group_name']} / {metadata['location_name']}"
            )
    elif action == "stock.moved":
        summary = (
            f"Moved {_format_quantity_display(metadata['quantity'])} {metadata['unit']} {metadata['product_name']} "
            f"to {metadata['to_location_group_name']} / {metadata['to_location_name']}"
        )
    elif action == "stock.updated":
        summary = (
            f"Updated {metadata['product_name']} lot in "
            f"{metadata['location_group_name']} / {metadata['location_name']}"
        )
    elif action == "product.created":
        summary = f"Created product {metadata['name']}"
    elif action == "product.updated":
        summary = f"Updated product {metadata['name']}"
    elif action == "product.metadata_updated":
        summary = f"Updated product details for {metadata['product_name']}"
    elif action == "product.enrichment_synced":
        summary = f"Linked Open Food Facts details to {metadata['product_name']}"
    elif action == "location.created":
        summary = f"Created location {metadata['location_group_name']} / {metadata['name']}"
    elif action == "location_group.created":
        summary = f"Created room {metadata['name']}"
    elif action == "shopping_list.item_added":
        summary = f"Added {metadata.get('product_name') or metadata['label']} to the shopping list"
    elif action == "shopping_list.item_completed":
        summary = f"Completed {metadata.get('product_name') or metadata['label']} on the shopping list"
    elif action == "shopping_list.item_updated":
        summary = f"Updated {metadata.get('product_name') or metadata['label']} on the shopping list"
    elif action == "shopping_list.item_linked_product":
        summary = f"Linked {metadata['product_name']} to a shopping item"
    elif action == "shopping_list.exported":
        summary = f"Exported {metadata['name']}"
    elif action == "shopping_list.pending_merged":
        summary = f"Merged pending shopping lists into {metadata['name']}"
    elif action == "shopping_list.returned_to_active":
        summary = f"Moved {metadata['name']} back into the active shopping list"
    elif action == "shopping_list.reconciled":
        summary = f"Finished reconciling {metadata['name']}"
    elif action == "shopping_list.items_reconciled":
        summary = f"Reconciled selected items from {metadata['name']}"
    elif action == "shopping_list.items_returned":
        summary = f"Returned selected items from {metadata['name']} to the active shopping list"
    elif action == "shopping_list.items_deleted":
        summary = f"Deleted selected items from {metadata['name']}"
    elif action == "setup.completed":
        summary = "Completed first-run setup"
    else:
        summary = action.replace("_", " ")

    actor_display = None
    if event.actor_user is not None:
        actor_display = event.actor_user.display_name or event.actor_user.email

    return AuditEventSummary(
        external_id=event.external_id,
        action=event.action,
        summary=summary,
        actor_display=actor_display,
        target_type=event.target_type,
        target_external_id=event.target_external_id,
        occurred_at=event.occurred_at,
    )


def _load_reference_lists(
    db: Session,
    *,
    household_id,
) -> tuple[list[LocationGroup], list[Location], list[Product]]:
    location_groups = db.scalars(
        select(LocationGroup).where(LocationGroup.household_id == household_id).order_by(LocationGroup.name)
    ).all()
    locations = db.scalars(
        select(Location)
        .where(Location.household_id == household_id)
        .options(selectinload(Location.location_group))
        .order_by(Location.name)
    ).all()
    products = db.scalars(
        select(Product)
        .where(Product.household_id == household_id)
        .options(selectinload(Product.aliases), selectinload(Product.barcodes), selectinload(Product.enrichments))
        .order_by(Product.name)
    ).all()
    return location_groups, locations, products


def _load_active_lots(db: Session, *, household_id) -> list[StockLot]:
    return db.scalars(
        select(StockLot)
        .where(StockLot.household_id == household_id)
        .where(StockLot.depleted_at.is_(None))
        .where(StockLot.quantity > Decimal("0"))
        .options(
            selectinload(StockLot.product).selectinload(Product.aliases),
            selectinload(StockLot.product).selectinload(Product.barcodes),
            selectinload(StockLot.product).selectinload(Product.enrichments),
            selectinload(StockLot.location).selectinload(Location.location_group),
        )
        .order_by(StockLot.expires_on, StockLot.created_at)
    ).all()


def _matches_product_query(product: Product, *, query: str | None) -> bool:
    if not query:
        return True

    normalized_query = normalize_lookup_name(query)
    try:
        barcode_query = normalize_barcode(query)
    except ValueError:
        barcode_query = None

    haystacks = [product.normalized_name, *[alias.normalized_name for alias in product.aliases]]
    if any(normalized_query in value for value in haystacks):
        return True
    return bool(
        barcode_query
        and any(barcode_query in barcode.normalized_value for barcode in product.barcodes)
    )


def _matches_lot_scope(lot: StockLot, *, filters: PantryFilterOptions, near_expiry_days: int) -> bool:
    if filters.location_group_external_id and lot.location.location_group.external_id != filters.location_group_external_id:
        return False
    if filters.location_external_id and lot.location.external_id != filters.location_external_id:
        return False
    if filters.near_expiry_only and not _is_near_expiry(lot, days=near_expiry_days):
        return False
    return True


def _summarize_names(values: list[str], *, empty_label: str) -> str:
    unique_values = sorted(dict.fromkeys(values), key=str.casefold)
    if not unique_values:
        return empty_label
    if len(unique_values) <= 2:
        return ", ".join(unique_values)
    return f"{', '.join(unique_values[:2])} +{len(unique_values) - 2}"


def _product_location_summaries(lots: list[StockLot]) -> list[ProductLocationSummary]:
    location_totals: dict[str, dict[str, object]] = defaultdict(
        lambda: {"total_quantity": Decimal("0.000"), "lot_count": 0, "location": None}
    )
    for lot in lots:
        bucket = location_totals[lot.location.external_id]
        bucket["total_quantity"] = bucket["total_quantity"] + lot.quantity
        bucket["lot_count"] = bucket["lot_count"] + 1
        bucket["location"] = lot.location

    return sorted(
        [
            ProductLocationSummary(
                location_external_id=location_external_id,
                location_name=location_data["location"].name,
                location_group_name=location_data["location"].location_group.name,
                total_quantity=location_data["total_quantity"],
                lot_count=location_data["lot_count"],
            )
            for location_external_id, location_data in location_totals.items()
        ],
        key=lambda location: (location.location_group_name.lower(), location.location_name.lower()),
    )


def _build_product_summary(
    *,
    product: Product,
    visible_lots: list[StockLot],
    all_active_lots: list[StockLot],
    open_shopping_product_ids: set,
    near_expiry_days: int,
) -> PantryProductSummary:
    sorted_lots = sorted(
        visible_lots,
        key=lambda lot: (
            lot.expires_on is None,
            lot.expires_on or date.max,
            lot.location.location_group.name.lower(),
            lot.location.name.lower(),
        ),
    )
    nearest_expiry_values = [lot.expires_on for lot in sorted_lots if lot.expires_on is not None]
    room_names = [lot.location.location_group.name for lot in sorted_lots]
    storage_names = [f"{lot.location.location_group.name} / {lot.location.name}" for lot in sorted_lots]

    return PantryProductSummary(
        product_external_id=product.external_id,
        product_name=product.name,
        unit=sorted_lots[0].unit if sorted_lots else product.default_unit,
        total_quantity=sum((lot.quantity for lot in sorted_lots), Decimal("0.000")),
        lot_count=len(sorted_lots),
        stock_status="in_stock" if all_active_lots else "out_of_stock",
        room_summary=_summarize_names(room_names, empty_label="Out of stock"),
        storage_summary=_summarize_names(storage_names, empty_label="No active stock"),
        nearest_expiry_on=min(nearest_expiry_values) if nearest_expiry_values else None,
        near_expiry_lot_count=sum(1 for lot in sorted_lots if _is_near_expiry(lot, days=near_expiry_days)),
        notes=product.notes,
        manual_ingredient_tags=list(product.manual_ingredient_tags or []),
        aliases=[alias.name for alias in product.aliases],
        barcodes=[barcode.value for barcode in product.barcodes],
        is_in_shopping_list=product.id in open_shopping_product_ids,
        enrichment=serialize_product_enrichment_summary(product),
        locations=_product_location_summaries(sorted_lots),
        stock_lots=[_stock_lot_summary(lot, near_expiry_days=near_expiry_days) for lot in sorted_lots],
    )


def build_pantry_overview(
    db: Session,
    *,
    access: HouseholdAccess,
    filters: PantryFilterOptions,
    page: int = 1,
    page_size: int = 25,
    near_expiry_days: int = 14,
) -> PantryOverviewResponse:
    location_groups, locations, products = _load_reference_lists(db, household_id=access.household.id)
    active_lots = _load_active_lots(db, household_id=access.household.id)
    lots_by_product_id: dict = defaultdict(list)
    for lot in active_lots:
        lots_by_product_id[lot.product_id].append(lot)

    has_lot_scope_filters = bool(
        filters.location_group_external_id or filters.location_external_id or filters.near_expiry_only
    )
    open_shopping_product_ids = list_open_shopping_product_ids(db, household=access.household)

    product_summaries: list[PantryProductSummary] = []
    filtered_lots: list[StockLot] = []
    for product in products:
        if not _matches_product_query(product, query=filters.q):
            continue

        product_active_lots = lots_by_product_id.get(product.id, [])
        product_visible_lots = [
            lot
            for lot in product_active_lots
            if _matches_lot_scope(lot, filters=filters, near_expiry_days=near_expiry_days)
        ]
        if has_lot_scope_filters and not product_visible_lots:
            continue

        visible_lots = product_visible_lots if has_lot_scope_filters else list(product_active_lots)
        filtered_lots.extend(visible_lots)
        product_summaries.append(
            _build_product_summary(
                product=product,
                visible_lots=visible_lots,
                all_active_lots=list(product_active_lots),
                open_shopping_product_ids=open_shopping_product_ids,
                near_expiry_days=near_expiry_days,
            )
        )

    product_summaries.sort(
        key=lambda item: (
            item.stock_status != "in_stock",
            item.product_name.lower(),
        )
    )
    matched_product_count = len(product_summaries)
    page_count = max(1, (matched_product_count + page_size - 1) // page_size)
    current_page = min(page, page_count)
    page_start = (current_page - 1) * page_size
    paginated_products = product_summaries[page_start : page_start + page_size]

    recent_events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.household_id == access.household.id)
        .options(selectinload(AuditEvent.actor_user))
        .order_by(AuditEvent.occurred_at.desc())
        .limit(40)
    ).all()

    return PantryOverviewResponse(
        household_external_id=access.household.external_id,
        household_name=access.household.name,
        effective_role=access.effective_role,
        can_administer=access.can_administer,
        page=current_page,
        page_size=page_size,
        page_count=page_count,
        matched_product_count=matched_product_count,
        filters=PantryFilters(
            q=filters.q,
            location_group_external_id=filters.location_group_external_id,
            location_external_id=filters.location_external_id,
            near_expiry_only=filters.near_expiry_only,
        ),
        counts=PantryCounts(
            location_group_count=len(location_groups),
            location_count=len(locations),
            product_count=len(products),
            active_lot_count=len(active_lots),
            near_expiry_lot_count=sum(1 for lot in active_lots if _is_near_expiry(lot, days=near_expiry_days)),
            out_of_stock_product_count=sum(1 for product in products if not lots_by_product_id.get(product.id)),
        ),
        location_groups=[
            LocationGroupSummary(
                external_id=group.external_id,
                name=group.name,
                location_count=sum(1 for location in locations if location.location_group_id == group.id),
            )
            for group in location_groups
        ],
        locations=[
            LocationSummary(
                external_id=location.external_id,
                name=location.name,
                location_group_external_id=location.location_group.external_id,
                location_group_name=location.location_group.name,
                **serialize_location_link(db, location=location),
            )
            for location in locations
        ],
        catalog_products=[
            {
                "external_id": product.external_id,
                "name": product.name,
                "default_unit": product.default_unit,
                "aliases": [alias.name for alias in product.aliases],
                "barcodes": [barcode.value for barcode in product.barcodes],
                "notes": product.notes,
                "manual_ingredient_tags": list(product.manual_ingredient_tags or []),
                "enrichment": serialize_product_enrichment_summary(product),
            }
            for product in products
        ],
        products=paginated_products,
        stock_lots=[
            _stock_lot_summary(lot, near_expiry_days=near_expiry_days)
            for lot in sorted(
                filtered_lots,
                key=lambda lot: (
                    lot.expires_on is None,
                    lot.expires_on or date.max,
                    lot.product.name.lower(),
                    lot.location.location_group.name.lower(),
                    lot.location.name.lower(),
                ),
            )
        ],
        recent_events=[_event_summary(event) for event in recent_events],
    )


def build_near_expiry_response(
    db: Session,
    *,
    access: HouseholdAccess,
    days: int,
) -> NearExpiryResponse:
    active_lots = _load_active_lots(db, household_id=access.household.id)
    near_expiry_lots = [lot for lot in active_lots if _is_near_expiry(lot, days=days)]
    near_expiry_lots.sort(
        key=lambda lot: (
            lot.expires_on or date.max,
            lot.product.name.lower(),
            lot.location.location_group.name.lower(),
            lot.location.name.lower(),
        )
    )

    return NearExpiryResponse(
        household_external_id=access.household.external_id,
        days=days,
        lots=[_stock_lot_summary(lot, near_expiry_days=days) for lot in near_expiry_lots],
    )
