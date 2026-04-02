from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps.tenancy import require_household_access
from app.schemas.households import HouseholdSummaryResponse
from app.services.tenancy import HouseholdAccess

router = APIRouter(prefix="/households", tags=["households"])


@router.get("/{household_external_id}", response_model=HouseholdSummaryResponse)
def get_household(access: HouseholdAccess = Depends(require_household_access())):
    return HouseholdSummaryResponse(
        external_id=access.household.external_id,
        name=access.household.name,
        effective_role=access.effective_role,
        can_administer=access.can_administer,
    )

