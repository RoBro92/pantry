from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class AddShoppingListItemRequest(BaseModel):
    product_external_id: str | None = None
    label: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    note: str | None = None
    source_type: str = "manual"

    @model_validator(mode="after")
    def validate_target(self) -> "AddShoppingListItemRequest":
        if not (self.product_external_id or (self.label and self.label.strip())):
            raise ValueError("A product or item label is required.")
        return self


class CompleteShoppingListItemRequest(BaseModel):
    status: str = "completed"


class UpdateShoppingListItemRequest(BaseModel):
    status: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    note: str | None = None


class MergePendingShoppingListsRequest(BaseModel):
    target_list_external_id: str | None = None


class AttachShoppingListProductRequest(BaseModel):
    product_external_id: str


class ShoppingListItemSummary(BaseModel):
    external_id: str
    label: str
    product_external_id: str | None = None
    product_name: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    note: str | None = None
    source_type: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    purchased_at: datetime | None = None
    not_purchased_at: datetime | None = None


class ShoppingListDetailSummary(BaseModel):
    external_id: str
    name: str
    lifecycle_state: str
    item_count: int
    unresolved_item_count: int
    purchased_item_count: int
    not_purchased_item_count: int
    generated_at: datetime | None = None
    reconciled_at: datetime | None = None
    merged_into_list_external_id: str | None = None
    items: list[ShoppingListItemSummary] = Field(default_factory=list)


class ShoppingListSummary(BaseModel):
    household_external_id: str
    household_name: str
    active_list: ShoppingListDetailSummary
    pending_lists: list[ShoppingListDetailSummary] = Field(default_factory=list)
    history_lists: list[ShoppingListDetailSummary] = Field(default_factory=list)
