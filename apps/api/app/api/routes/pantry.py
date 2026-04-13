from __future__ import annotations

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps.auth import get_current_user
from app.api.deps.tenancy import require_household_access
from app.core.db import get_db_session
from app.domain.roles import HOUSEHOLD_ADMIN_ROLE
from app.models.user import User
from app.schemas.pantry import (
    AddStockLotRequest,
    ConfirmedProductEnrichmentRequest,
    CreatePantryEntryRequest,
    CreateLocationGroupRequest,
    CreateLocationRequest,
    DeleteProductResponse,
    ProductEnrichmentPreviewRequest,
    ProductEnrichmentPreviewResponse,
    CreateProductRequest,
    UpdateProductRequest,
    LocationGroupSummary,
    LocationSummary,
    MoveStockLotRequest,
    NearExpiryResponse,
    PantryOverviewResponse,
    PantryEntryMutationResponse,
    PantryDuplicateCheckRequest,
    PantryDuplicateCheckResponse,
    ProductIntelligenceRunRequest,
    ProductIntelligenceRunResponse,
    ProductIntelligenceStatusResponse,
    ProductSummary,
    RemoveStockRequest,
    StockMutationResponse,
    UpdateStockLotRequest,
)
from app.services.pantry_catalog import (
    create_location,
    create_location_group,
    create_product,
    delete_product,
    get_product_by_external_id,
    update_product,
)
from app.services.location_links import serialize_location_link
from app.services.pantry_queries import (
    PantryFilterOptions,
    build_near_expiry_response,
    build_pantry_overview,
    build_stock_lot_summary,
)
from app.services.pantry_stock import (
    add_stock_lot,
    buy_more_from_stock_lot,
    create_or_add_pantry_entry,
    detect_pantry_duplicate,
    move_stock_lot,
    remove_stock_from_lot,
    update_stock_lot,
)
from app.services.product_enrichment import (
    ProductEnrichmentError,
    apply_confirmed_product_enrichment,
    preview_product_enrichment,
    serialize_product_summary,
)
from app.services.product_intelligence import (
    build_product_intelligence_status,
    run_product_intelligence_classification,
)
from app.services.ai_runtime_errors import AIUserFacingError
from app.services.tenancy import HouseholdAccess

router = APIRouter(prefix="/households/{household_external_id}", tags=["pantry"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/pantry/overview", response_model=PantryOverviewResponse)
def get_pantry_overview(
    q: str | None = None,
    location_group_external_id: str | None = None,
    location_external_id: str | None = None,
    near_expiry_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=50),
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
            near_expiry_only=near_expiry_only,
        ),
        page=page,
        page_size=page_size,
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


@router.get("/product-intelligence/status", response_model=ProductIntelligenceStatusResponse)
def get_product_intelligence_status(
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access(allowed_roles={HOUSEHOLD_ADMIN_ROLE})),
):
    return build_product_intelligence_status(db, household=access.household)


@router.post("/product-intelligence/classify", response_model=ProductIntelligenceRunResponse)
def post_product_intelligence_classification(
    payload: ProductIntelligenceRunRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access(allowed_roles={HOUSEHOLD_ADMIN_ROLE})),
):
    try:
        return run_product_intelligence_classification(
            db,
            household=access.household,
            actor=current_user,
            request=payload,
        )
    except ValueError as exc:
        if isinstance(exc, AIUserFacingError):
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        message = str(exc)
        if "provider" in message.lower() or "ai " in message.lower() or "disabled" in message.lower():
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.post("/location-groups", response_model=LocationGroupSummary, status_code=status.HTTP_201_CREATED)
def post_location_group(
    payload: CreateLocationGroupRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access(allowed_roles={HOUSEHOLD_ADMIN_ROLE})),
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
    access: HouseholdAccess = Depends(require_household_access(allowed_roles={HOUSEHOLD_ADMIN_ROLE})),
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
        **serialize_location_link(db, location=location),
    )


@router.post("/products", response_model=ProductSummary, status_code=status.HTTP_201_CREATED)
def post_product(
    payload: CreateProductRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access(allowed_roles={HOUSEHOLD_ADMIN_ROLE})),
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
            notes=payload.notes,
            manual_ingredient_tags=payload.manual_ingredient_tags,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    if payload.confirmed_enrichment is not None:
        try:
            apply_confirmed_product_enrichment(
                db,
                household=access.household,
                actor=current_user,
                product=product,
                confirmed_enrichment=payload.confirmed_enrichment,
            )
            db.commit()
            db.expire_all()
            product = (
                get_product_by_external_id(db, household=access.household, external_id=product.external_id)
                or product
            )
        except ProductEnrichmentError:
            pass

    return serialize_product_summary(product)


