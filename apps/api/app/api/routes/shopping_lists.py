from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.deps.tenancy import require_household_access
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.shopping import (
    AddShoppingListItemRequest,
    AttachShoppingListProductRequest,
    BulkPendingShoppingListRequest,
    CompleteShoppingListItemRequest,
    FinalizePendingShoppingListRequest,
    MergePendingShoppingListsRequest,
    ShoppingListSummary,
    UpdateShoppingListItemRequest,
)
from app.services.shopping_lists import (
    add_item_to_default_shopping_list,
    attach_product_to_shopping_list_item,
    bulk_operate_pending_shopping_list_items,
    build_household_shopping_list,
    complete_shopping_list_item,
    delete_shopping_list_item,
    export_active_shopping_list,
    finalize_pending_shopping_list,
    merge_pending_shopping_lists,
    return_pending_list_to_active,
    update_shopping_list_item,
)
from app.services.tenancy import HouseholdAccess

router = APIRouter(prefix="/households/{household_external_id}", tags=["shopping-lists"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/shopping-list", response_model=ShoppingListSummary)
def get_shopping_list(
    history_limit: int = Query(default=6, ge=1, le=200),
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    return build_household_shopping_list(db, household=access.household, history_limit=history_limit)


@router.post("/shopping-list/items", response_model=ShoppingListSummary, status_code=status.HTTP_201_CREATED)
def post_shopping_list_item(
    payload: AddShoppingListItemRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        add_item_to_default_shopping_list(
            db,
            household=access.household,
            actor=current_user,
            product_external_id=payload.product_external_id,
            label=payload.label,
            quantity=payload.quantity,
            unit=payload.unit,
            note=payload.note,
            pantry_location_external_id=payload.pantry_location_external_id,
            source_type=payload.source_type,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return build_household_shopping_list(db, household=access.household)


@router.put("/shopping-list/items/{item_external_id}", response_model=ShoppingListSummary)
def put_shopping_list_item(
    item_external_id: str,
    payload: UpdateShoppingListItemRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        update_shopping_list_item(
            db,
            household=access.household,
            actor=current_user,
            item_external_id=item_external_id,
            status=payload.status,
            quantity=payload.quantity,
            unit=payload.unit,
            note=payload.note,
            pantry_location_external_id=payload.pantry_location_external_id,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return build_household_shopping_list(db, household=access.household)


@router.post("/shopping-list/pending/{list_external_id}/bulk", response_model=ShoppingListSummary)
def post_bulk_pending_list_action(
    list_external_id: str,
    payload: BulkPendingShoppingListRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        bulk_operate_pending_shopping_list_items(
            db,
            household=access.household,
            actor=current_user,
            list_external_id=list_external_id,
            action=payload.action,
            items=[
                {
                    "item_external_id": item.item_external_id,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "note": item.note,
                    "pantry_location_external_id": item.pantry_location_external_id,
                }
                for item in payload.items
            ],
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return build_household_shopping_list(db, household=access.household)


@router.delete("/shopping-list/items/{item_external_id}", response_model=ShoppingListSummary)
def delete_shopping_list_item_route(
    item_external_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        delete_shopping_list_item(
            db,
            household=access.household,
            actor=current_user,
            item_external_id=item_external_id,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return build_household_shopping_list(db, household=access.household)


@router.post("/shopping-list/items/{item_external_id}/attach-product", response_model=ShoppingListSummary)
def post_attach_shopping_list_product(
    item_external_id: str,
    payload: AttachShoppingListProductRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        attach_product_to_shopping_list_item(
            db,
            household=access.household,
            actor=current_user,
            item_external_id=item_external_id,
            product_external_id=payload.product_external_id,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return build_household_shopping_list(db, household=access.household)


@router.post("/shopping-list/items/{item_external_id}/complete", response_model=ShoppingListSummary)
def post_complete_shopping_list_item(
    item_external_id: str,
    payload: CompleteShoppingListItemRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        complete_shopping_list_item(
            db,
            household=access.household,
            actor=current_user,
            item_external_id=item_external_id,
            status=payload.status,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return build_household_shopping_list(db, household=access.household)


@router.post("/shopping-list/export", response_class=PlainTextResponse)
def post_export_shopping_list(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        shopping_list, export_text = export_active_shopping_list(
            db,
            household=access.household,
            actor=current_user,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return PlainTextResponse(
        export_text,
        headers={
            "content-disposition": (
                f'attachment; filename="{shopping_list.name.casefold().replace(" ", "-")}.txt"'
            )
        },
    )


@router.post("/shopping-list/pending/merge", response_model=ShoppingListSummary)
def post_merge_pending_shopping_lists(
    payload: MergePendingShoppingListsRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        merge_pending_shopping_lists(
            db,
            household=access.household,
            actor=current_user,
            target_list_external_id=payload.target_list_external_id,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return build_household_shopping_list(db, household=access.household)


@router.post("/shopping-list/pending/{list_external_id}/return-to-active", response_model=ShoppingListSummary)
def post_return_pending_list_to_active(
    list_external_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        return_pending_list_to_active(
            db,
            household=access.household,
            actor=current_user,
            list_external_id=list_external_id,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return build_household_shopping_list(db, household=access.household)


@router.post("/shopping-list/pending/{list_external_id}/finalize", response_model=ShoppingListSummary)
def post_finalize_pending_list(
    list_external_id: str,
    payload: FinalizePendingShoppingListRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        finalize_pending_shopping_list(
            db,
            household=access.household,
            actor=current_user,
            list_external_id=list_external_id,
            return_shortfalls_to_active=payload.return_shortfalls_to_active,
            unresolved_action=payload.unresolved_action,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return build_household_shopping_list(db, household=access.household)
