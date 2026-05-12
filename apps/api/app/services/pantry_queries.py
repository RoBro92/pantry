from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import case, distinct, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.audit_event import AuditEvent
from app.models.barcode import Barcode
from app.models.location import Location
from app.models.location_group import LocationGroup
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.models.product_canonical_link import ProductCanonicalLink
from app.models.stock_lot import StockLot
from app.schemas.pantry import (
    AuditEventSummary,
    LocationGroupSummary,
    LocationSummary,
    NearExpiryResponse,
    PantryCounts,
    PantryFilters,
    PantryItemListResponse,
    PantryLocationOptionsResponse,
    PantryOverviewResponse,
    PantryProductOptionSummary,
    PantryProductOptionsResponse,
    PantryProductSummary,
    PantrySupportDataResponse,
    ProductLocationSummary,
    StockLotSummary,
)
from app.services import location_links
from app.services.canonical_knowledge import serialize_product_canonical_summary
from app.services.pantry_normalization import normalize_barcode, normalize_lookup_name
from app.services.pantry_serialization import (
    serialize_product_enrichment_summary,
    serialize_product_intelligence_summary,
)
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
    elif action == "product.intelligence.classified":
        summary = f"Updated AI product intelligence for {metadata['product_name']}"
    elif action == "product.intelligence.run.completed":
        summary = f"Ran AI product classification for {metadata['classified_count']} product(s)"
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
        .options(
            selectinload(Product.aliases),
            selectinload(Product.barcodes),
            selectinload(Product.enrichments),
            selectinload(Product.intelligence_records),
            selectinload(Product.canonical_link).selectinload(ProductCanonicalLink.canonical_item),
        )
        .order_by(Product.name)
    ).all()
    return location_groups, locations, products


def _load_location_groups(db: Session, *, household_id) -> list[LocationGroup]:
    return db.scalars(
        select(LocationGroup).where(LocationGroup.household_id == household_id).order_by(LocationGroup.name)
    ).all()


def _load_locations(db: Session, *, household_id) -> list[Location]:
    return db.scalars(
        select(Location)
        .where(Location.household_id == household_id)
        .options(selectinload(Location.location_group))
        .order_by(Location.name)
    ).all()


def _location_group_summaries(
    location_groups: list[LocationGroup],
    locations: list[Location],
) -> list[LocationGroupSummary]:
    return [
        LocationGroupSummary(
            external_id=group.external_id,
            name=group.name,
            location_count=sum(1 for location in locations if location.location_group_id == group.id),
        )
        for group in location_groups
    ]


def _serialize_location_link(*, location: Location, public_base_url: str) -> dict[str, str]:
    location_route = location.external_id
    browser_path = location_links.build_location_browser_path(location_route)
    return {
        "location_route": location_route,
        "browser_path": browser_path,
        "browser_url": f"{public_base_url}{browser_path}",
    }


def _location_summaries(
    locations: list[Location],
    *,
    public_base_url: str,
) -> list[LocationSummary]:
    return [
        LocationSummary(
            external_id=location.external_id,
            name=location.name,
            location_group_external_id=location.location_group.external_id,
            location_group_name=location.location_group.name,
            **_serialize_location_link(location=location, public_base_url=public_base_url),
        )
        for location in locations
    ]


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
            selectinload(StockLot.product).selectinload(Product.intelligence_records),
            selectinload(StockLot.product).selectinload(Product.canonical_link).selectinload(ProductCanonicalLink.canonical_item),
            selectinload(StockLot.location).selectinload(Location.location_group),
        )
        .order_by(StockLot.expires_on, StockLot.created_at)
    ).all()


def _active_lot_exists_for_product(product_id_column, *, household_id):
    return exists(
        select(StockLot.id)
        .where(StockLot.household_id == household_id)
        .where(StockLot.product_id == product_id_column)
        .where(StockLot.depleted_at.is_(None))
        .where(StockLot.quantity > Decimal("0"))
    )


