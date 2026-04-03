from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from app.models.identifiers import generate_external_id


class UsageCounter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint(
            "counter_key",
            "scope_type",
            "scope_key",
            "period_start",
            name="uq_usage_counters_scope_period",
        ),
    )

    external_id: Mapped[str] = mapped_column(
        String(32), default=lambda: generate_external_id("uct"), unique=True, nullable=False
    )
    counter_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="instance")
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False, default="instance")
    period_start: Mapped[date] = mapped_column(Date(), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
