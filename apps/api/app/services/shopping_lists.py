from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from app.models.base import utc_now
from app.models.household import Household
from app.models.location import Location
from app.models.product import Product
from app.models.shopping_list import ShoppingList
from app.models.shopping_list_item import ShoppingListItem
from app.models.stock_lot import StockLot
from app.models.user import User
from app.schemas.shopping import (
    ShoppingListDetailSummary,
    ShoppingListItemSummary,
    ShoppingListSummary,
)
from app.services.audit import record_audit_event
from app.services.pantry_catalog import get_location_by_external_id, get_product_by_external_id
from app.services.pantry_normalization import (
    lookup_token_signature,
    normalize_lookup_name,
    normalize_unit,
    require_text,
)
from app.services.pantry_stock import add_stock_lot

DEFAULT_SHOPPING_LIST_NAME = "Shopping list"

SHOPPING_LIST_STATE_ACTIVE = "active"
SHOPPING_LIST_STATE_AWAITING_PURCHASE = "awaiting_purchase"
SHOPPING_LIST_STATE_RECONCILED = "reconciled"
SHOPPING_LIST_STATE_RETURNED = "returned"
SHOPPING_LIST_STATE_MERGED = "merged"

SHOPPING_ITEM_STATUS_OPEN = "open"
SHOPPING_ITEM_STATUS_AWAITING_PURCHASE = "awaiting_purchase"
SHOPPING_ITEM_STATUS_PURCHASED = "purchased"
SHOPPING_ITEM_STATUS_NOT_PURCHASED = "not_purchased"

BULK_PENDING_ACTION_RECONCILE = "reconcile_selected"
BULK_PENDING_ACTION_RETURN = "return_selected"
BULK_PENDING_ACTION_DELETE = "delete_selected"
FINALIZE_UNRESOLVED_ACTION_RETURN = "return_to_active"
FINALIZE_UNRESOLVED_ACTION_DELETE = "delete"

ACTIVE_LIST_STATES = {SHOPPING_LIST_STATE_ACTIVE}
PENDING_LIST_STATES = {SHOPPING_LIST_STATE_AWAITING_PURCHASE}
HISTORY_LIST_STATES = {
    SHOPPING_LIST_STATE_RECONCILED,
    SHOPPING_LIST_STATE_RETURNED,
    SHOPPING_LIST_STATE_MERGED,
}


def _normalize_quantity(quantity: Decimal | None) -> Decimal | None:
    if quantity is None:
        return None
    if quantity <= Decimal("0"):
        raise ValueError("Shopping list quantity must be greater than zero.")
    return quantity.quantize(Decimal("0.001"))


