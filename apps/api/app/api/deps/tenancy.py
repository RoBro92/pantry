from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.db import get_db_session
from app.models.user import User
from app.services.tenancy import HouseholdAccess, resolve_household_access


def require_household_access(*, allowed_roles: set[str] | None = None) -> Callable[..., HouseholdAccess]:
    def dependency(
        household_external_id: str,
        db: Session = Depends(get_db_session),
        current_user: User = Depends(get_current_user),
    ) -> HouseholdAccess:
        access = resolve_household_access(
            db,
            household_external_id=household_external_id,
            user=current_user,
            allowed_roles=allowed_roles,
        )
        if access is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Household not found.")

        return access

    return dependency