@router.put("/products/{product_external_id}", response_model=ProductSummary)
def put_product(
    product_external_id: str,
    payload: UpdateProductRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access(allowed_roles={HOUSEHOLD_ADMIN_ROLE})),
):
    product = get_product_by_external_id(db, household=access.household, external_id=product_external_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    try:
        product = update_product(
            db,
            household=access.household,
            actor=current_user,
            product=product,
            name=payload.name,
            default_unit=payload.default_unit,
            aliases=payload.aliases,
            barcodes=payload.barcodes,
            notes=payload.notes,
            manual_ingredient_tags=payload.manual_ingredient_tags,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    if payload.confirmed_enrichment is not None:
        try:
            apply_confirmed_product_enrichment(
                db,
                household=access.household,
                actor=current_user,
                product=product,
                confirmed_enrichment=payload.confirmed_enrichment,
            )
            db.commit()
            db.expire_all()
            product = get_product_by_external_id(db, household=access.household, external_id=product_external_id) or product
        except ProductEnrichmentError:
            pass

    return serialize_product_summary(product)


@router.delete("/products/{product_external_id}", response_model=DeleteProductResponse)
def delete_product_route(
    product_external_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access(allowed_roles={HOUSEHOLD_ADMIN_ROLE})),
):
    product = get_product_by_external_id(db, household=access.household, external_id=product_external_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    delete_product(
        db,
        household=access.household,
        actor=current_user,
        product=product,
    )
    return DeleteProductResponse(
        message=f"Deleted {product.name} and its associated stock lots from Pantry.",
    )


@router.post("/pantry/enrichment/preview", response_model=ProductEnrichmentPreviewResponse)
def post_product_enrichment_preview(
    payload: ProductEnrichmentPreviewRequest,
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        return preview_product_enrichment(product_name=payload.product_name, barcode=payload.barcode)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.post("/products/{product_external_id}/enrichment", response_model=ProductSummary)
def post_product_enrichment(
    product_external_id: str,
    payload: ConfirmedProductEnrichmentRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access(allowed_roles={HOUSEHOLD_ADMIN_ROLE})),
):
    product = get_product_by_external_id(db, household=access.household, external_id=product_external_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    try:
        apply_confirmed_product_enrichment(
            db,
            household=access.household,
            actor=current_user,
            product=product,
            confirmed_enrichment=payload,
        )
        db.commit()
        db.expire_all()
        product = get_product_by_external_id(db, household=access.household, external_id=product_external_id) or product
    except ProductEnrichmentError as exc:
        raise _bad_request(exc) from exc

    return serialize_product_summary(product)


@router.post("/pantry/entries", response_model=PantryEntryMutationResponse)
def post_pantry_entry(
    payload: CreatePantryEntryRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        result = create_or_add_pantry_entry(
            db,
            household=access.household,
            actor=current_user,
            name=payload.name,
            quantity=payload.quantity,
            unit=payload.unit,
            location_external_id=payload.location_external_id,
            barcode=payload.barcode,
            aliases=payload.aliases,
            product_notes=payload.product_notes,
            manual_ingredient_tags=payload.manual_ingredient_tags,
            note=payload.note,
            purchased_on=payload.purchased_on,
            expires_on=payload.expires_on,
            existing_product_external_id=payload.existing_product_external_id,
            allow_separate_product=payload.allow_separate_product,
            confirmed_enrichment=payload.confirmed_enrichment,
            allow_create_product=access.can_administer,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    product = result.get("product")
    lot = result.get("lot")
    matched_product = result.get("matched_product")
    return PantryEntryMutationResponse(
        status=str(result["status"]),
        message=str(result["message"]),
        product=(
            serialize_product_summary(product)
            if product is not None
            else None
        ),
        lot=build_stock_lot_summary(lot) if lot is not None else None,
        matched_product=(
            {
                "external_id": matched_product.external_id,
                "name": matched_product.name,
                "default_unit": matched_product.default_unit,
                "aliases": [alias.name for alias in matched_product.aliases],
                "match_reason": str(result.get("duplicate_match_reason") or ""),
                "match_confidence": None,
                "can_keep_separate_product": bool(result.get("can_keep_separate_product", False)),
            }
            if matched_product is not None
            else None
        ),
        duplicate_match_reason=str(result.get("duplicate_match_reason") or "") or None,
        can_keep_separate_product=bool(result.get("can_keep_separate_product", False)),
        alias_conflicts=list(result.get("alias_conflicts", [])),
    )


@router.post("/pantry/entries/duplicate-check", response_model=PantryDuplicateCheckResponse)
def post_pantry_duplicate_check(
    payload: PantryDuplicateCheckRequest,
    db: Session = Depends(get_db_session),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        duplicate = detect_pantry_duplicate(
            db,
            household=access.household,
            display_name=payload.name or "",
            barcode=payload.barcode,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    matched_product = duplicate["matched_product"]
    return PantryDuplicateCheckResponse(
        status="matched" if matched_product is not None else "none",
        message=str(duplicate["message"]),
        matched_product=(
            {
                "external_id": matched_product.external_id,
                "name": matched_product.name,
                "default_unit": matched_product.default_unit,
                "aliases": [alias.name for alias in matched_product.aliases],
                "match_reason": duplicate["match_reason"],
                "match_confidence": duplicate["match_confidence"],
                "can_keep_separate_product": bool(duplicate["can_keep_separate_product"]),
            }
            if matched_product is not None
            else None
        ),
        duplicate_match_reason=duplicate["match_reason"],
        can_keep_separate_product=bool(duplicate["can_keep_separate_product"]),
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


@router.put("/stock-lots/{lot_external_id}", response_model=StockMutationResponse)
def put_stock_lot(
    lot_external_id: str,
    payload: UpdateStockLotRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        lot = update_stock_lot(
            db,
            household=access.household,
            actor=current_user,
            lot_external_id=lot_external_id,
            quantity=payload.quantity,
            location_external_id=payload.location_external_id,
            note=payload.note,
            purchased_on=payload.purchased_on,
            expires_on=payload.expires_on,
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


@router.post("/stock-lots/{lot_external_id}/buy-more", response_model=StockMutationResponse)
def post_buy_more_stock(
    lot_external_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    access: HouseholdAccess = Depends(require_household_access()),
):
    try:
        lot = buy_more_from_stock_lot(
            db,
            household=access.household,
            actor=current_user,
            lot_external_id=lot_external_id,
        )
    except ValueError as exc:
        raise _bad_request(exc) from exc

    return StockMutationResponse(lot=build_stock_lot_summary(lot))