def _list_name_timestamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _sort_list_timestamp(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _format_quantity(quantity: Decimal | None, unit: str | None) -> str | None:
    if quantity is None:
        return None
    formatted_quantity = format(quantity, "f").rstrip("0").rstrip(".")
    if not formatted_quantity:
        formatted_quantity = "0"
    if unit:
        return f"{formatted_quantity} {unit}"
    return formatted_quantity


def _same_requested_unit(item: ShoppingListItem, unit: str | None) -> bool:
    return bool(item.requested_unit and unit and item.requested_unit == unit)


def _requested_quantity(item: ShoppingListItem) -> Decimal | None:
    return item.requested_quantity if item.requested_quantity is not None else item.quantity


def _requested_unit(item: ShoppingListItem) -> str | None:
    return item.requested_unit if item.requested_unit is not None else item.unit


def _item_label_key(label: str) -> str:
    signature = lookup_token_signature(label)
    if len(signature) >= 2:
        return "|".join(signature)
    return normalize_lookup_name(label)


def _item_identity_key(item: ShoppingListItem) -> tuple[str, str]:
    if item.product_id is not None:
        return ("product", str(item.product_id))
    return ("label", _item_label_key(item.label))


def _incoming_identity_key(*, product: Product | None, label: str) -> tuple[str, str]:
    if product is not None:
        return ("product", str(product.id))
    return ("label", _item_label_key(label))


def _append_note(existing_note: str | None, next_note: str | None) -> str | None:
    if not next_note:
        return existing_note
    if not existing_note:
        return next_note
    if next_note.casefold() in existing_note.casefold():
        return existing_note
    combined = f"{existing_note}; {next_note}"
    return combined[:512]


def _merge_item_fields(
    item: ShoppingListItem,
    *,
    quantity: Decimal | None,
    unit: str | None,
    note: str | None,
) -> None:
    if quantity is not None:
        if item.quantity is None:
            item.quantity = quantity
        elif item.unit and unit and item.unit != unit:
            item.note = _append_note(
                item.note,
                f"Additional amount requested: {_format_quantity(quantity, unit)}",
            )
        else:
            item.quantity = (item.quantity + quantity).quantize(Decimal("0.001"))

    if unit and not item.unit:
        item.unit = unit
    if note:
        item.note = _append_note(item.note, note)


def _serialize_item(item: ShoppingListItem) -> ShoppingListItemSummary:
    return ShoppingListItemSummary(
        external_id=item.external_id,
        label=item.label,
        product_external_id=item.product.external_id if item.product is not None else None,
        product_name=item.product.name if item.product is not None else None,
        quantity=item.quantity,
        requested_quantity=item.requested_quantity,
        unit=item.unit,
        requested_unit=item.requested_unit,
        note=item.note,
        pantry_location_external_id=item.pantry_location.external_id if item.pantry_location is not None else None,
        pantry_location_name=item.pantry_location.name if item.pantry_location is not None else None,
        pantry_location_group_name=(
            item.pantry_location.location_group.name if item.pantry_location is not None else None
        ),
        source_type=item.source_type,
        status=item.status,
        created_at=item.created_at,
        completed_at=item.completed_at,
        purchased_at=item.purchased_at,
        not_purchased_at=item.not_purchased_at,
    )


def _item_sort_key(item: ShoppingListItem) -> tuple[int, datetime]:
    status_rank = {
        SHOPPING_ITEM_STATUS_OPEN: 0,
        SHOPPING_ITEM_STATUS_AWAITING_PURCHASE: 0,
        SHOPPING_ITEM_STATUS_NOT_PURCHASED: 1,
        SHOPPING_ITEM_STATUS_PURCHASED: 2,
    }
    return (status_rank.get(item.status, 99), item.created_at)


def _serialize_list(shopping_list: ShoppingList) -> ShoppingListDetailSummary:
    sorted_items = sorted(shopping_list.items, key=_item_sort_key)
    unresolved_statuses = {SHOPPING_ITEM_STATUS_OPEN, SHOPPING_ITEM_STATUS_AWAITING_PURCHASE}
    return ShoppingListDetailSummary(
        external_id=shopping_list.external_id,
        name=shopping_list.name,
        lifecycle_state=shopping_list.lifecycle_state,
        item_count=len(sorted_items),
        unresolved_item_count=sum(1 for item in sorted_items if item.status in unresolved_statuses),
        purchased_item_count=sum(1 for item in sorted_items if item.status == SHOPPING_ITEM_STATUS_PURCHASED),
        not_purchased_item_count=sum(
            1 for item in sorted_items if item.status == SHOPPING_ITEM_STATUS_NOT_PURCHASED
        ),
        generated_at=shopping_list.generated_at,
        reconciled_at=shopping_list.reconciled_at,
        merged_into_list_external_id=shopping_list.merged_into_list.external_id
        if shopping_list.merged_into_list is not None
        else None,
        items=[_serialize_item(item) for item in sorted_items],
    )


def _load_shopping_list(
    db: Session,
    *,
    household: Household,
    external_id: str,
) -> ShoppingList | None:
    return db.scalar(
        select(ShoppingList)
        .where(ShoppingList.household_id == household.id)
        .where(ShoppingList.external_id == external_id)
        .options(
            selectinload(ShoppingList.items).selectinload(ShoppingListItem.product),
            selectinload(ShoppingList.items).selectinload(ShoppingListItem.pantry_location).selectinload(Location.location_group),
            selectinload(ShoppingList.merged_into_list),
        )
    )


def _load_all_lists(db: Session, *, household: Household) -> list[ShoppingList]:
    return db.scalars(
        select(ShoppingList)
        .where(ShoppingList.household_id == household.id)
        .options(
            selectinload(ShoppingList.items).selectinload(ShoppingListItem.product),
            selectinload(ShoppingList.items).selectinload(ShoppingListItem.pantry_location).selectinload(Location.location_group),
            selectinload(ShoppingList.merged_into_list),
        )
        .order_by(ShoppingList.updated_at.desc(), ShoppingList.created_at.desc())
    ).all()


def _build_trip_name(at: datetime) -> str:
    return f"Shopping trip {_list_name_timestamp(at)}"


def _build_unique_list_name(
    db: Session,
    *,
    household: Household,
    base_name: str,
    exclude_list_id: object | None = None,
) -> str:
    candidate = require_text(base_name, field_name="Shopping list name")
    suffix = 2
    while True:
        normalized_candidate = normalize_lookup_name(candidate)
        statement = (
            select(ShoppingList.id)
            .where(ShoppingList.household_id == household.id)
            .where(ShoppingList.normalized_name == normalized_candidate)
        )
        if exclude_list_id is not None:
            statement = statement.where(ShoppingList.id != exclude_list_id)
        existing = db.scalar(statement)
        if existing is None:
            return candidate
        candidate = f"{base_name} ({suffix})"
        suffix += 1


def get_or_create_active_shopping_list(
    db: Session,
    *,
    household: Household,
    commit: bool = False,
) -> ShoppingList:
    shopping_list = db.scalar(
        select(ShoppingList)
        .where(ShoppingList.household_id == household.id)
        .where(ShoppingList.is_default.is_(True))
        .where(ShoppingList.lifecycle_state == SHOPPING_LIST_STATE_ACTIVE)
        .options(selectinload(ShoppingList.items).selectinload(ShoppingListItem.product))
        .options(selectinload(ShoppingList.items).selectinload(ShoppingListItem.pantry_location).selectinload(Location.location_group))
    )
    if shopping_list is not None:
        return shopping_list

    shopping_list = ShoppingList(
        household_id=household.id,
        name=DEFAULT_SHOPPING_LIST_NAME,
        normalized_name=normalize_lookup_name(DEFAULT_SHOPPING_LIST_NAME),
        is_default=True,
        lifecycle_state=SHOPPING_LIST_STATE_ACTIVE,
    )
    db.add(shopping_list)
    db.flush()
    if commit:
        db.commit()
        db.refresh(shopping_list)
        return _load_shopping_list(db, household=household, external_id=shopping_list.external_id) or shopping_list
    return shopping_list


def get_shopping_list_item_by_external_id(
    db: Session,
    *,
    household: Household,
    item_external_id: str,
) -> ShoppingListItem | None:
    return db.scalar(
        select(ShoppingListItem)
        .where(ShoppingListItem.household_id == household.id)
        .where(ShoppingListItem.external_id == item_external_id)
        .options(
            selectinload(ShoppingListItem.product),
            selectinload(ShoppingListItem.pantry_location).selectinload(Location.location_group),
            selectinload(ShoppingListItem.shopping_list).selectinload(ShoppingList.items),
        )
    )


def _resolve_default_pantry_location(
    db: Session,
    *,
    household: Household,
    product: Product | None,
    explicit_location_external_id: str | None = None,
) -> Location | None:
    if explicit_location_external_id:
        location = get_location_by_external_id(
            db,
            household=household,
            external_id=explicit_location_external_id,
        )
        if location is None:
            raise ValueError("Storage location not found.")
        return location

    if product is None:
        return None

    return db.scalar(
        select(Location)
        .join(StockLot, StockLot.location_id == Location.id)
        .where(StockLot.household_id == household.id)
        .where(StockLot.product_id == product.id)
        .order_by(
            case((StockLot.depleted_at.is_(None), 0), else_=1),
            StockLot.updated_at.desc(),
            StockLot.created_at.desc(),
        )
    )


def list_open_shopping_product_ids(db: Session, *, household: Household) -> set:
    product_ids = db.scalars(
        select(ShoppingListItem.product_id)
        .join(ShoppingList, ShoppingListItem.shopping_list_id == ShoppingList.id)
        .where(ShoppingListItem.household_id == household.id)
        .where(ShoppingList.lifecycle_state.in_(ACTIVE_LIST_STATES | PENDING_LIST_STATES))
        .where(
            ShoppingListItem.status.in_(
                [
                    SHOPPING_ITEM_STATUS_OPEN,
                    SHOPPING_ITEM_STATUS_AWAITING_PURCHASE,
                    SHOPPING_ITEM_STATUS_NOT_PURCHASED,
                ]
            )
        )
        .where(ShoppingListItem.product_id.is_not(None))
    ).all()
    return {product_id for product_id in product_ids if product_id is not None}


def _merge_item_into_list(
    db: Session,
    *,
    shopping_list: ShoppingList,
    household: Household,
    existing_items: list[ShoppingListItem],
    product: Product | None,
    label: str,
    quantity: Decimal | None,
    unit: str | None,
    note: str | None,
    pantry_location: Location | None,
    source_type: str,
    status: str,
) -> ShoppingListItem:
    incoming_key = _incoming_identity_key(product=product, label=label)
    existing_item = next(
        (
            item
            for item in existing_items
            if item.status == status and _item_identity_key(item) == incoming_key
        ),
        None,
    )
    if existing_item is not None:
        _merge_item_fields(existing_item, quantity=quantity, unit=unit, note=note)
        if pantry_location is not None and existing_item.pantry_location_id is None:
            existing_item.pantry_location_id = pantry_location.id
            existing_item.pantry_location = pantry_location
        db.add(existing_item)
        return existing_item

    item = ShoppingListItem(
        household_id=household.id,
        shopping_list_id=shopping_list.id,
        product_id=product.id if product is not None else None,
        label=label,
        normalized_label=normalize_lookup_name(label),
        quantity=quantity,
        unit=unit,
        note=note,
        pantry_location_id=pantry_location.id if pantry_location is not None else None,
        source_type=source_type,
        status=status,
        requested_quantity=quantity,
        requested_unit=unit,
    )
    db.add(item)
    db.flush()
    if product is not None:
        item.product = product
    if pantry_location is not None:
        item.pantry_location = pantry_location
    existing_items.append(item)
    return item


def build_household_shopping_list(
    db: Session,
    *,
    household: Household,
    history_limit: int = 6,
) -> ShoppingListSummary:
    active_list = get_or_create_active_shopping_list(db, household=household, commit=True)
    lists = _load_all_lists(db, household=household)

    active = next(
        (
            shopping_list
            for shopping_list in lists
            if shopping_list.external_id == active_list.external_id
        ),
        active_list,
    )
    pending_lists = [
        shopping_list
        for shopping_list in lists
        if shopping_list.lifecycle_state in PENDING_LIST_STATES
    ]
    history_lists = [
        shopping_list
        for shopping_list in lists
        if shopping_list.lifecycle_state in HISTORY_LIST_STATES
    ]

    pending_lists.sort(
        key=lambda shopping_list: _sort_list_timestamp(shopping_list.generated_at or shopping_list.updated_at),
        reverse=True,
    )
    history_lists.sort(
        key=lambda shopping_list: _sort_list_timestamp(shopping_list.reconciled_at or shopping_list.updated_at),
        reverse=True,
    )

    return ShoppingListSummary(
        household_external_id=household.external_id,
        household_name=household.name,
        active_list=_serialize_list(active),
        pending_lists=[_serialize_list(shopping_list) for shopping_list in pending_lists],
        history_lists=[_serialize_list(shopping_list) for shopping_list in history_lists[:history_limit]],
    )


def add_item_to_default_shopping_list(
    db: Session,
    *,
    household: Household,
    actor: User,
    product_external_id: str | None = None,
    label: str | None = None,
    quantity: Decimal | None = None,
    unit: str | None = None,
    note: str | None = None,
    pantry_location_external_id: str | None = None,
    source_type: str = "manual",
) -> ShoppingListItem:
    shopping_list = get_or_create_active_shopping_list(db, household=household)

    product: Product | None = None
    item_label = label
    item_unit = unit
    if product_external_id:
        product = get_product_by_external_id(db, household=household, external_id=product_external_id)
        if product is None:
            raise ValueError("Product not found.")
        item_label = product.name
        item_unit = unit or product.default_unit

    display_label = require_text(item_label or "", field_name="Shopping list item")
    normalized_note = require_text(note, field_name="Note") if note else None
    normalized_quantity = _normalize_quantity(quantity)
    normalized_unit = normalize_unit(item_unit) if item_unit else None
    pantry_location = _resolve_default_pantry_location(
        db,
        household=household,
        product=product,
        explicit_location_external_id=pantry_location_external_id,
    )

    item = _merge_item_into_list(
        db,
        shopping_list=shopping_list,
        household=household,
        existing_items=list(shopping_list.items),
        product=product,
        label=display_label,
        quantity=normalized_quantity,
        unit=normalized_unit,
        note=normalized_note,
        pantry_location=pantry_location,
        source_type=source_type,
        status=SHOPPING_ITEM_STATUS_OPEN,
    )

    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="shopping_list.item_added",
        target_type="shopping_list_item",
        target_external_id=item.external_id,
        event_metadata={
            "label": display_label,
            "product_name": product.name if product is not None else None,
            "source_type": source_type,
            "quantity": str(item.quantity) if item.quantity is not None else None,
            "unit": item.unit,
        },
    )
    db.commit()
    db.expire_all()
    db.refresh(item)
    return get_shopping_list_item_by_external_id(db, household=household, item_external_id=item.external_id) or item


