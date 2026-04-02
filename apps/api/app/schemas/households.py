from __future__ import annotations

from pydantic import BaseModel


class HouseholdSummaryResponse(BaseModel):
    external_id: str
    name: str
    effective_role: str
    can_administer: bool

