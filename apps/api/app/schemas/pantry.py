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
    manual_ingredient_tags: list[str] = Field(default_factory=list)
    confirmed_enrichment: "ConfirmedProductEnrichmentRequest | None" = None


class CreatePantryEntryRequest(BaseModel):
    name: str
    quantity: Decimal
    unit: str
    location_external_id: str
    barcode: str | None = None
    aliases: list[str] = Field(default_factory=list)
    manual_ingredient_tags: list[str] = Field(default_factory=list)
    purchased_on: date | None = None
    expires_on: date | None = None
    note: str | None = None
    existing_product_external_id: str | None = None
    allow_separate_product: bool = False
    confirmed_enrichment: "ConfirmedProductEnrichmentRequest | None" = None


class ProductNutritionSummaryItem(BaseModel):
    key: str
    label: str
    value: float
    unit: str | None = None


class ProductEnrichmentAttribution(BaseModel):
    source_name: str
    source_label: str
    source_url: str
    product_url: str | None = None
    data_notice: str
    license_name: str | None = None
    license_url: str | None = None


class ProductEnrichmentSummary(BaseModel):
    source_name: str
    source_product_id: str
    source_barcode: str | None
    source_product_name: str | None
    source_product_url: str | None
    product_image_url: str | None
    enrichment_status: str | None = None
    ingredients_text: str | None
    ingredient_tags: list[str] = Field(default_factory=list)
    ingredient_tokens: list[str] = Field(default_factory=list)
    allergens_text: str | None
    traces_text: str | None
    allergen_tags: list[str] = Field(default_factory=list)
    trace_tags: list[str] = Field(default_factory=list)
    dietary_tags: list[str] = Field(default_factory=list)
    nutriments_payload: dict[str, object] = Field(default_factory=dict)
    nutrition_summary: list[ProductNutritionSummaryItem] = Field(default_factory=list)
    nutrition_summary_text: str | None = None
    labels: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    match_status: str | None = None
    match_confidence: float | None = None
    last_synced_at: datetime | None = None
    attribution: ProductEnrichmentAttribution


class ConfirmedProductEnrichmentRequest(BaseModel):
    source_name: str
    source_product_id: str
    match_status: str | None = None


class ProductEnrichmentCandidate(BaseModel):
    source_name: str
    source_product_id: str
    source_barcode: str | None
    source_product_name: str | None
    source_product_url: str | None
    product_image_url: str | None
    enrichment_status: str | None = None
    ingredients_text: str | None
    ingredient_tags: list[str] = Field(default_factory=list)
    ingredient_tokens: list[str] = Field(default_factory=list)
    allergens_text: str | None
    traces_text: str | None
    allergen_tags: list[str] = Field(default_factory=list)
    trace_tags: list[str] = Field(default_factory=list)
    dietary_tags: list[str] = Field(default_factory=list)
    nutriments_payload: dict[str, object] = Field(default_factory=dict)
    nutrition_summary: list[ProductNutritionSummaryItem] = Field(default_factory=list)
    nutrition_summary_text: str | None = None
    labels: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    match_status: str
    match_confidence: float | None = None
    incomplete_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    attribution: ProductEnrichmentAttribution


class ProductEnrichmentPreviewRequest(BaseModel):
    product_name: str
    barcode: str | None = None


class ProductEnrichmentPreviewResponse(BaseModel):
    query_name: str
    query_barcode: str | None
    lookup_strategy: str
    status: str
    message: str
    candidates: list[ProductEnrichmentCandidate] = Field(default_factory=list)


class AddStockLotRequest(BaseModel):
    product_external_id: str
    location_external_id: str
    quantity: Decimal
    note: str | None = None
    purchased_on: date | None = None
    expires_on: date | None = None


class UpdateStockLotRequest(BaseModel):
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


class PantryDuplicateCheckRequest(BaseModel):
    name: str | None = None
    barcode: str | None = None


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
    location_route: str | None = None
    browser_path: str | None = None
    browser_url: str | None = None


class ProductSummary(BaseModel):
    external_id: str
    name: str
    default_unit: str
    aliases: list[str]
    barcodes: list[str]
    manual_ingredient_tags: list[str] = Field(default_factory=list)
    enrichment: ProductEnrichmentSummary | None = None


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
    stock_status: str
    room_summary: str
    storage_summary: str
    nearest_expiry_on: date | None = None
    near_expiry_lot_count: int = 0
    manual_ingredient_tags: list[str] = Field(default_factory=list)
    aliases: list[str]
    barcodes: list[str]
    is_in_shopping_list: bool = False
    enrichment: ProductEnrichmentSummary | None = None
    locations: list[ProductLocationSummary]
    stock_lots: list["StockLotSummary"]


class ProductMatchSummary(BaseModel):
    external_id: str
    name: str
    default_unit: str
    aliases: list[str]
    match_reason: str | None = None
    match_confidence: float | None = None
    can_keep_separate_product: bool = False


class ProductAliasConflictSummary(BaseModel):
    alias: str
    product_external_id: str
    product_name: str


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
    depleted_at: datetime | None = None
    is_depleted: bool = False
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
    near_expiry_only: bool = False


class PantryCounts(BaseModel):
    location_group_count: int
    location_count: int
    product_count: int
    active_lot_count: int
    near_expiry_lot_count: int
    out_of_stock_product_count: int = 0


class PantryOverviewResponse(BaseModel):
    household_external_id: str
    household_name: str
    effective_role: str
    can_administer: bool
    page: int = 1
    page_size: int = 25
    page_count: int = 1
    matched_product_count: int = 0
    filters: PantryFilters
    counts: PantryCounts
    location_groups: list[LocationGroupSummary]
    locations: list[LocationSummary]
    catalog_products: list[ProductSummary]
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


class PantryEntryMutationResponse(BaseModel):
    status: str
    message: str
    product: ProductSummary | None = None
    lot: StockLotSummary | None = None
    matched_product: ProductMatchSummary | None = None
    duplicate_match_reason: str | None = None
    can_keep_separate_product: bool = False
    alias_conflicts: list[ProductAliasConflictSummary] = Field(default_factory=list)


class PantryDuplicateCheckResponse(BaseModel):
    status: str
    message: str
    matched_product: ProductMatchSummary | None = None
    duplicate_match_reason: str | None = None
    can_keep_separate_product: bool = False