def update_shopping_list_item(
    db: Session,
    *,
    household: Household,
    actor: User,
    item_external_id: str,
    status: str | None = None,
    quantity: Decimal | None = None,
    unit: str | None = None,
    note: str | None = None,
    pantry_location_external_id: str | None = None,
) -> ShoppingListItem:
    item = get_shopping_list_item_by_external_id(db, household=household, item_external_id=item_external_id)
    if item is None or item.shopping_list is None:
        raise ValueError("Shopping list item not found.")
    pending_list = (
        item.shopping_list
        if item.shopping_list.lifecycle_state == SHOPPING_LIST_STATE_AWAITING_PURCHASE
        else None
    )

    normalized_quantity = _normalize_quantity(quantity) if quantity is not None else None
    normalized_unit = normalize_unit(unit) if unit else None
    normalized_note = require_text(note, field_name="Note") if note else None
    pantry_location = (
        _resolve_default_pantry_location(
            db,
            household=household,
            product=item.product,
            explicit_location_external_id=pantry_location_external_id,
        )
        if pantry_location_external_id is not None
        else None
    )

    if normalized_quantity is not None:
        item.quantity = normalized_quantity
        if item.shopping_list.lifecycle_state == SHOPPING_LIST_STATE_ACTIVE:
            item.requested_quantity = normalized_quantity
    if unit is not None:
        item.unit = normalized_unit
        if item.shopping_list.lifecycle_state == SHOPPING_LIST_STATE_ACTIVE:
            item.requested_unit = normalized_unit
    if note is not None:
        item.note = normalized_note
    if pantry_location_external_id is not None:
        item.pantry_location_id = pantry_location.id if pantry_location is not None else None
        item.pantry_location = pantry_location

    if status is not None:
        valid_statuses = (
            {SHOPPING_ITEM_STATUS_OPEN}
            if item.shopping_list.lifecycle_state == SHOPPING_LIST_STATE_ACTIVE
            else {
                SHOPPING_ITEM_STATUS_AWAITING_PURCHASE,
                SHOPPING_ITEM_STATUS_PURCHASED,
                SHOPPING_ITEM_STATUS_NOT_PURCHASED,
            }
        )
        if status not in valid_statuses:
            raise ValueError("That item status is not valid for this shopping list.")
        item.status = status
        item.completed_at = utc_now() if status == SHOPPING_ITEM_STATUS_PURCHASED else None
        item.purchased_at = utc_now() if status == SHOPPING_ITEM_STATUS_PURCHASED else None
        item.not_purchased_at = utc_now() if status == SHOPPING_ITEM_STATUS_NOT_PURCHASED else None
        item.reconciled_at = None
        if status in {SHOPPING_ITEM_STATUS_OPEN, SHOPPING_ITEM_STATUS_AWAITING_PURCHASE}:
            item.completed_at = None
            item.purchased_at = None
            item.not_purchased_at = None
            item.reconciled_at = None
    elif (
        item.shopping_list.lifecycle_state == SHOPPING_LIST_STATE_AWAITING_PURCHASE
        and normalized_quantity is not None
        and item.requested_quantity is not None
        and _same_requested_unit(item, normalized_unit or item.unit)
        and normalized_quantity == item.requested_quantity
    ):
        item.status = SHOPPING_ITEM_STATUS_PURCHASED
        item.completed_at = utc_now()
        item.purchased_at = item.completed_at
        item.not_purchased_at = None
        item.reconciled_at = None

    db.add(item)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="shopping_list.item_updated",
        target_type="shopping_list_item",
        target_external_id=item.external_id,
        event_metadata={
            "label": item.label,
            "product_name": item.product.name if item.product is not None else None,
            "status": item.status,
            "quantity": str(item.quantity) if item.quantity is not None else None,
            "unit": item.unit,
        },
    )
    if pending_list is not None and all(
        candidate.status != SHOPPING_ITEM_STATUS_AWAITING_PURCHASE
        for candidate in pending_list.items
    ):
        _finalize_pending_shopping_list_record(
            db,
            household=household,
            actor=actor,
            pending_list=pending_list,
            return_shortfalls_to_active=True,
        )
        return get_shopping_list_item_by_external_id(db, household=household, item_external_id=item.external_id) or item

    db.commit()
    db.refresh(item)
    return get_shopping_list_item_by_external_id(db, household=household, item_external_id=item.external_id) or item


