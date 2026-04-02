from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.location import Location
from app.models.product import Product
from app.models.stock_lot import StockLot
from app.models.user import User
from app.services.instance_settings import resolve_public_base_url
from app.services.tenancy import resolve_household_access


def build_location_browser_path(location_route: str) -> str:
    return f"/locations/{location_route}"


def build_location_browser_url(db: Session, *, location_route: str) -> str:
    public_base_url = resolve_public_base_url(db)
    return f"{public_base_url.effective_value}{build_location_browser_path(location_route)}"


def serialize_location_link(db: Session, *, location: Location) -> dict[str, str]:
    location_route = location.external_id
    return {
        "location_route": location_route,
        "browser_path": build_location_browser_path(location_route),
        "browser_url": build_location_browser_url(db, location_route=location_route),
    }


def get_location_by_route(db: Session, *, location_route: str) -> Location | None:
    return db.scalar(
        select(Location)
        .where(Location.external_id == location_route)
        .options(selectinload(Location.location_group), selectinload(Location.household))
    )


def build_location_access_response(
    db: Session,
    *,
    location_route: str,
    user: User,
) -> dict[str, object] | None:
    location = get_location_by_route(db, location_route=location_route)
    if location is None:
        return None

    access = resolve_household_access(db, household_external_id=location.household.external_id, user=user)
    if access is None:
        return None

    lots = db.scalars(
        select(StockLot)
        .where(StockLot.household_id == access.household.id)
        .where(StockLot.location_id == location.id)
        .where(StockLot.depleted_at.is_(None))
        .where(StockLot.quantity > Decimal("0"))
        .options(selectinload(StockLot.product).selectinload(Product.aliases))
        .order_by(StockLot.expires_on, StockLot.created_at)
    ).all()

    link = serialize_location_link(db, location=location)
    pantry_path = f"/app/households/{access.household.external_id}?location_external_id={location.external_id}"
    return {
        "location_route": link["location_route"],
        "browser_path": link["browser_path"],
        "browser_url": link["browser_url"],
        "pantry_path": pantry_path,
        "household_external_id": access.household.external_id,
        "household_name": access.household.name,
        "effective_role": access.effective_role,
        "can_administer": access.can_administer,
        "location": {
            "external_id": location.external_id,
            "name": location.name,
            "location_group_external_id": location.location_group.external_id,
            "location_group_name": location.location_group.name,
        },
        "stock_lots": [
            {
                "external_id": lot.external_id,
                "product_external_id": lot.product.external_id,
                "product_name": lot.product.name,
                "quantity": lot.quantity,
                "unit": lot.unit,
                "note": lot.note,
                "expires_on": lot.expires_on,
            }
            for lot in lots
        ],
        "active_lot_count": len(lots),
        "active_product_count": len({lot.product_id for lot in lots}),
    }
