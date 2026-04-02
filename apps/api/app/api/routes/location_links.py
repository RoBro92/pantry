from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.core.db import get_db_session
from app.models.user import User
from app.schemas.location_links import LocationAccessResponse
from app.services.location_links import build_location_access_response

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/{location_route}", response_model=LocationAccessResponse)
def get_location_access(
    location_route: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    payload = build_location_access_response(db, location_route=location_route, user=current_user)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found.")
    return LocationAccessResponse.model_validate(payload)