def delete_shopping_list_item(
    db: Session,
    *,
    household: Household,
    actor: User,
    item_external_id: str,
) -> None:
    item = get_shopping_list_item_by_external_id(db, household=household, item_external_id=item_external_id)
    if item is None or item.shopping_list is None:
        raise ValueError("Shopping list item not found.")
    if item.shopping_list.lifecycle_state != SHOPPING_LIST_STATE_ACTIVE:
        raise ValueError("Only active shopping list items can be removed.")

    label = item.label
    product_name = item.product.name if item.product is not None else None
    external_id = item.external_id
    if item.shopping_list is not None and item in item.shopping_list.items:
        item.shopping_list.items.remove(item)
    db.delete(item)
    db.flush()
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="shopping_list.item_removed",
        target_type="shopping_list_item",
        target_external_id=external_id,
        event_metadata={
            "label": label,
            "product_name": product_name,
        },
    )
    db.commit()


def complete_shopping_list_item(
    db: Session,
    *,
    household: Household,
    actor: User,
    item_external_id: str,
    status: str = SHOPPING_ITEM_STATUS_PURCHASED,
) -> ShoppingListItem:
    if status == "completed":
        status = SHOPPING_ITEM_STATUS_PURCHASED
    if status == SHOPPING_ITEM_STATUS_OPEN:
        return update_shopping_list_item(
            db,
            household=household,
            actor=actor,
            item_external_id=item_external_id,
            status=SHOPPING_ITEM_STATUS_OPEN,
        )
    return update_shopping_list_item(
        db,
        household=household,
        actor=actor,
        item_external_id=item_external_id,
        status=status,
    )