def _lot_scope_exists_for_product(
    product_id_column,
    *,
    household_id,
    filters: PantryFilterOptions,
    near_expiry_days: int,
):
    scoped_lot = (
        select(StockLot.id)
        .join(Location, Location.id == StockLot.location_id)
        .where(StockLot.household_id == household_id)
        .where(StockLot.product_id == product_id_column)
        .where(StockLot.depleted_at.is_(None))
        .where(StockLot.quantity > Decimal("0"))
    )
    if filters.location_group_external_id:
        scoped_lot = scoped_lot.join(LocationGroup, LocationGroup.id == Location.location_group_id).where(
            LocationGroup.external_id == filters.location_group_external_id
        )
    if filters.location_external_id:
        scoped_lot = scoped_lot.where(Location.external_id == filters.location_external_id)
    if filters.near_expiry_only:
        scoped_lot = scoped_lot.where(StockLot.expires_on.is_not(None)).where(
            StockLot.expires_on <= _today() + timedelta(days=near_expiry_days)
        )
    return exists(scoped_lot)


def _product_matches_query_clause(*, household_id, query: str | None):
    if not query:
        return None

    normalized_query = normalize_lookup_name(query)
    try:
        barcode_query = normalize_barcode(query)
    except ValueError:
        barcode_query = None

    alias_match = exists(
        select(ProductAlias.id)
        .where(ProductAlias.household_id == household_id)
        .where(ProductAlias.product_id == Product.id)
        .where(ProductAlias.normalized_name.contains(normalized_query))
    )
    clauses = [Product.normalized_name.contains(normalized_query), alias_match]
    if barcode_query:
        barcode_match = exists(
            select(Barcode.id)
            .where(Barcode.household_id == household_id)
            .where(Barcode.product_id == Product.id)
            .where(Barcode.normalized_value.contains(barcode_query))
        )
        clauses.append(barcode_match)
    return or_(*clauses)


def _product_filter_query(
    *,
    household_id,
    filters: PantryFilterOptions,
    near_expiry_days: int,
):
    query = select(Product.id).where(Product.household_id == household_id)
    query_clause = _product_matches_query_clause(household_id=household_id, query=filters.q)
    if query_clause is not None:
        query = query.where(query_clause)

    has_lot_scope_filters = bool(
        filters.location_group_external_id or filters.location_external_id or filters.near_expiry_only
    )
    if has_lot_scope_filters:
        query = query.where(
            _lot_scope_exists_for_product(
                Product.id,
                household_id=household_id,
                filters=filters,
                near_expiry_days=near_expiry_days,
            )
        )

    has_active_lots = _active_lot_exists_for_product(Product.id, household_id=household_id)
    return query.order_by(case((has_active_lots, 0), else_=1), func.lower(Product.name))


def _load_products_by_ids(db: Session, *, household_id, product_ids: list) -> list[Product]:
    if not product_ids:
        return []
    products = db.scalars(
        select(Product)
        .where(Product.household_id == household_id)
        .where(Product.id.in_(product_ids))
        .options(
            selectinload(Product.aliases),
            selectinload(Product.barcodes),
            selectinload(Product.enrichments),
            selectinload(Product.intelligence_records),
            selectinload(Product.canonical_link).selectinload(ProductCanonicalLink.canonical_item),
        )
    ).all()
    products_by_id = {product.id: product for product in products}
    return [products_by_id[product_id] for product_id in product_ids if product_id in products_by_id]


def _load_active_lots_for_products(db: Session, *, household_id, product_ids: list) -> list[StockLot]:
    if not product_ids:
        return []
    return db.scalars(
        select(StockLot)
        .where(StockLot.household_id == household_id)
        .where(StockLot.product_id.in_(product_ids))
        .where(StockLot.depleted_at.is_(None))
        .where(StockLot.quantity > Decimal("0"))
        .options(
            selectinload(StockLot.product).selectinload(Product.aliases),
            selectinload(StockLot.product).selectinload(Product.barcodes),
            selectinload(StockLot.product).selectinload(Product.enrichments),
            selectinload(StockLot.product).selectinload(Product.intelligence_records),
            selectinload(StockLot.product)
            .selectinload(Product.canonical_link)
            .selectinload(ProductCanonicalLink.canonical_item),
            selectinload(StockLot.location).selectinload(Location.location_group),
        )
        .order_by(StockLot.expires_on, StockLot.created_at)
    ).all()


