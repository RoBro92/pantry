from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CreateLocationGroupRequest(BaseModel):
    name: str


class CreateLocationRequest(BaseModel):
    location_group_external_id: str
    name: str


class CreateProductRequest(BaseModel):
    name: str
    default_unit: str
    aliases: list[str] = Field(default_factory=list)
    barcodes: list[str] = Field(default_factory=list)


class AddStockLotRequest(BaseModel):
    product_external_id: str
    location_external_id: str
    quantity: Decimal
    note: str | None = None
    purchased_on: date | None = None
    expires_on: date | None = None


class RemoveStockRequest(BaseModel):
    quantity: Decimal


class MoveStockLotRequest(BaseModel):
    quantity: Decimal
    destination_location_external_id: str


class LocationGroupSummary(BaseModel):
    external_id: str
    name: str
    location_count: int

    model_config = ConfigDict(from_attributes=True)


class LocationSummary(BaseModel):
    external_id: str
    name: str
    location_group_external_id: str
    location_group_name: str


class ProductSummary(BaseModel):
    external_id: str
    name: str
    default_unit: str
    aliases: list[str]
    barcodes: list[str]


class ProductLocationSummary(BaseModel):
    location_external_id: str
    location_name: str
    location_group_name: str
    total_quantity: Decimal
    lot_count: int


class PantryProductSummary(BaseModel):
    product_external_id: str
    product_name: str
    unit: str
    total_quantity: Decimal
    lot_count: int
    aliases: list[str]
    barcodes: list[str]
    locations: list[ProductLocationSummary]


class StockLotSummary(BaseModel):
    external_id: str
    product_external_id: str
    product_name: str
    location_external_id: str
    location_name: str
    location_group_name: str
    quantity: Decimal
    unit: str
    note: str | None
    purchased_on: date | None
    expires_on: date | None
    is_near_expiry: bool


class AuditEventSummary(BaseModel):
    external_id: str
    action: str
    summary: str
    actor_display: str | None
    target_type: str
    target_external_id: str
    occurred_at: datetime


class PantryFilters(BaseModel):
    q: str | None
    location_group_external_id: str | None
    location_external_id: str | None


class PantryCounts(BaseModel):
    location_group_count: int
    location_count: int
    product_count: int
    active_lot_count: int
    near_expiry_lot_count: int


class PantryOverviewResponse(BaseModel):
    household_external_id: str
    household_name: str
    effective_role: str
    can_administer: bool
    filters: PantryFilters
    counts: PantryCounts
    location_groups: list[LocationGroupSummary]
    locations: list[LocationSummary]
    products: list[PantryProductSummary]
    stock_lots: list[StockLotSummary]
    recent_events: list[AuditEventSummary]


class NearExpiryResponse(BaseModel):
    household_external_id: str
    days: int
    lots: list[StockLotSummary]


class StockMutationResponse(BaseModel):
    lot: StockLotSummary
    created_lot: StockLotSummary | None = None
