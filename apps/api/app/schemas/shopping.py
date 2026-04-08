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


class ShoppingListSummary(BaseModel):
    external_id: str
    household_external_id: str
    household_name: str
    name: str
    open_item_count: int
    completed_item_count: int
    items: list[ShoppingListItemSummary] = Field(default_factory=list)