def attach_product_to_shopping_list_item(
    db: Session,
    *,
    household: Household,
    actor: User,
    item_external_id: str,
    product_external_id: str,
) -> ShoppingListItem:
    item = get_shopping_list_item_by_external_id(db, household=household, item_external_id=item_external_id)
    if item is None:
        raise ValueError("Shopping list item not found.")

    product = get_product_by_external_id(db, household=household, external_id=product_external_id)
    if product is None:
        raise ValueError("Product not found.")

    item.product_id = product.id
    item.product = product
    item.label = product.name
    item.normalized_label = normalize_lookup_name(product.name)
    if item.unit is None:
        item.unit = product.default_unit
    if item.requested_unit is None:
        item.requested_unit = item.unit or product.default_unit
    if item.pantry_location_id is None:
        pantry_location = _resolve_default_pantry_location(db, household=household, product=product)
        if pantry_location is not None:
            item.pantry_location_id = pantry_location.id
            item.pantry_location = pantry_location
    db.add(item)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="shopping_list.item_linked_product",
        target_type="shopping_list_item",
        target_external_id=item.external_id,
        event_metadata={
            "label": item.label,
            "product_name": product.name,
        },
    )
    db.commit()
    db.refresh(item)
    return get_shopping_list_item_by_external_id(db, household=household, item_external_id=item.external_id) or item


def export_active_shopping_list(
    db: Session,
    *,
    household: Household,
    actor: User,
) -> tuple[ShoppingList, str]:
    active_list = get_or_create_active_shopping_list(db, household=household)
    active_items = [item for item in active_list.items if item.status == SHOPPING_ITEM_STATUS_OPEN]
    if not active_items:
        raise ValueError("Add at least one item before exporting the shopping list.")

    now = utc_now()
    active_list.is_default = False
    active_list.lifecycle_state = SHOPPING_LIST_STATE_AWAITING_PURCHASE
    active_list.generated_at = now
    active_list.name = _build_unique_list_name(
        db,
        household=household,
        base_name=_build_trip_name(now),
        exclude_list_id=active_list.id,
    )
    active_list.normalized_name = normalize_lookup_name(active_list.name)
    for item in active_items:
        item.status = SHOPPING_ITEM_STATUS_AWAITING_PURCHASE
        item.requested_quantity = item.quantity
        item.requested_unit = item.unit
        if item.product is not None and item.pantry_location_id is None:
            pantry_location = _resolve_default_pantry_location(db, household=household, product=item.product)
            if pantry_location is not None:
                item.pantry_location_id = pantry_location.id
                item.pantry_location = pantry_location
        db.add(item)
    db.add(active_list)
    new_active_list = get_or_create_active_shopping_list(db, household=household)

    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="shopping_list.exported",
        target_type="shopping_list",
        target_external_id=active_list.external_id,
        event_metadata={
            "name": active_list.name,
            "item_count": len(active_items),
        },
    )
    db.commit()
    db.refresh(active_list)
    db.refresh(new_active_list)

    exported_lines = [
        "Pantro shopping list",
        f"Household: {household.name}",
        f"Generated: {now.strftime('%d %b %Y %H:%M UTC')}",
        "",
    ]
    for item in sorted(active_items, key=_item_sort_key):
        detail_bits = []
        formatted_quantity = _format_quantity(item.quantity, item.unit)
        if formatted_quantity:
            detail_bits.append(formatted_quantity)
        if item.note:
            detail_bits.append(item.note)
        suffix = f" ({' · '.join(detail_bits)})" if detail_bits else ""
        exported_lines.append(f"[ ] {item.product.name if item.product is not None else item.label}{suffix}")

    refreshed_list = _load_shopping_list(db, household=household, external_id=active_list.external_id) or active_list
    return refreshed_list, "\n".join(exported_lines).strip() + "\n"


def merge_pending_shopping_lists(
    db: Session,
    *,
    household: Household,
    actor: User,
    target_list_external_id: str | None = None,
) -> ShoppingList:
    pending_lists = [
        shopping_list
        for shopping_list in _load_all_lists(db, household=household)
        if shopping_list.lifecycle_state == SHOPPING_LIST_STATE_AWAITING_PURCHASE
    ]
    if len(pending_lists) < 2:
        raise ValueError("Create at least two awaiting-purchase lists before merging.")
    if any(
        any(item.status != SHOPPING_ITEM_STATUS_AWAITING_PURCHASE for item in shopping_list.items)
        for shopping_list in pending_lists
    ):
        raise ValueError("Only unresolved awaiting-purchase lists can be merged right now.")

    if target_list_external_id:
        target_list = next(
            (
                shopping_list
                for shopping_list in pending_lists
                if shopping_list.external_id == target_list_external_id
            ),
            None,
        )
        if target_list is None:
            raise ValueError("Pending shopping list not found.")
    else:
        target_list = max(
            pending_lists,
            key=lambda shopping_list: shopping_list.generated_at or shopping_list.created_at,
        )

    merged_item_count = 0
    target_items = list(target_list.items)
    for source_list in pending_lists:
        if source_list.id == target_list.id:
            continue
        for item in list(source_list.items):
            _merge_item_into_list(
                db,
                shopping_list=target_list,
                household=household,
                existing_items=target_items,
                product=item.product,
                label=item.label,
                quantity=item.quantity,
                unit=item.unit,
                note=item.note,
                pantry_location=item.pantry_location,
                source_type=item.source_type,
                status=SHOPPING_ITEM_STATUS_AWAITING_PURCHASE,
            )
            db.delete(item)
            merged_item_count += 1
        source_list.lifecycle_state = SHOPPING_LIST_STATE_MERGED
        source_list.reconciled_at = utc_now()
        source_list.archived_at = source_list.reconciled_at
        source_list.merged_into_list_id = target_list.id
        db.add(source_list)

    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="shopping_list.pending_merged",
        target_type="shopping_list",
        target_external_id=target_list.external_id,
        event_metadata={
            "name": target_list.name,
            "merged_item_count": merged_item_count,
        },
    )
    db.commit()
    return _load_shopping_list(db, household=household, external_id=target_list.external_id) or target_list


