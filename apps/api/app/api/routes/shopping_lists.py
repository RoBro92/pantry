from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.deps.tenancy import require_household_access
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.shopping import (
    AddShoppingListItemRequest,
    CompleteShoppingListItemRequest,
    ShoppingListSummary,
)
from app.services.shopping_lists import (
    add_item_to_default_shopping_list,
    build_household_shopping_list,
    complete_shopping_list_item,
)
from app.services.tenancy import HouseholdAccess

router = APIRouter(prefix="/households/{household_external_id}", tags=["shopping-lists"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/shopping-list", response_model=ShoppingListSummary)
def get_shopping_list(
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    return build_household_shopping_list(db, household=access.household)


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
            source_type=payload.source_type,
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