def _build_pantry_counts(db: Session, *, household_id, near_expiry_days: int = 14) -> PantryCounts:
    product_count = db.scalar(select(func.count(Product.id)).where(Product.household_id == household_id)) or 0
    active_lot_filters = [
        StockLot.household_id == household_id,
        StockLot.depleted_at.is_(None),
        StockLot.quantity > Decimal("0"),
    ]
    active_lot_count = db.scalar(select(func.count(StockLot.id)).where(*active_lot_filters)) or 0
    near_expiry_lot_count = (
        db.scalar(
            select(func.count(StockLot.id))
            .where(*active_lot_filters)
            .where(StockLot.expires_on.is_not(None))
            .where(StockLot.expires_on <= _today() + timedelta(days=near_expiry_days))
        )
        or 0
    )
    active_product_count = (
        db.scalar(select(func.count(distinct(StockLot.product_id))).where(*active_lot_filters)) or 0
    )
    return PantryCounts(
        location_group_count=db.scalar(
            select(func.count(LocationGroup.id)).where(LocationGroup.household_id == household_id)
        )
        or 0,
        location_count=db.scalar(select(func.count(Location.id)).where(Location.household_id == household_id)) or 0,
        product_count=product_count,
        active_lot_count=active_lot_count,
        near_expiry_lot_count=near_expiry_lot_count,
        out_of_stock_product_count=max(0, product_count - active_product_count),
    )


def _load_recent_events(db: Session, *, household_id, limit: int = 40) -> list[AuditEvent]:
    return db.scalars(
        select(AuditEvent)
        .where(AuditEvent.household_id == household_id)
        .options(selectinload(AuditEvent.actor_user))
        .order_by(AuditEvent.occurred_at.desc())
        .limit(limit)
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
        canonical=serialize_product_canonical_summary(product),
        enrichment=serialize_product_enrichment_summary(product),
        intelligence=serialize_product_intelligence_summary(product),
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

    matched_products: list[tuple[Product, list[StockLot], list[StockLot]]] = []
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
        matched_products.append((product, visible_lots, list(product_active_lots)))

    matched_products.sort(
        key=lambda item: (
            not item[2],
            item[0].name.lower(),
        )
    )
    matched_product_count = len(matched_products)
    page_count = max(1, (matched_product_count + page_size - 1) // page_size)
    current_page = min(page, page_count)
    page_start = (current_page - 1) * page_size
    paginated_products = [
        _build_product_summary(
            product=product,
            visible_lots=visible_lots,
            all_active_lots=product_active_lots,
            open_shopping_product_ids=open_shopping_product_ids,
            near_expiry_days=near_expiry_days,
        )
        for product, visible_lots, product_active_lots in matched_products[page_start : page_start + page_size]
    ]

    recent_events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.household_id == access.household.id)
        .options(selectinload(AuditEvent.actor_user))
        .order_by(AuditEvent.occurred_at.desc())
        .limit(40)
    ).all()
    public_base_url = location_links.resolve_public_base_url(db).effective_value

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
                **_serialize_location_link(location=location, public_base_url=public_base_url),
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
                "intelligence": serialize_product_intelligence_summary(product),
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


