from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.role import Role


def get_role_by_code(db: Session, code: str) -> Role | None:
    return db.scalar(select(Role).where(Role.code == code))

