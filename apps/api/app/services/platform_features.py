from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.feature_flag import FeatureFlag
from app.models.household import Household

FLAG_AI_SUGGESTIONS = "ai_household_suggestions"
FLAG_RECIPE_URL_IMPORTS = "recipe_url_imports"
FLAG_REVIEWED_IMPORTS = "reviewed_imports"
FLAG_USAGE_METERING = "usage_metering"
FLAG_DEMO_RESET = "demo_reset"
FLAG_HOSTED_BILLING = "hosted_billing"

FEATURE_DEFAULTS: dict[str, dict[str, bool]] = {
    FLAG_AI_SUGGESTIONS: {
        "self_hosted": True,
        "demo": True,
        "saas": True,
    },
    FLAG_RECIPE_URL_IMPORTS: {
        "self_hosted": True,
        "demo": True,
        "saas": True,
    },
    FLAG_REVIEWED_IMPORTS: {
        "self_hosted": True,
        "demo": True,
        "saas": True,
    },
    FLAG_USAGE_METERING: {
        "self_hosted": True,
        "demo": True,
        "saas": True,
    },
    FLAG_DEMO_RESET: {
        "self_hosted": False,
        "demo": False,
        "saas": False,
    },
    FLAG_HOSTED_BILLING: {
        "self_hosted": False,
        "demo": False,
        "saas": False,
    },
}


@dataclass(frozen=True)
class FeatureGateDecision:
    flag_key: str
    enabled: bool
    source: str
    reason: str
    note: str | None = None


def _build_scope_filter(*, flag_key: str, scope_type: str, scope_key: str):
    return (
        select(FeatureFlag)
        .where(FeatureFlag.flag_key == flag_key)
        .where(FeatureFlag.scope_type == scope_type)
        .where(FeatureFlag.scope_key == scope_key)
    )


def _default_feature_enabled(flag_key: str) -> bool:
    settings = get_settings()
    defaults = FEATURE_DEFAULTS.get(flag_key)
    if defaults is None:
        raise ValueError(f"Unknown feature flag {flag_key}.")
    return defaults[settings.deployment_mode]


def get_effective_feature_flag(
    db: Session,
    *,
    flag_key: str,
    household: Household | None = None,
) -> FeatureGateDecision:
    if household is not None:
        record = db.scalar(
            _build_scope_filter(
                flag_key=flag_key,
                scope_type="household",
                scope_key=household.external_id,
            )
        )
        if record is not None:
            return FeatureGateDecision(
                flag_key=flag_key,
                enabled=record.is_enabled,
                source="household_override",
                reason="Resolved from a household-scoped override.",
                note=record.note,
            )

    record = db.scalar(
        _build_scope_filter(
            flag_key=flag_key,
            scope_type="instance",
            scope_key="instance",
        )
    )
    if record is not None:
        return FeatureGateDecision(
            flag_key=flag_key,
            enabled=record.is_enabled,
            source="instance_override",
            reason="Resolved from an instance-scoped override.",
            note=record.note,
        )

    enabled = _default_feature_enabled(flag_key)
    return FeatureGateDecision(
        flag_key=flag_key,
        enabled=enabled,
        source="deployment_default",
        reason=f"Resolved from the {get_settings().deployment_mode} deployment default.",
    )


def require_feature_enabled(
    db: Session,
    *,
    flag_key: str,
    household: Household | None = None,
    disabled_message: str | None = None,
) -> None:
    decision = get_effective_feature_flag(db, flag_key=flag_key, household=household)
    if decision.enabled:
        return
    raise ValueError(disabled_message or f"Feature {flag_key} is disabled.")


def upsert_feature_flag(
    db: Session,
    *,
    flag_key: str,
    is_enabled: bool,
    note: str | None = None,
    scope_type: str = "instance",
    scope_key: str = "instance",
) -> FeatureFlag:
    _default_feature_enabled(flag_key)
    record = db.scalar(
        _build_scope_filter(
            flag_key=flag_key,
            scope_type=scope_type,
            scope_key=scope_key,
        )
    )
    if record is None:
        record = FeatureFlag(
            flag_key=flag_key,
            scope_type=scope_type,
            scope_key=scope_key,
            is_enabled=is_enabled,
            note=note,
        )
    else:
        record.is_enabled = is_enabled
        record.note = note

    db.add(record)
    db.commit()
    db.refresh(record)
    return record
