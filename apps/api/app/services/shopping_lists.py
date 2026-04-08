from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.base import utc_now
from app.models.household import Household
from app.models.product import Product
from app.models.shopping_list import ShoppingList
from app.models.shopping_list_item import ShoppingListItem
from app.models.user import User
from app.schemas.shopping import (
    ShoppingListDetailSummary,
    ShoppingListItemSummary,
    ShoppingListSummary,
)
from app.services.audit import record_audit_event
from app.services.pantry_catalog import get_product_by_external_id
from app.services.pantry_normalization import (
    lookup_token_signature,
    normalize_lookup_name,
    normalize_unit,
    require_text,
)

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


def _format_quantity(quantity: Decimal | None, unit: str | None) -> str | None:
    if quantity is None:
        return None
    if unit:
        return f"{quantity} {unit}"
    return str(quantity)


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
        unit=item.unit,
        note=item.note,
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
            selectinload(ShoppingList.merged_into_list),
        )
    )


def _load_all_lists(db: Session, *, household: Household) -> list[ShoppingList]:
    return db.scalars(
        select(ShoppingList)
        .where(ShoppingList.household_id == household.id)
        .options(
            selectinload(ShoppingList.items).selectinload(ShoppingListItem.product),
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
            selectinload(ShoppingListItem.shopping_list).selectinload(ShoppingList.items),
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
        source_type=source_type,
        status=status,
    )
    db.add(item)
    db.flush()
    if product is not None:
        item.product = product
    existing_items.append(item)
    return item


def build_household_shopping_list(
    db: Session,
    *,
    household: Household,
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
        key=lambda shopping_list: shopping_list.generated_at or shopping_list.updated_at,
        reverse=True,
    )
    history_lists.sort(
        key=lambda shopping_list: shopping_list.reconciled_at or shopping_list.updated_at,
        reverse=True,
    )

    return ShoppingListSummary(
        household_external_id=household.external_id,
        household_name=household.name,
        active_list=_serialize_list(active),
        pending_lists=[_serialize_list(shopping_list) for shopping_list in pending_lists],
        history_lists=[_serialize_list(shopping_list) for shopping_list in history_lists[:6]],
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
) -> ShoppingListItem:
    item = get_shopping_list_item_by_external_id(db, household=household, item_external_id=item_external_id)
    if item is None or item.shopping_list is None:
        raise ValueError("Shopping list item not found.")

    normalized_quantity = _normalize_quantity(quantity) if quantity is not None else None
    normalized_unit = normalize_unit(unit) if unit else None
    normalized_note = require_text(note, field_name="Note") if note else None

    if normalized_quantity is not None:
        item.quantity = normalized_quantity
    if unit is not None:
        item.unit = normalized_unit
    if note is not None:
        item.note = normalized_note

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
        if status in {SHOPPING_ITEM_STATUS_OPEN, SHOPPING_ITEM_STATUS_AWAITING_PURCHASE}:
            item.completed_at = None
            item.purchased_at = None
            item.not_purchased_at = None

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
    db.commit()
    db.refresh(item)
    return get_shopping_list_item_by_external_id(db, household=household, item_external_id=item.external_id) or item


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
        "Pantry shopping list",
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
                source_type=item.source_type,
                status=SHOPPING_ITEM_STATUS_AWAITING_PURCHASE,
            )
            db.delete(item)
            merged_item_count += 1
        source_list.lifecycle_state = SHOPPING_LIST_STATE_MERGED
        source_list.reconciled_at = utc_now()
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
            quantity=item.quantity,
            unit=item.unit,
            note=item.note,
            source_type=item.source_type,
            status=SHOPPING_ITEM_STATUS_OPEN,
        )
        item.status = SHOPPING_ITEM_STATUS_NOT_PURCHASED
        item.not_purchased_at = utc_now()
        db.add(item)
        returned_item_count += 1

    pending_list.lifecycle_state = SHOPPING_LIST_STATE_RETURNED
    pending_list.reconciled_at = utc_now()
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


def finalize_pending_shopping_list(
    db: Session,
    *,
    household: Household,
    actor: User,
    list_external_id: str,
) -> ShoppingList:
    pending_list = _load_shopping_list(db, household=household, external_id=list_external_id)
    if pending_list is None or pending_list.lifecycle_state != SHOPPING_LIST_STATE_AWAITING_PURCHASE:
        raise ValueError("Awaiting-purchase list not found.")

    unresolved_items = [
        item for item in pending_list.items if item.status == SHOPPING_ITEM_STATUS_AWAITING_PURCHASE
    ]
    if unresolved_items:
        raise ValueError("Resolve each pending shopping item before finishing this list.")

    active_list = get_or_create_active_shopping_list(db, household=household)
    active_items = list(active_list.items)
    returned_item_count = 0
    for item in pending_list.items:
        if item.status != SHOPPING_ITEM_STATUS_NOT_PURCHASED:
            continue
        _merge_item_into_list(
            db,
            shopping_list=active_list,
            household=household,
            existing_items=active_items,
            product=item.product,
            label=item.label,
            quantity=item.quantity,
            unit=item.unit,
            note=item.note,
            source_type=item.source_type,
            status=SHOPPING_ITEM_STATUS_OPEN,
        )
        returned_item_count += 1

    pending_list.lifecycle_state = SHOPPING_LIST_STATE_RECONCILED
    pending_list.reconciled_at = utc_now()
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
            "purchased_item_count": sum(
                1
                for item in pending_list.items
                if item.status == SHOPPING_ITEM_STATUS_PURCHASED
            ),
        },
    )
    db.commit()
    return _load_shopping_list(db, household=household, external_id=pending_list.external_id) or pending_list