def return_pending_list_to_active(
    db: Session,
    *,
    household: Household,
    actor: User,
    list_external_id: str,
) -> ShoppingList:
    pending_list = _load_shopping_list(db, household=household, external_id=list_external_id)
    if pending_list is None or pending_list.lifecycle_state != SHOPPING_LIST_STATE_AWAITING_PURCHASE:
        raise ValueError("Awaiting-purchase list not found.")

    active_list = get_or_create_active_shopping_list(db, household=household)
    active_items = list(active_list.items)
    returned_item_count = 0
    for item in pending_list.items:
        if item.status not in {
            SHOPPING_ITEM_STATUS_AWAITING_PURCHASE,
            SHOPPING_ITEM_STATUS_NOT_PURCHASED,
        }:
            continue
        _merge_item_into_list(
            db,
            shopping_list=active_list,
            household=household,
            existing_items=active_items,
            product=item.product,
            label=item.label,
            quantity=_requested_quantity(item),
            unit=_requested_unit(item),
            note=item.note,
            pantry_location=item.pantry_location,
            source_type=item.source_type,
            status=SHOPPING_ITEM_STATUS_OPEN,
        )
        item.status = SHOPPING_ITEM_STATUS_NOT_PURCHASED
        item.not_purchased_at = utc_now()
        item.reconciled_at = item.not_purchased_at
        db.add(item)
        returned_item_count += 1

    pending_list.lifecycle_state = SHOPPING_LIST_STATE_RETURNED
    pending_list.reconciled_at = utc_now()
    pending_list.archived_at = pending_list.reconciled_at
    db.add(pending_list)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="shopping_list.returned_to_active",
        target_type="shopping_list",
        target_external_id=pending_list.external_id,
        event_metadata={
            "name": pending_list.name,
            "returned_item_count": returned_item_count,
        },
    )
    db.commit()
    return _load_shopping_list(db, household=household, external_id=pending_list.external_id) or pending_list


def _return_shortfall_to_active_list(
    db: Session,
    *,
    household: Household,
    active_list: ShoppingList,
    active_items: list[ShoppingListItem],
    item: ShoppingListItem,
) -> bool:
    requested_quantity = _requested_quantity(item)
    if (
        requested_quantity is None
        or item.quantity is None
        or item.quantity >= requested_quantity
        or not _same_requested_unit(item, item.unit)
    ):
        return False

    shortfall_quantity = (requested_quantity - item.quantity).quantize(Decimal("0.001"))
    if shortfall_quantity <= Decimal("0.000"):
        return False

    _merge_item_into_list(
        db,
        shopping_list=active_list,
        household=household,
        existing_items=active_items,
        product=item.product,
        label=item.label,
        quantity=shortfall_quantity,
        unit=_requested_unit(item),
        note=item.note,
        pantry_location=item.pantry_location,
        source_type=item.source_type,
        status=SHOPPING_ITEM_STATUS_OPEN,
    )
    return True


def _write_purchased_item_to_pantry(
    db: Session,
    *,
    household: Household,
    actor: User,
    item: ShoppingListItem,
    purchased_on: date,
) -> None:
    if item.product is None:
        raise ValueError(f"Create a product record for {item.label} before finishing reconciliation.")

    quantity = item.quantity or item.requested_quantity or Decimal("1.000")
    unit = item.unit or item.requested_unit or item.product.default_unit
    pantry_location = item.pantry_location or _resolve_default_pantry_location(
        db,
        household=household,
        product=item.product,
    )
    if pantry_location is None:
        raise ValueError(
            f"Choose a storage location for {item.product.name} before finishing reconciliation."
        )

    add_stock_lot(
        db,
        household=household,
        actor=actor,
        product_external_id=item.product.external_id,
        location_external_id=pantry_location.external_id,
        quantity=quantity,
        note=item.note,
        purchased_on=purchased_on,
        expires_on=None,
        unit_override=unit,
        commit=False,
    )


def _normalize_selected_pending_items(
    pending_list: ShoppingList,
    *,
    items: list[dict[str, object]],
) -> list[tuple[ShoppingListItem, dict[str, object]]]:
    if not items:
        raise ValueError("Select at least one shopping item first.")

    items_by_external_id = {item.external_id: item for item in pending_list.items}
    selected_items: list[tuple[ShoppingListItem, dict[str, object]]] = []
    seen_item_ids: set[str] = set()
    for payload in items:
        item_external_id = str(payload.get("item_external_id") or "").strip()
        if not item_external_id or item_external_id in seen_item_ids:
            continue
        item = items_by_external_id.get(item_external_id)
        if item is None:
            raise ValueError("One or more selected shopping items could not be found.")
        if item.status != SHOPPING_ITEM_STATUS_AWAITING_PURCHASE:
            raise ValueError("Only unresolved shopping items can be selected.")
        selected_items.append((item, payload))
        seen_item_ids.add(item_external_id)

    if not selected_items:
        raise ValueError("Select at least one unresolved shopping item first.")
    return selected_items


def _normalize_reconciliation_quantity(item: ShoppingListItem, *, payload: dict[str, object]) -> Decimal:
    raw_quantity = payload.get("quantity")
    if raw_quantity is None:
        raw_quantity = item.requested_quantity or item.quantity or Decimal("1.000")
    return _normalize_quantity(raw_quantity)


