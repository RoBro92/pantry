from __future__ import annotations

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps.auth import get_current_user
from app.api.deps.tenancy import require_household_access
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.pantry import (
    AddStockLotRequest,
    CreateLocationGroupRequest,
    CreateLocationRequest,
    CreateProductRequest,
    LocationGroupSummary,
    LocationSummary,
    MoveStockLotRequest,
    NearExpiryResponse,
    PantryOverviewResponse,
    ProductSummary,
    RemoveStockRequest,
    StockMutationResponse,
)
from app.services.pantry_catalog import create_location, create_location_group, create_product
from app.services.pantry_queries import (
    PantryFilterOptions,
    build_near_expiry_response,
    build_pantry_overview,
    build_stock_lot_summary,
)
from app.services.pantry_stock import add_stock_lot, move_stock_lot, remove_stock_from_lot
from app.services.tenancy import HouseholdAccess

router = APIRouter(prefix="/households/{household_external_id}", tags=["pantry"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/pantry/overview", response_model=PantryOverviewResponse)
def get_pantry_overview(
    q: str | None = None,
    location_group_external_id: str | None = None,
    location_external_id: str | None = None,
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    return build_pantry_overview(
        db,
        access=access,
        filters=PantryFilterOptions(
            q=q,
            location_group_external_id=location_group_external_id,
            location_external_id=location_external_id,
        ),
    )


@router.get("/pantry/near-expiry", response_model=NearExpiryResponse)
def get_near_expiry(
    days: int = Query(default=14, ge=1, le=365),
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    return build_near_expiry_response(
        db,
        access=access,
        days=days,
    )


@router.post("/location-groups", response_model=LocationGroupSummary, status_code=status.HTTP_201_CREATED)
def post_location_group(
    payload: CreateLocationGroupRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        group = create_location_group(db, household=access.household, actor=current_user, name=payload.name)
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return LocationGroupSummary(external_id=group.external_id, name=group.name, location_count=0)


@router.post("/locations", response_model=LocationSummary, status_code=status.HTTP_201_CREATED)
def post_location(
    payload: CreateLocationRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        location = create_location(
            db,
            household=access.household,
            actor=current_user,
            location_group_external_id=payload.location_group_external_id,
            name=payload.name,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return LocationSummary(
        external_id=location.external_id,
        name=location.name,
        location_group_external_id=location.location_group.external_id,
        location_group_name=location.location_group.name,
    )


@router.post("/products", response_model=ProductSummary, status_code=status.HTTP_201_CREATED)
def post_product(
    payload: CreateProductRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        product = create_product(
            db,
            household=access.household,
            actor=current_user,
            name=payload.name,
            default_unit=payload.default_unit,
            aliases=payload.aliases,
            barcodes=payload.barcodes,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return ProductSummary(
        external_id=product.external_id,
        name=product.name,
        default_unit=product.default_unit,
        aliases=[alias.name for alias in product.aliases],
        barcodes=[barcode.value for barcode in product.barcodes],
    )


@router.post("/stock-lots", response_model=StockMutationResponse, status_code=status.HTTP_201_CREATED)
def post_stock_lot(
    payload: AddStockLotRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        lot = add_stock_lot(
            db,
            household=access.household,
            actor=current_user,
            product_external_id=payload.product_external_id,
            location_external_id=payload.location_external_id,
            quantity=payload.quantity,
            note=payload.note,
            purchased_on=payload.purchased_on,
            expires_on=payload.expires_on,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return StockMutationResponse(lot=build_stock_lot_summary(lot))


@router.post("/stock-lots/{lot_external_id}/remove", response_model=StockMutationResponse)
def post_remove_stock(
    lot_external_id: str,
    payload: RemoveStockRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        lot = remove_stock_from_lot(
            db,
            household=access.household,
            actor=current_user,
            lot_external_id=lot_external_id,
            quantity=payload.quantity,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return StockMutationResponse(lot=build_stock_lot_summary(lot))


@router.post("/stock-lots/{lot_external_id}/move", response_model=StockMutationResponse)
def post_move_stock(
    lot_external_id: str,
    payload: MoveStockLotRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        lot, created_lot = move_stock_lot(
            db,
            household=access.household,
            actor=current_user,
            lot_external_id=lot_external_id,
            quantity=payload.quantity,
            destination_location_external_id=payload.destination_location_external_id,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return StockMutationResponse(
        lot=build_stock_lot_summary(lot),
        created_lot=build_stock_lot_summary(created_lot) if created_lot is not None else None,
    )