def build_pantry_item_list(
    db: Session,
    *,
    access: HouseholdAccess,
    filters: PantryFilterOptions,
    page: int = 1,
    page_size: int = 25,
    near_expiry_days: int = 14,
) -> PantryItemListResponse:
    product_query = _product_filter_query(
        household_id=access.household.id,
        filters=filters,
        near_expiry_days=near_expiry_days,
    )
    product_subquery = product_query.order_by(None).subquery()
    matched_product_count = db.scalar(select(func.count()).select_from(product_subquery)) or 0
    page_count = max(1, (matched_product_count + page_size - 1) // page_size)
    current_page = min(page, page_count)
    product_ids = db.scalars(
        product_query.offset((current_page - 1) * page_size).limit(page_size)
    ).all()
    products = _load_products_by_ids(db, household_id=access.household.id, product_ids=product_ids)
    active_lots = _load_active_lots_for_products(db, household_id=access.household.id, product_ids=product_ids)

    lots_by_product_id: dict = defaultdict(list)
    for lot in active_lots:
        lots_by_product_id[lot.product_id].append(lot)

    has_lot_scope_filters = bool(
        filters.location_group_external_id or filters.location_external_id or filters.near_expiry_only
    )
    open_shopping_product_ids = list_open_shopping_product_ids(db, household=access.household)
    product_summaries = []
    for product in products:
        product_active_lots = lots_by_product_id.get(product.id, [])
        product_visible_lots = [
            lot
            for lot in product_active_lots
            if _matches_lot_scope(lot, filters=filters, near_expiry_days=near_expiry_days)
        ]
        visible_lots = product_visible_lots if has_lot_scope_filters else list(product_active_lots)
        product_summaries.append(
            _build_product_summary(
                product=product,
                visible_lots=visible_lots,
                all_active_lots=product_active_lots,
                open_shopping_product_ids=open_shopping_product_ids,
                near_expiry_days=near_expiry_days,
            )
        )

    return PantryItemListResponse(
        household_external_id=access.household.external_id,
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
        products=product_summaries,
    )


def build_pantry_support_data(
    db: Session,
    *,
    access: HouseholdAccess,
    near_expiry_days: int = 14,
) -> PantrySupportDataResponse:
    location_groups = _load_location_groups(db, household_id=access.household.id)
    locations = _load_locations(db, household_id=access.household.id)
    public_base_url = location_links.resolve_public_base_url(db).effective_value
    return PantrySupportDataResponse(
        household_external_id=access.household.external_id,
        household_name=access.household.name,
        effective_role=access.effective_role,
        can_administer=access.can_administer,
        counts=_build_pantry_counts(db, household_id=access.household.id, near_expiry_days=near_expiry_days),
        location_groups=_location_group_summaries(location_groups, locations),
        locations=_location_summaries(locations, public_base_url=public_base_url),
        recent_events=[_event_summary(event) for event in _load_recent_events(db, household_id=access.household.id)],
    )


def build_pantry_location_options(
    db: Session,
    *,
    access: HouseholdAccess,
) -> PantryLocationOptionsResponse:
    locations = _load_locations(db, household_id=access.household.id)
    public_base_url = location_links.resolve_public_base_url(db).effective_value
    return PantryLocationOptionsResponse(
        household_external_id=access.household.external_id,
        can_administer=access.can_administer,
        locations=_location_summaries(locations, public_base_url=public_base_url),
    )


def build_pantry_product_options(
    db: Session,
    *,
    access: HouseholdAccess,
) -> PantryProductOptionsResponse:
    products = db.scalars(
        select(Product)
        .where(Product.household_id == access.household.id)
        .options(
            selectinload(Product.aliases),
            selectinload(Product.barcodes),
            selectinload(Product.intelligence_records),
        )
        .order_by(Product.name)
    ).all()
    return PantryProductOptionsResponse(
        household_external_id=access.household.external_id,
        products=[
            PantryProductOptionSummary(
                external_id=product.external_id,
                name=product.name,
                default_unit=product.default_unit,
                aliases=[alias.name for alias in product.aliases],
                barcodes=[barcode.value for barcode in product.barcodes],
                intelligence_ingredient_families=list(
                    product.intelligence_records[0].ingredient_families or []
                )
                if product.intelligence_records
                else [],
                intelligence_food_category=(
                    product.intelligence_records[0].food_category if product.intelligence_records else None
                ),
            )
            for product in products
        ],
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