def _normalize_reconciliation_unit(item: ShoppingListItem, *, payload: dict[str, object]) -> str:
    raw_unit = payload.get("unit")
    if isinstance(raw_unit, str) and raw_unit.strip():
        normalized_unit = normalize_unit(raw_unit)
    else:
        normalized_unit = normalize_unit(
            item.requested_unit
            or item.unit
            or (item.product.default_unit if item.product is not None else None)
            or "count"
        )
    if not normalized_unit:
        raise ValueError(f"Choose a purchased unit for {item.product.name if item.product is not None else item.label}.")
    return normalized_unit


def _normalize_reconciliation_note(item: ShoppingListItem, *, payload: dict[str, object]) -> str | None:
    if "note" not in payload:
        return item.note
    raw_note = payload.get("note")
    if isinstance(raw_note, str):
        return require_text(raw_note, field_name="Note") if raw_note else None
    if raw_note is None:
        return item.note
    return require_text(str(raw_note), field_name="Note")


def _resolve_reconciliation_location(
    db: Session,
    *,
    household: Household,
    item: ShoppingListItem,
    payload: dict[str, object],
) -> Location | None:
    explicit_location_external_id = payload.get("pantry_location_external_id")
    if isinstance(explicit_location_external_id, str) and not explicit_location_external_id.strip():
        explicit_location_external_id = None
    if explicit_location_external_id is None and item.pantry_location is not None:
        explicit_location_external_id = item.pantry_location.external_id
    return _resolve_default_pantry_location(
        db,
        household=household,
        product=item.product,
        explicit_location_external_id=explicit_location_external_id if isinstance(explicit_location_external_id, str) else None,
    )


def _resolve_unresolved_pending_items_for_finalize(
    db: Session,
    *,
    household: Household,
    pending_list: ShoppingList,
    active_list: ShoppingList,
    active_items: list[ShoppingListItem],
    unresolved_action: str,
    resolved_at,
) -> tuple[int, int]:
    unresolved_items = [
        item for item in pending_list.items if item.status == SHOPPING_ITEM_STATUS_AWAITING_PURCHASE
    ]
    returned_count = 0
    deleted_count = 0

    if unresolved_action == FINALIZE_UNRESOLVED_ACTION_RETURN:
        for item in unresolved_items:
            _merge_item_into_list(
                db,
                shopping_list=active_list,
                household=household,
                existing_items=active_items,
                product=item.product,
                label=item.label,
                quantity=_requested_quantity(item),
                unit=_requested_unit(item),
                note=item.note,
                pantry_location=item.pantry_location,
                source_type=item.source_type,
                status=SHOPPING_ITEM_STATUS_OPEN,
            )
            item.status = SHOPPING_ITEM_STATUS_NOT_PURCHASED
            item.completed_at = resolved_at
            item.purchased_at = None
            item.not_purchased_at = resolved_at
            item.reconciled_at = resolved_at
            db.add(item)
            returned_count += 1
        return returned_count, deleted_count

    if unresolved_action == FINALIZE_UNRESOLVED_ACTION_DELETE:
        for item in unresolved_items:
            if item.shopping_list is not None and item in item.shopping_list.items:
                item.shopping_list.items.remove(item)
            db.delete(item)
            deleted_count += 1
        return returned_count, deleted_count

    raise ValueError("Choose how to handle the remaining unresolved shopping items first.")


def _finalize_pending_shopping_list_record(
    db: Session,
    *,
    household: Household,
    actor: User,
    pending_list: ShoppingList,
    return_shortfalls_to_active: bool = False,
    unresolved_action: str | None = None,
) -> ShoppingList:
    unresolved_items = [
        item for item in pending_list.items if item.status == SHOPPING_ITEM_STATUS_AWAITING_PURCHASE
    ]
    if unresolved_items and unresolved_action not in {
        FINALIZE_UNRESOLVED_ACTION_RETURN,
        FINALIZE_UNRESOLVED_ACTION_DELETE,
    }:
        raise ValueError("Resolve each pending shopping item before finishing this list.")

    active_list = get_or_create_active_shopping_list(db, household=household)
    active_items = list(active_list.items)
    returned_item_count = 0
    deleted_unresolved_item_count = 0
    shortfall_return_count = 0
    purchased_on = utc_now().date()
    reconciled_at = utc_now()

    if unresolved_items:
        returned_item_count, deleted_unresolved_item_count = _resolve_unresolved_pending_items_for_finalize(
            db,
            household=household,
            pending_list=pending_list,
            active_list=active_list,
            active_items=active_items,
            unresolved_action=unresolved_action or "",
            resolved_at=reconciled_at,
        )

    for item in pending_list.items:
        if item.status == SHOPPING_ITEM_STATUS_NOT_PURCHASED and item.reconciled_at is None:
            _merge_item_into_list(
                db,
                shopping_list=active_list,
                household=household,
                existing_items=active_items,
                product=item.product,
                label=item.label,
                quantity=_requested_quantity(item),
                unit=_requested_unit(item),
                note=item.note,
                pantry_location=item.pantry_location,
                source_type=item.source_type,
                status=SHOPPING_ITEM_STATUS_OPEN,
            )
            item.reconciled_at = reconciled_at
            item.completed_at = item.completed_at or reconciled_at
            item.not_purchased_at = item.not_purchased_at or reconciled_at
            db.add(item)
            returned_item_count += 1
            continue

        if item.status != SHOPPING_ITEM_STATUS_PURCHASED or item.reconciled_at is not None:
            continue

        _write_purchased_item_to_pantry(
            db,
            household=household,
            actor=actor,
            item=item,
            purchased_on=purchased_on,
        )
        if return_shortfalls_to_active and _return_shortfall_to_active_list(
            db,
            household=household,
            active_list=active_list,
            active_items=active_items,
            item=item,
        ):
            shortfall_return_count += 1
        item.reconciled_at = reconciled_at
        item.completed_at = item.completed_at or reconciled_at
        item.purchased_at = item.purchased_at or reconciled_at
        db.add(item)

    pending_list.lifecycle_state = SHOPPING_LIST_STATE_RECONCILED
    pending_list.reconciled_at = reconciled_at
    pending_list.archived_at = reconciled_at
    db.add(pending_list)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="shopping_list.reconciled",
        target_type="shopping_list",
        target_external_id=pending_list.external_id,
        event_metadata={
            "name": pending_list.name,
            "returned_item_count": returned_item_count,
            "deleted_unresolved_item_count": deleted_unresolved_item_count,
            "shortfall_return_count": shortfall_return_count,
            "purchased_item_count": sum(
                1 for item in pending_list.items if item.status == SHOPPING_ITEM_STATUS_PURCHASED
            ),
            "unresolved_action": unresolved_action,
        },
    )
    db.commit()
    return _load_shopping_list(db, household=household, external_id=pending_list.external_id) or pending_list


