from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.identifiers import generate_external_id


class FeatureFlag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint("flag_key", "scope_type", "scope_key", name="uq_feature_flags_scope"),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("ffg"), unique=True, nullable=False
    )
    flag_key: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="instance")
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False, default="instance")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
