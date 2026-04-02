from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.roles import PLATFORM_ADMIN_ROLE
from app.models.user import User
from app.services.auth import get_user_by_external_id


def get_current_user(request: Request, db: Session = Depends(get_db_session)) -> User:
    user_external_id = request.session.get("user_external_id")
    if not user_external_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    user = get_user_by_external_id(db, user_external_id)
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid.")

    return user


def require_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.platform_role is None or current_user.platform_role.code != PLATFORM_ADMIN_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin access required.")

    return current_user

