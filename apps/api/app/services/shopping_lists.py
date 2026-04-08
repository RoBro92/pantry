from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.base import utc_now
from app.models.household import Household
from app.models.product import Product
from app.models.shopping_list import ShoppingList
from app.models.shopping_list_item import ShoppingListItem
from app.models.user import User
from app.schemas.shopping import ShoppingListItemSummary, ShoppingListSummary
from app.services.audit import record_audit_event
from app.services.pantry_catalog import get_product_by_external_id
from app.services.pantry_normalization import normalize_lookup_name, normalize_unit, require_text

DEFAULT_SHOPPING_LIST_NAME = "Shopping list"
SHOPPING_ITEM_STATUS_OPEN = "open"
SHOPPING_ITEM_STATUS_COMPLETED = "completed"


def _normalize_quantity(quantity: Decimal | None) -> Decimal | None:
    if quantity is None:
        return None
    if quantity <= Decimal("0"):
        raise ValueError("Shopping list quantity must be greater than zero.")
    return quantity.quantize(Decimal("0.001"))


def get_or_create_default_shopping_list(
    db: Session,
    *,
    household: Household,
    commit: bool = False,
) -> ShoppingList:
    shopping_list = db.scalar(
        select(ShoppingList)
        .where(ShoppingList.household_id == household.id)
        .where(ShoppingList.is_default.is_(True))
    )
    if shopping_list is not None:
        return shopping_list

    shopping_list = ShoppingList(
        household_id=household.id,
        name=DEFAULT_SHOPPING_LIST_NAME,
        normalized_name=normalize_lookup_name(DEFAULT_SHOPPING_LIST_NAME),
        is_default=True,
    )
    db.add(shopping_list)
    db.flush()
    if commit:
        db.commit()
        db.refresh(shopping_list)
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
        .options(selectinload(ShoppingListItem.product))
    )


def list_open_shopping_product_ids(db: Session, *, household: Household) -> set:
    product_ids = db.scalars(
        select(ShoppingListItem.product_id)
        .where(ShoppingListItem.household_id == household.id)
        .where(ShoppingListItem.status == SHOPPING_ITEM_STATUS_OPEN)
        .where(ShoppingListItem.product_id.is_not(None))
    ).all()
    return {product_id for product_id in product_ids if product_id is not None}


def serialize_shopping_list_item(item: ShoppingListItem) -> ShoppingListItemSummary:
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
    )


def build_household_shopping_list(
    db: Session,
    *,
    household: Household,
) -> ShoppingListSummary:
    shopping_list = get_or_create_default_shopping_list(db, household=household, commit=True)
    items = db.scalars(
        select(ShoppingListItem)
        .where(ShoppingListItem.shopping_list_id == shopping_list.id)
        .options(selectinload(ShoppingListItem.product))
        .order_by(
            ShoppingListItem.status.asc(),
            ShoppingListItem.completed_at.is_not(None),
            ShoppingListItem.created_at.desc(),
        )
    ).all()
    open_item_count = sum(1 for item in items if item.status == SHOPPING_ITEM_STATUS_OPEN)
    completed_item_count = sum(1 for item in items if item.status == SHOPPING_ITEM_STATUS_COMPLETED)
    return ShoppingListSummary(
        external_id=shopping_list.external_id,
        household_external_id=household.external_id,
        household_name=household.name,
        name=shopping_list.name,
        open_item_count=open_item_count,
        completed_item_count=completed_item_count,
        items=[serialize_shopping_list_item(item) for item in items],
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
    shopping_list = get_or_create_default_shopping_list(db, household=household)

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
    normalized_label = normalize_lookup_name(display_label)
    normalized_note = require_text(note, field_name="Note") if note else None
    normalized_quantity = _normalize_quantity(quantity)
    normalized_unit = normalize_unit(item_unit) if item_unit else None

    existing_item = db.scalar(
        select(ShoppingListItem)
        .where(ShoppingListItem.shopping_list_id == shopping_list.id)
        .where(ShoppingListItem.status == SHOPPING_ITEM_STATUS_OPEN)
        .where(
            ShoppingListItem.product_id == product.id
            if product is not None
            else ShoppingListItem.normalized_label == normalized_label
        )
        .options(selectinload(ShoppingListItem.product))
    )
    if existing_item is not None:
        if normalized_quantity is not None:
            existing_item.quantity = normalized_quantity
        if normalized_unit is not None:
            existing_item.unit = normalized_unit
        if normalized_note is not None:
            existing_item.note = normalized_note
        db.add(existing_item)
        db.commit()
        db.refresh(existing_item)
        return existing_item

    item = ShoppingListItem(
        household_id=household.id,
        shopping_list_id=shopping_list.id,
        product_id=product.id if product is not None else None,
        label=display_label,
        normalized_label=normalized_label,
        quantity=normalized_quantity,
        unit=normalized_unit,
        note=normalized_note,
        source_type=source_type,
        status=SHOPPING_ITEM_STATUS_OPEN,
    )
    db.add(item)
    db.flush()
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
    status: str = SHOPPING_ITEM_STATUS_COMPLETED,
) -> ShoppingListItem:
    item = get_shopping_list_item_by_external_id(db, household=household, item_external_id=item_external_id)
    if item is None:
        raise ValueError("Shopping list item not found.")

    item.status = status
    item.completed_at = utc_now() if status == SHOPPING_ITEM_STATUS_COMPLETED else None
    db.add(item)
    record_audit_event(
        db,
        household=household,
        actor=actor,
        action="shopping_list.item_completed",
        target_type="shopping_list_item",
        target_external_id=item.external_id,
        event_metadata={
            "label": item.label,
            "product_name": item.product.name if item.product is not None else None,
            "status": status,
        },
    )
    db.commit()
    db.refresh(item)
    return item
