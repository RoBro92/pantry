from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.usage_counters import check_usage_quota


def test_get_settings_rejects_invalid_deployment_mode(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DEPLOYMENT_MODE", "unsupported")

    with pytest.raises(ValueError, match="DEPLOYMENT_MODE"):
        get_settings()

    monkeypatch.setenv("DEPLOYMENT_MODE", "self_hosted")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.deployment_mode == "self_hosted"


def test_quota_checks_are_placeholder_only(db_session):
    result = check_usage_quota(
        db_session,
        counter_key="reviewed_import_uploads",
        scope_type="household",
        scope_key="hou_test",
    )
    assert result.allowed is True
    assert result.enforced is False
    assert result.current_count == 0
    assert "not enabled" in (result.reason or "").lower()