def bulk_operate_pending_shopping_list_items(
    db: Session,
    *,
    household: Household,
    actor: User,
    list_external_id: str,
    action: str,
    items: list[dict[str, object]],
) -> ShoppingList:
    pending_list = _load_shopping_list(db, household=household, external_id=list_external_id)
    if pending_list is None or pending_list.lifecycle_state != SHOPPING_LIST_STATE_AWAITING_PURCHASE:
        raise ValueError("Awaiting-purchase list not found.")

    if action not in {
        BULK_PENDING_ACTION_RECONCILE,
        BULK_PENDING_ACTION_RETURN,
        BULK_PENDING_ACTION_DELETE,
    }:
        raise ValueError("Unsupported bulk shopping action.")

    selected_items = _normalize_selected_pending_items(pending_list, items=items)
    now = utc_now()
    active_list = get_or_create_active_shopping_list(db, household=household)
    active_items = list(active_list.items)
    purchased_on = now.date()

    reconciled_count = 0
    returned_count = 0
    deleted_count = 0
    shortfall_return_count = 0

    for item, payload in selected_items:
        if action == BULK_PENDING_ACTION_RECONCILE:
            quantity = _normalize_reconciliation_quantity(item, payload=payload)
            unit = _normalize_reconciliation_unit(item, payload=payload)
            note = _normalize_reconciliation_note(item, payload=payload)
            pantry_location = _resolve_reconciliation_location(
                db,
                household=household,
                item=item,
                payload=payload,
            )

            item.quantity = quantity
            item.unit = unit
            item.note = note
            item.pantry_location_id = pantry_location.id if pantry_location is not None else None
            item.pantry_location = pantry_location
            item.status = SHOPPING_ITEM_STATUS_PURCHASED
            item.completed_at = now
            item.purchased_at = now
            item.not_purchased_at = None

            _write_purchased_item_to_pantry(
                db,
                household=household,
                actor=actor,
                item=item,
                purchased_on=purchased_on,
            )

            if _return_shortfall_to_active_list(
                db,
                household=household,
                active_list=active_list,
                active_items=active_items,
                item=item,
            ):
                shortfall_return_count += 1

            item.reconciled_at = now
            db.add(item)
            reconciled_count += 1
            continue

        if action == BULK_PENDING_ACTION_RETURN:
            note = _normalize_reconciliation_note(item, payload=payload)
            _merge_item_into_list(
                db,
                shopping_list=active_list,
                household=household,
                existing_items=active_items,
                product=item.product,
                label=item.label,
                quantity=_requested_quantity(item),
                unit=_requested_unit(item),
                note=note,
                pantry_location=item.pantry_location,
                source_type=item.source_type,
                status=SHOPPING_ITEM_STATUS_OPEN,
            )
            item.note = note
            item.status = SHOPPING_ITEM_STATUS_NOT_PURCHASED
            item.completed_at = now
            item.purchased_at = None
            item.not_purchased_at = now
            item.reconciled_at = now
            db.add(item)
            returned_count += 1
            continue

        if item.shopping_list is not None and item in item.shopping_list.items:
            item.shopping_list.items.remove(item)
        db.delete(item)
        deleted_count += 1

    action_name = {
        BULK_PENDING_ACTION_RECONCILE: "shopping_list.items_reconciled",
        BULK_PENDING_ACTION_RETURN: "shopping_list.items_returned",
        BULK_PENDING_ACTION_DELETE: "shopping_list.items_deleted",
    }[action]
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action=action_name,
        target_type="shopping_list",
        target_external_id=pending_list.external_id,
        event_metadata={
            "name": pending_list.name,
            "reconciled_item_count": reconciled_count,
            "returned_item_count": returned_count,
            "deleted_item_count": deleted_count,
            "shortfall_return_count": shortfall_return_count,
        },
    )
    if all(item.status != SHOPPING_ITEM_STATUS_AWAITING_PURCHASE for item in pending_list.items):
        return _finalize_pending_shopping_list_record(
            db,
            household=household,
            actor=actor,
            pending_list=pending_list,
            return_shortfalls_to_active=False,
        )

    db.commit()
    return _load_shopping_list(db, household=household, external_id=pending_list.external_id) or pending_list


def finalize_pending_shopping_list(
    db: Session,
    *,
    household: Household,
    actor: User,
    list_external_id: str,
    return_shortfalls_to_active: bool = False,
    unresolved_action: str | None = None,
) -> ShoppingList:
    pending_list = _load_shopping_list(db, household=household, external_id=list_external_id)
    if pending_list is None or pending_list.lifecycle_state != SHOPPING_LIST_STATE_AWAITING_PURCHASE:
        raise ValueError("Awaiting-purchase list not found.")
    return _finalize_pending_shopping_list_record(
        db,
        household=household,
        actor=actor,
        pending_list=pending_list,
        return_shortfalls_to_active=return_shortfalls_to_active,
        unresolved_action=unresolved_action,
    )
