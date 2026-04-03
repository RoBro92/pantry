from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utc_now
from app.models.usage_counter import UsageCounter


@dataclass(frozen=True)
class QuotaCheckResult:
    counter_key: str
    scope_type: str
    scope_key: str
    current_count: int
    allowed: bool
    enforced: bool
    soft_limit: int | None
    reason: str | None


def get_usage_counter(
    db: Session,
    *,
    counter_key: str,
    scope_type: str,
    scope_key: str,
    period_start: date,
) -> UsageCounter | None:
    return db.scalar(
        select(UsageCounter)
        .where(UsageCounter.counter_key == counter_key)
        .where(UsageCounter.scope_type == scope_type)
        .where(UsageCounter.scope_key == scope_key)
        .where(UsageCounter.period_start == period_start)
    )


def increment_usage_counter(
    db: Session,
    *,
    counter_key: str,
    scope_type: str,
    scope_key: str,
    increment_by: int = 1,
    period_start: date | None = None,
) -> UsageCounter:
    bucket = period_start or utc_now().date()
    counter = get_usage_counter(
        db,
        counter_key=counter_key,
        scope_type=scope_type,
        scope_key=scope_key,
        period_start=bucket,
    )
    if counter is None:
        counter = UsageCounter(
            counter_key=counter_key,
            scope_type=scope_type,
            scope_key=scope_key,
            period_start=bucket,
            count=0,
        )

    counter.count += increment_by
    counter.last_recorded_at = utc_now()
    db.add(counter)
    db.flush()
    return counter


def check_usage_quota(
    db: Session,
    *,
    counter_key: str,
    scope_type: str,
    scope_key: str,
    period_start: date | None = None,
) -> QuotaCheckResult:
    bucket = period_start or utc_now().date()
    counter = get_usage_counter(
        db,
        counter_key=counter_key,
        scope_type=scope_type,
        scope_key=scope_key,
        period_start=bucket,
    )
    current_count = counter.count if counter is not None else 0
    return QuotaCheckResult(
        counter_key=counter_key,
        scope_type=scope_type,
        scope_key=scope_key,
        current_count=current_count,
        allowed=True,
        enforced=False,
        soft_limit=None,
        reason="Quota enforcement is intentionally not enabled in this milestone.",
    )
