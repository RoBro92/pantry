from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ImportLinkedProductSummary(BaseModel):
    external_id: str
    name: str
    default_unit: str


class ImportSourceFileSummary(BaseModel):
    external_id: str
    original_filename: str
    client_content_type: str | None
    detected_content_type: str | None
    file_extension: str | None
    size_bytes: int
    validation_status: str
    scan_status: str
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportCountsSummary(BaseModel):
    line_count: int
    matched_line_count: int
    needs_review_line_count: int
    unresolved_line_count: int
    ignored_line_count: int
    confirmed_line_count: int


class ImportJobSummary(BaseModel):
    external_id: str
    source_type: str
    status: str
    source_label: str
    note: str | None
    occurred_on: date | None
    parser_kind: str | None
    failure_message: str | None
    requested_by_display: str | None
    counts: ImportCountsSummary
    source_files: list[ImportSourceFileSummary]
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None
    confirmed_at: datetime | None


class ImportLineSummary(BaseModel):
    external_id: str
    position: int
    source_reference: str | None
    raw_label: str
    quantity: Decimal
    unit: str
    barcode: str | None
    note: str | None
    purchased_on: date | None
    expires_on: date | None
    status: str
    match_basis: str
    product: ImportLinkedProductSummary | None
    suggested_product: ImportLinkedProductSummary | None
    confirmed_stock_lot_external_id: str | None = None
    updated_at: datetime


class ImportDetail(BaseModel):
    external_id: str
    source_type: str
    status: str
    source_label: str
    note: str | None
    occurred_on: date | None
    parser_kind: str | None
    failure_message: str | None
    requested_by_display: str | None
    counts: ImportCountsSummary
    source_files: list[ImportSourceFileSummary]
    lines: list[ImportLineSummary]
    ready_to_confirm: bool
    blocking_line_count: int
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None
    confirmed_at: datetime | None


class ImportListResponse(BaseModel):
    household_external_id: str
    household_name: str
    effective_role: str
    can_administer: bool
    imports: list[ImportJobSummary]


class ImportDetailResponse(BaseModel):
    household_external_id: str
    household_name: str
    effective_role: str
    can_administer: bool
    import_job: ImportDetail


class UpdateImportLineRequest(BaseModel):
    raw_label: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    barcode: str | None = None
    note: str | None = None
    purchased_on: date | None = None
    expires_on: date | None = None
    product_external_id: str | None = None
    status: str | None = None


class ConfirmImportRequest(BaseModel):
    location_external_id: str
    purchased_on: date | None = None
