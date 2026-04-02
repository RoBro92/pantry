from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.pantry import LocationSummary


class LocationLinkSummary(BaseModel):
    location_route: str
    browser_path: str
    browser_url: str


class LocationAccessLotSummary(BaseModel):
    external_id: str
    product_external_id: str
    product_name: str
    quantity: Decimal
    unit: str
    note: str | None
    expires_on: date | None


class LocationAccessResponse(BaseModel):
    location_route: str
    browser_path: str
    browser_url: str
    pantry_path: str
    household_external_id: str
    household_name: str
    effective_role: str
    can_administer: bool
    location: LocationSummary
    stock_lots: list[LocationAccessLotSummary]
    active_lot_count: int
    active_product_count: int
