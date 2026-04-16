from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.domain.ai import AI_HEALTH_HEALTHY
from app.models.ai_provider_config import AIProviderConfig
from app.models.household import Household
from app.models.import_job import ImportJob
from app.models.instance_setting import InstanceSetting
from app.models.membership import Membership
from app.models.recipe import Recipe
from app.models.user import User
from app.models.usage_counter import UsageCounter
from app.services.ai_config import upsert_instance_provider_config
from app.services.auth import create_household, create_membership, create_platform_admin, create_user
from app.services.instance_settings import (
    record_smtp_test_result,
    upsert_password_reset_email_template,
    upsert_public_base_url,
    upsert_smtp_settings,
)
from app.services.ai_providers import AIProviderHealth
from app.services.secrets import encrypt_secret
from app.services.pantry_catalog import create_location, create_location_group, create_product
from app.services.pantry_normalization import normalize_lookup_name
from app.services.pantry_stock import add_stock_lot
from app.services.releases import ReleaseMetadata
from app.services.runtime_status import RedisHealthSnapshot
from app.services.smtp import SMTPTestResult


PASSWORD = "correct horse battery"


def login(client, *, email: str, password: str = PASSWORD) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("provider_type", "base_url", "default_model", "api_key"),
    [
        ("openai", "https://api.openai.com/v1", "gpt-5.4-mini", "openai-secret"),
        ("claude", "https://api.anthropic.com", "claude-sonnet-4-6", "claude-secret"),
        ("gemini", "https://generativelanguage.googleapis.com", "gemini-2.5-flash", "gemini-secret"),
        ("ollama", "http://localhost:11434", "qwen3:8b", None),
    ],
)
def test_platform_admin_ai_provider_config_saves_supported_providers(
    client, db_session, provider_type, base_url, default_model, api_key
):
    create_platform_admin(
        db_session,
        email="ai-admin@example.com",
        password=PASSWORD,
        display_name="AI Admin",
    )
    login(client, email="ai-admin@example.com")

    response = client.put(
        "/api/platform-admin/ai/provider-config",
        json={
            "provider_type": provider_type,
            "base_url": base_url,
            "default_model": default_model,
            "api_key": api_key,
            "is_enabled": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["config"]["provider_type"] == provider_type
    assert payload["config"]["base_url"] == base_url
    assert payload["config"]["default_model"] == default_model
    assert payload["config"]["has_api_key"] is bool(api_key)
    assert "api_key" not in payload["config"]
    if api_key:
        assert api_key not in json.dumps(payload)

    stored = db_session.scalar(select(AIProviderConfig))
    assert stored is not None
    assert stored.provider_type == provider_type
    assert stored.base_url == base_url
    assert stored.default_model == default_model
    assert bool(stored.encrypted_api_key) is bool(api_key)
    if api_key:
        assert stored.encrypted_api_key != api_key


@pytest.mark.parametrize(
    ("provider_type", "base_url", "default_model", "api_key"),
    [
        ("openai", "https://api.openai.com/v1", "gpt-5.4-mini", "openai-secret"),
        ("claude", "https://api.anthropic.com", "claude-sonnet-4-6", "claude-secret"),
        ("gemini", "https://generativelanguage.googleapis.com", "gemini-2.5-flash", "gemini-secret"),
        ("ollama", "http://localhost:11434", "qwen3:8b", None),
    ],
)
def test_platform_admin_ai_health_check_supports_all_built_in_providers(
    client, db_session, monkeypatch, provider_type, base_url, default_model, api_key
):
    create_platform_admin(
        db_session,
        email="ai-health@example.com",
        password=PASSWORD,
        display_name="AI Health Admin",
    )
    login(client, email="ai-health@example.com")

    save_response = client.put(
        "/api/platform-admin/ai/provider-config",
        json={
            "provider_type": provider_type,
            "base_url": base_url,
            "default_model": default_model,
            "api_key": api_key,
            "is_enabled": True,
        },
    )
    assert save_response.status_code == 200

    seen: dict[str, str] = {}

    class StubProviderAdapter:
        def __init__(self, runtime_config):
            seen["provider_type"] = runtime_config.provider_type

        def check_health(self):
            return AIProviderHealth(
                is_healthy=True,
                status=AI_HEALTH_HEALTHY,
                message=None,
                models=[default_model],
                capabilities={"supports_model_listing": True, "supports_structured_output": True},
            )

    monkeypatch.setattr("app.services.ai_config.build_ai_provider_adapter", StubProviderAdapter)

    response = client.post("/api/platform-admin/ai/provider-config/health-check", json={})
    assert response.status_code == 200
    payload = response.json()

    assert seen["provider_type"] == provider_type
    assert payload["config"]["provider_type"] == provider_type
    assert payload["health"]["is_healthy"] is True
    assert payload["health"]["models"] == [default_model]


def test_platform_admin_ai_provider_config_normalizes_legacy_openai_compatible_records(
    client, db_session, monkeypatch
):
    create_platform_admin(
        db_session,
        email="ai-legacy@example.com",
        password=PASSWORD,
        display_name="AI Legacy Admin",
    )
    db_session.add(
        AIProviderConfig(
            scope_type="instance",
            scope_key="instance",
            provider_type="openai_compatible",
            base_url="https://api.openai.com/v1",
            default_model="gpt-5.4-mini",
            encrypted_api_key=encrypt_secret("legacy-openai-key"),
            is_enabled=True,
        )
    )
    db_session.commit()
    login(client, email="ai-legacy@example.com")

    response = client.get("/api/platform-admin/ai/provider-config")
    assert response.status_code == 200
    assert response.json()["config"]["provider_type"] == "openai"

    seen: dict[str, str] = {}

    class StubProviderAdapter:
        def __init__(self, runtime_config):
            seen["provider_type"] = runtime_config.provider_type

        def check_health(self):
            return AIProviderHealth(
                is_healthy=True,
                status=AI_HEALTH_HEALTHY,
                message=None,
                models=["gpt-5.4-mini"],
                capabilities={"supports_model_listing": True, "supports_structured_output": True},
            )

    monkeypatch.setattr("app.services.ai_config.build_ai_provider_adapter", StubProviderAdapter)

    health_response = client.post("/api/platform-admin/ai/provider-config/health-check", json={})
    assert health_response.status_code == 200
    assert seen["provider_type"] == "openai"
    assert health_response.json()["config"]["provider_type"] == "openai"


def test_platform_admin_ai_provider_config_get_does_not_expose_api_key(client, db_session):
    admin = create_platform_admin(
        db_session,
        email="ai-get-admin@example.com",
        password=PASSWORD,
        display_name="AI Get Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=admin,
        provider_type="openai",
        base_url="https://api.openai.com/v1",
        default_model="gpt-5.4-mini",
        api_key="openai-secret-value",
        is_enabled=True,
    )
    login(client, email="ai-get-admin@example.com")

    response = client.get("/api/platform-admin/ai/provider-config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["has_api_key"] is True
    assert "api_key" not in payload["config"]
    assert "openai-secret-value" not in json.dumps(payload)


def test_platform_admin_diagnostics_report_uses_measured_data(client, db_session, monkeypatch):
    admin = create_platform_admin(
        db_session,
        email="admin@example.com",
        password=PASSWORD,
        display_name="Admin",
    )
    member = create_user(
        db_session,
        email="member@example.com",
        password=PASSWORD,
        display_name="Member",
    )
    household = create_household(db_session, name="Diagnostics Household")
    create_membership(db_session, user=member, household=household, role_code="household_user")

    group = create_location_group(db_session, household=household, actor=member, name="Kitchen")
    location = create_location(
        db_session,
        household=household,
        actor=member,
        location_group_external_id=group.external_id,
        name="Fridge",
    )
    product = create_product(
        db_session,
        household=household,
        actor=member,
        name="Milk",
        default_unit="bottle",
        aliases=[],
        barcodes=[],
    )
    add_stock_lot(
        db_session,
        household=household,
        actor=member,
        product_external_id=product.external_id,
        location_external_id=location.external_id,
        quantity=Decimal("1.000"),
        note=None,
        purchased_on=None,
        expires_on=None,
    )
    db_session.add(
        Recipe(
            household_id=household.id,
            title="Tea",
            normalized_title=normalize_lookup_name("Tea"),
            notes=None,
            source_kind="manual",
        )
    )
    db_session.add(
        ImportJob(
            household_id=household.id,
            requested_by_user_id=member.id,
            source_type="upload",
            status="queued",
            source_label="receipt.csv",
            note=None,
        )
    )
    db_session.commit()

    upsert_instance_provider_config(
        db_session,
        actor=admin,
        provider_type="ollama",
        base_url="http://ollama.local:11434",
        default_model="llama3.2",
        api_key=None,
        is_enabled=True,
    )
    upsert_smtp_settings(
        db_session,
        actor=admin,
        host="smtp.example.com",
        port=587,
        username="mailer",
        password="super-secret",
        from_email="pantry@example.com",
        from_name="Pantro",
        security="starttls",
        is_enabled=True,
    )
    upsert_public_base_url(db_session, actor=admin, public_base_url="http://192.168.1.10")

    monkeypatch.setattr(
        "app.services.diagnostics.check_redis_health",
        lambda: RedisHealthSnapshot(status="ok", latency_ms=1.25, message=None),
    )
    monkeypatch.setattr(
        "app.services.diagnostics.read_worker_heartbeat",
        lambda: {
            "status": "ok",
            "service": "pantro-worker",
            "version": "0.1.0",
            "mode": "import-poller",
            "poll_interval_seconds": 30,
            "started_at": datetime.now(timezone.utc),
            "last_seen_at": datetime.now(timezone.utc),
        },
    )
    release_settings = replace(
        get_settings(),
        app_version="0.1.0",
        release_check_repository="example/pantry",
        release_check_metadata_url=None,
    )
    monkeypatch.setattr("app.services.releases.get_settings", lambda: release_settings)
    monkeypatch.setattr(
        "app.services.releases.fetch_latest_release_metadata",
        lambda _: ReleaseMetadata(
            tag_name="v0.1.1",
            version="0.1.1",
            name="Pantro v0.1.1",
            html_url="https://github.com/example/pantry/releases/tag/v0.1.1",
            published_at=datetime.now(timezone.utc),
        ),
    )

    login(client, email="admin@example.com")
    response = client.get("/api/platform-admin/diagnostics")
    assert response.status_code == 200
    payload = response.json()

    assert payload["policy"] == "real_data_only"
    assert payload["counts"]["households"] == 1
    assert payload["counts"]["users"] == 2
    assert payload["counts"]["products"] == 1
    assert payload["counts"]["stock_lots"] == 1
    assert payload["counts"]["recipes"] == 1
    assert payload["counts"]["import_jobs"] == 1
    assert payload["worker"]["status"] == "ok"
    assert payload["redis"]["status"] == "ok"
    assert payload["queue"]["queued_import_jobs"] == 1
    assert payload["smtp"]["configured"] is True
    assert payload["release_check"]["status"] == "update_available"
    assert payload["release_check"]["latest_version"] == "0.1.1"
    assert payload["smtp"]["effective"]["has_password"] is True
    assert "password" not in payload["smtp"]["effective"]
    assert "password" not in payload["smtp"]["stored"]
    assert payload["public_base_url"]["effective_value"] == "http://192.168.1.10"
    assert len(payload["limitations"]) >= 2


def test_platform_admin_smtp_save_and_test_redacts_password(client, db_session, monkeypatch):
    admin = create_platform_admin(
        db_session,
        email="smtp-admin@example.com",
        password=PASSWORD,
        display_name="SMTP Admin",
    )
    login(client, email="smtp-admin@example.com")

    save_response = client.put(
        "/api/platform-admin/smtp",
        json={
            "host": "smtp.example.com",
            "port": 465,
            "username": "mailer",
            "password": "replace-me",
            "from_email": "pantry@example.com",
            "from_name": "Pantro",
            "security": "ssl",
            "is_enabled": True,
        },
    )
    assert save_response.status_code == 200
    save_payload = save_response.json()
    assert save_payload["effective"]["has_password"] is True
    assert "password" not in save_payload["effective"]

    stored = db_session.scalar(select(InstanceSetting).where(InstanceSetting.scope_key == "instance"))
    assert stored is not None
    assert stored.encrypted_smtp_password is not None
    assert stored.encrypted_smtp_password != "replace-me"

    monkeypatch.setattr(
        "app.api.routes.smtp_admin.run_smtp_connectivity_test",
        lambda db: SMTPTestResult(status="passed", ok=True, message="250 OK"),
    )
    test_response = client.post("/api/platform-admin/smtp/test", json={})
    assert test_response.status_code == 200
    test_payload = test_response.json()
    assert test_payload["ok"] is True
    assert test_payload["config"]["last_test_status"] == "passed"


def test_platform_admin_smtp_validation_rejects_url_like_hosts(client, db_session):
    create_platform_admin(
        db_session,
        email="smtp-validation@example.com",
        password=PASSWORD,
        display_name="SMTP Validation Admin",
    )
    login(client, email="smtp-validation@example.com")

    response = client.put(
        "/api/platform-admin/smtp",
        json={
            "host": "smtp://smtp.example.com",
            "port": 587,
            "from_email": "pantry@example.com",
            "security": "starttls",
            "is_enabled": True,
        },
    )
    assert response.status_code == 400
    assert "must not include a path" in response.json()["detail"] or "hostname or IP address" in response.json()["detail"]


def test_platform_admin_smtp_validation_requires_reset_link_placeholder(client, db_session):
    create_platform_admin(
        db_session,
        email="smtp-template@example.com",
        password=PASSWORD,
        display_name="SMTP Template Admin",
    )
    login(client, email="smtp-template@example.com")

    save_response = client.put(
        "/api/platform-admin/smtp",
        json={
            "host": "smtp.example.com",
            "port": 587,
            "from_email": "pantry@example.com",
            "security": "starttls",
            "is_enabled": True,
        },
    )
    assert save_response.status_code == 200

    response = client.put(
        "/api/platform-admin/smtp/templates/password_reset",
        json={
            "is_enabled": True,
            "subject": "Reset your password",
            "body_template": "This template forgot the reset link.",
        },
    )
    assert response.status_code == 400
    assert "{{reset_link}}" in response.json()["detail"]


def test_platform_admin_can_toggle_smtp_template_enabled_state(client, db_session):
    create_platform_admin(
        db_session,
        email="smtp-toggle@example.com",
        password=PASSWORD,
        display_name="SMTP Toggle Admin",
    )
    login(client, email="smtp-toggle@example.com")

    disabled = client.post(
        "/api/platform-admin/smtp/templates/password_reset/toggle",
        json={"is_enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["templates"][0]["is_enabled"] is False

    enabled = client.post(
        "/api/platform-admin/smtp/templates/password_reset/toggle",
        json={"is_enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["templates"][0]["is_enabled"] is True


def test_platform_admin_can_create_users_households_and_memberships(client, db_session):
    admin = create_platform_admin(
        db_session,
        email="management-admin@example.com",
        password=PASSWORD,
        display_name="Management Admin",
    )
    login(client, email="management-admin@example.com")

    create_user_response = client.post(
        "/api/platform-admin/users",
        json={
            "email": "managed-user@example.com",
            "display_name": "Managed User",
            "password": PASSWORD,
        },
    )
    assert create_user_response.status_code == 201
    created_user = create_user_response.json()
    assert created_user["membership_count"] == 0

    create_household_response = client.post(
        "/api/platform-admin/households",
        json={"name": "Managed Household"},
    )
    assert create_household_response.status_code == 201
    created_household = create_household_response.json()
    assert created_household["membership_count"] == 0

    membership_response = client.post(
        f"/api/platform-admin/households/{created_household['external_id']}/memberships",
        json={
            "user_external_id": created_user["external_id"],
            "role": "household_admin",
        },
    )
    assert membership_response.status_code == 200
    membership_payload = membership_response.json()
    assert membership_payload["email"] == "managed-user@example.com"
    assert membership_payload["role"] == "household_admin"

    households_response = client.get("/api/platform-admin/households")
    assert households_response.status_code == 200
    household_payload = households_response.json()[0]
    assert household_payload["memberships"][0]["email"] == "managed-user@example.com"


def test_platform_admin_can_update_users_and_send_reset_email(client, db_session, monkeypatch):
    admin = create_platform_admin(
        db_session,
        email="management-admin@example.com",
        password=PASSWORD,
        display_name="Management Admin",
    )
    managed_user = create_user(
        db_session,
        email="managed-user@example.com",
        password=PASSWORD,
        display_name="Managed User",
    )
    household = create_household(db_session, name="Managed Household")
    create_membership(db_session, user=managed_user, household=household, role_code="household_user")

    upsert_smtp_settings(
        db_session,
        actor=admin,
        host="smtp.example.com",
        port=587,
        username="mailer",
        password="top-secret",
        from_email="pantry@example.com",
        from_name="Pantro",
        security="starttls",
        is_enabled=True,
    )
    upsert_password_reset_email_template(
        db_session,
        actor=admin,
        is_enabled=True,
        subject=None,
        body_template=None,
    )
    record_smtp_test_result(db_session, actor=admin, status="passed", error=None)

    sent_messages: list[str] = []
    monkeypatch.setattr(
        "app.services.password_resets.send_email",
        lambda *args, **kwargs: sent_messages.append(kwargs["to_email"]),
    )

    login(client, email="management-admin@example.com")

    update_response = client.patch(
        f"/api/platform-admin/users/{managed_user.external_id}",
        json={
          "email": "managed-user-renamed@example.com",
          "display_name": "Managed User Renamed",
          "platform_role": "platform_admin",
          "memberships": [
              {
                  "household_external_id": household.external_id,
                  "role": "household_admin",
              }
          ],
        },
    )
    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["email"] == "managed-user-renamed@example.com"
    assert payload["platform_role"] == "platform_admin"
    assert payload["memberships"][0]["role"] == "household_admin"

    reset_response = client.post(
        f"/api/platform-admin/users/{managed_user.external_id}/send-password-reset",
        json={},
    )
    assert reset_response.status_code == 200
    assert sent_messages == ["managed-user-renamed@example.com"]


def test_platform_admin_can_delete_managed_user_with_confirmation(client, db_session):
    create_platform_admin(
        db_session,
        email="delete-admin@example.com",
        password=PASSWORD,
        display_name="Delete Admin",
    )
    managed_user = create_user(
        db_session,
        email="delete-me@example.com",
        password=PASSWORD,
        display_name="Delete Me",
    )
    household = create_household(db_session, name="Delete Household")
    create_membership(db_session, user=managed_user, household=household, role_code="household_user")
    db_session.commit()

    login(client, email="delete-admin@example.com")

    response = client.request(
        "DELETE",
        f"/api/platform-admin/users/{managed_user.external_id}",
        json={"confirm_user_email": "delete-me@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User deleted."

    managed_user_id = managed_user.id
    db_session.expire_all()
    assert db_session.scalar(select(User).where(User.id == managed_user_id)) is None
    assert db_session.scalar(select(Membership).where(Membership.user_id == managed_user_id)) is None


def test_platform_admin_delete_user_surfaces_last_household_admin_guard(client, db_session):
    create_platform_admin(
        db_session,
        email="delete-guard-admin@example.com",
        password=PASSWORD,
        display_name="Delete Guard Admin",
    )
    guarded_user = create_user(
        db_session,
        email="last-household-admin@example.com",
        password=PASSWORD,
        display_name="Guarded Admin",
    )
    household = create_household(db_session, name="Guarded Delete Household")
    create_membership(db_session, user=guarded_user, household=household, role_code="household_admin")
    db_session.commit()

    login(client, email="delete-guard-admin@example.com")

    response = client.request(
        "DELETE",
        f"/api/platform-admin/users/{guarded_user.external_id}",
        json={"confirm_user_email": "last-household-admin@example.com"},
    )
    assert response.status_code == 400
    assert "must keep at least one household admin" in response.json()["detail"]


def test_platform_admin_can_rename_households(client, db_session):
    create_platform_admin(
        db_session,
        email="rename-admin@example.com",
        password=PASSWORD,
        display_name="Rename Admin",
    )
    household = create_household(db_session, name="Original Household")

    login(client, email="rename-admin@example.com")

    response = client.patch(
        f"/api/platform-admin/households/{household.external_id}",
        json={"name": "Renamed Household"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Household"

    db_session.expire_all()
    renamed_household = db_session.scalar(select(Household).where(Household.id == household.id))
    assert renamed_household is not None
    assert renamed_household.name == "Renamed Household"


def test_platform_admin_blocks_removing_or_demoting_the_last_household_admin(client, db_session):
    admin = create_platform_admin(
        db_session,
        email="guard-admin@example.com",
        password=PASSWORD,
        display_name="Guard Admin",
    )
    guarded_user = create_user(
        db_session,
        email="guarded-member@example.com",
        password=PASSWORD,
        display_name="Guarded Member",
    )
    household = create_household(db_session, name="Guarded Household")
    membership = create_membership(
        db_session,
        user=guarded_user,
        household=household,
        role_code="household_admin",
    )
    db_session.commit()

    login(client, email="guard-admin@example.com")

    remove_response = client.post(
        f"/api/platform-admin/households/{household.external_id}/memberships/{membership.external_id}/remove",
        json={},
    )
    assert remove_response.status_code == 400
    assert remove_response.json()["detail"] == "Each household must keep at least one household admin."

    demote_response = client.post(
        f"/api/platform-admin/households/{household.external_id}/memberships",
        json={
            "user_external_id": guarded_user.external_id,
            "role": "household_user",
        },
    )
    assert demote_response.status_code == 400
    assert demote_response.json()["detail"] == "Each household must keep at least one household admin."


def test_platform_admin_can_export_and_restore_instance_backups(client, db_session):
    admin = create_platform_admin(
        db_session,
        email="backup-admin@example.com",
        password=PASSWORD,
        display_name="Backup Admin",
    )
    member = create_user(
        db_session,
        email="backup-member@example.com",
        password=PASSWORD,
        display_name="Backup Member",
    )
    household = create_household(db_session, name="Backup Household")
    create_membership(db_session, user=member, household=household, role_code="household_user")
    db_session.commit()

    login(client, email="backup-admin@example.com")

    export_response = client.get("/api/platform-admin/backups/export/instance")
    assert export_response.status_code == 200
    backup_bundle = json.loads(export_response.text)
    assert backup_bundle["format"] == "pantry.backup.bundle"
    assert backup_bundle["scope"] == "instance"

    extra_user = create_user(
        db_session,
        email="extra-user@example.com",
        password=PASSWORD,
        display_name="Extra User",
    )
    extra_household = create_household(db_session, name="Extra Household")
    create_membership(db_session, user=extra_user, household=extra_household, role_code="household_user")
    db_session.commit()
    assert db_session.scalar(select(func.count(User.id))) == 3

    upload_response = client.post(
        "/api/platform-admin/backups/restore-upload",
        files={"file": ("pantry-instance-backup.json", json.dumps(backup_bundle), "application/json")},
    )
    assert upload_response.status_code == 200
    staged_payload = upload_response.json()
    assert staged_payload["supported_for_restore"] is True
    assert staged_payload["bundle"]["scope"] == "instance"

    restore_response = client.post(
        "/api/platform-admin/backups/restore",
        json={
            "stage_id": staged_payload["stage_id"],
            "confirmation_phrase": "RESTORE PANTRY INSTANCE",
        },
    )
    assert restore_response.status_code == 200
    restore_payload = restore_response.json()
    assert restore_payload["restored"] is True
    assert restore_payload["requires_reauthentication"] is True

    restored_users = db_session.scalars(select(User).order_by(User.email)).all()
    assert [user.email for user in restored_users] == ["backup-admin@example.com", "backup-member@example.com"]
    assert db_session.scalar(select(func.count(Household.id))) == 1
    assert db_session.scalar(select(User).where(User.email == "extra-user@example.com")) is None
    assert db_session.scalar(select(Household).where(Household.name == "Extra Household")) is None


def test_platform_admin_can_restore_household_backup_into_a_new_household(client, db_session):
    admin = create_platform_admin(
        db_session,
        email="household-restore-admin@example.com",
        password=PASSWORD,
        display_name="Restore Admin",
    )
    member = create_user(
        db_session,
        email="household-member@example.com",
        password=PASSWORD,
        display_name="Restore Member",
    )
    source_household = create_household(db_session, name="Source Household")
    create_membership(db_session, user=member, household=source_household, role_code="household_admin")
    group = create_location_group(db_session, household=source_household, actor=member, name="Kitchen")
    location = create_location(
        db_session,
        household=source_household,
        actor=member,
        location_group_external_id=group.external_id,
        name="Fridge",
    )
    product = create_product(
        db_session,
        household=source_household,
        actor=member,
        name="Milk",
        default_unit="bottle",
        aliases=[],
        barcodes=[],
    )
    add_stock_lot(
        db_session,
        household=source_household,
        actor=member,
        product_external_id=product.external_id,
        location_external_id=location.external_id,
        quantity=Decimal("1.000"),
        note="Restored lot",
        purchased_on=None,
        expires_on=None,
    )
    db_session.commit()

    login(client, email="household-restore-admin@example.com")

    export_response = client.get(
        f"/api/platform-admin/backups/export/households/{source_household.external_id}"
    )
    assert export_response.status_code == 200
    backup_bundle = json.loads(export_response.text)
    assert backup_bundle["scope"] == "household"

    upload_response = client.post(
        "/api/platform-admin/households/restore-upload",
        files={"file": ("pantry-household-backup.json", json.dumps(backup_bundle), "application/json")},
    )
    assert upload_response.status_code == 200
    staged_payload = upload_response.json()
    assert staged_payload["supported_for_restore"] is True
    assert staged_payload["bundle"]["scope"] == "household"

    restore_response = client.post(
        "/api/platform-admin/households/restore",
        json={
            "stage_id": staged_payload["stage_id"],
            "target_household_name": "Restored Household",
            "confirmation_phrase": "RESTORE PANTRY HOUSEHOLD",
        },
    )
    assert restore_response.status_code == 200
    restore_payload = restore_response.json()
    assert restore_payload["restored"] is True
    assert restore_payload["bundle"]["household_name"] == "Restored Household"

    restored_household = db_session.scalar(
        select(Household).where(Household.name == "Restored Household")
    )
    assert restored_household is not None
    assert restored_household.external_id != source_household.external_id
    assert db_session.scalar(select(func.count(Household.id))) == 2
    assert (
        db_session.scalar(select(func.count(Membership.id)).where(Membership.household_id == restored_household.id))
        == 1
    )
    assert (
        db_session.scalar(select(func.count(ImportJob.id)).where(ImportJob.household_id == restored_household.id))
        == 0
    )
    assert db_session.scalar(select(func.count(Recipe.id)).where(Recipe.household_id == restored_household.id)) == 0


def test_platform_admin_household_restore_blocks_existing_target_name_conflicts(client, db_session):
    create_platform_admin(
        db_session,
        email="household-conflict-admin@example.com",
        password=PASSWORD,
        display_name="Conflict Admin",
    )
    member = create_user(
        db_session,
        email="conflict-member@example.com",
        password=PASSWORD,
        display_name="Conflict Member",
    )
    source_household = create_household(db_session, name="Conflict Source")
    create_membership(db_session, user=member, household=source_household, role_code="household_admin")
    create_household(db_session, name="Existing Household")
    db_session.commit()

    login(client, email="household-conflict-admin@example.com")

    export_response = client.get(
        f"/api/platform-admin/backups/export/households/{source_household.external_id}"
    )
    backup_bundle = json.loads(export_response.text)
    upload_response = client.post(
        "/api/platform-admin/households/restore-upload",
        files={"file": ("pantry-household-backup.json", json.dumps(backup_bundle), "application/json")},
    )
    staged_payload = upload_response.json()

    restore_response = client.post(
        "/api/platform-admin/households/restore",
        json={
            "stage_id": staged_payload["stage_id"],
            "target_household_name": "Existing Household",
            "confirmation_phrase": "RESTORE PANTRY HOUSEHOLD",
        },
    )
    assert restore_response.status_code == 400
    assert "already exists" in restore_response.json()["detail"]


def test_platform_admin_household_restore_accepts_supported_older_schema_bundle(client, db_session):
    create_platform_admin(
        db_session,
        email="older-household-admin@example.com",
        password=PASSWORD,
        display_name="Older Schema Admin",
    )
    member = create_user(
        db_session,
        email="older-household-member@example.com",
        password=PASSWORD,
        display_name="Older Schema Member",
    )
    source_household = create_household(db_session, name="Older Source")
    create_membership(db_session, user=member, household=source_household, role_code="household_admin")
    db_session.commit()

    login(client, email="older-household-admin@example.com")

    export_response = client.get(
        f"/api/platform-admin/backups/export/households/{source_household.external_id}"
    )
    backup_bundle = json.loads(export_response.text)
    backup_bundle["schema_revision"] = "20260407_000009"
    del backup_bundle["tables"]["product_enrichments"]
    del backup_bundle["tables"]["shopping_lists"]
    del backup_bundle["tables"]["shopping_list_items"]

    upload_response = client.post(
        "/api/platform-admin/households/restore-upload",
        files={"file": ("pantry-household-backup.json", json.dumps(backup_bundle), "application/json")},
    )
    assert upload_response.status_code == 200
    staged_payload = upload_response.json()
    assert staged_payload["supported_for_restore"] is True
    assert any("product enrichment support" in warning.lower() for warning in staged_payload["warnings"])

    restore_response = client.post(
        "/api/platform-admin/households/restore",
        json={
            "stage_id": staged_payload["stage_id"],
            "target_household_name": "Older Restored Household",
            "confirmation_phrase": "RESTORE PANTRY HOUSEHOLD",
        },
    )
    assert restore_response.status_code == 200
    restore_payload = restore_response.json()
    assert restore_payload["restored"] is True
    assert any("older Pantro schema" in warning for warning in restore_payload["warnings"])


def test_platform_admin_restore_upload_rejects_non_json_files(client, db_session):
    create_platform_admin(
        db_session,
        email="backup-validation@example.com",
        password=PASSWORD,
        display_name="Backup Validation Admin",
    )
    login(client, email="backup-validation@example.com")

    response = client.post(
        "/api/platform-admin/backups/restore-upload",
        files={"file": ("backup.sh", "#!/bin/sh\necho nope\n", "text/plain")},
    )
    assert response.status_code == 400
    assert ".json" in response.json()["detail"]


def test_platform_admin_can_remove_household_memberships_with_safeguards(client, db_session):
    admin = create_platform_admin(
        db_session,
        email="household-admin@example.com",
        password=PASSWORD,
        display_name="Household Admin",
    )
    removable_user = create_user(
        db_session,
        email="remove-me@example.com",
        password=PASSWORD,
        display_name="Remove Me",
    )
    household = create_household(db_session, name="Remove Test Household")
    protected_membership = create_membership(
        db_session,
        user=admin,
        household=household,
        role_code="household_admin",
    )
    removable_membership = create_membership(
        db_session,
        user=removable_user,
        household=household,
        role_code="household_user",
    )

    login(client, email="household-admin@example.com")

    remove_response = client.post(
        f"/api/platform-admin/households/{household.external_id}/memberships/{removable_membership.external_id}/remove",
        json={},
    )
    assert remove_response.status_code == 200
    assert db_session.scalar(select(Membership).where(Membership.id == removable_membership.id)) is None

    protected_response = client.post(
        f"/api/platform-admin/households/{household.external_id}/memberships/{protected_membership.external_id}/remove",
        json={},
    )
    assert protected_response.status_code == 400
    assert "at least one household admin" in protected_response.json()["detail"].lower()


def test_platform_admin_household_deletion_requires_confirmation_and_acknowledgement(client, db_session):
    admin = create_platform_admin(
        db_session,
        email="delete-admin@example.com",
        password=PASSWORD,
        display_name="Delete Admin",
    )
    household = create_household(db_session, name="Delete Me")
    create_membership(db_session, user=admin, household=household, role_code="household_admin")

    login(client, email="delete-admin@example.com")

    missing_ack_response = client.post(
        f"/api/platform-admin/households/{household.external_id}/delete",
        json={"confirm_household_name": "Delete Me", "acknowledge_last_household_deletion": False},
    )
    assert missing_ack_response.status_code == 400
    assert "last household" in missing_ack_response.json()["detail"].lower()

    wrong_name_response = client.post(
        f"/api/platform-admin/households/{household.external_id}/delete",
        json={"confirm_household_name": "Wrong", "acknowledge_last_household_deletion": True},
    )
    assert wrong_name_response.status_code == 400
    assert "exact household name" in wrong_name_response.json()["detail"].lower()

    delete_response = client.post(
        f"/api/platform-admin/households/{household.external_id}/delete",
        json={"confirm_household_name": "Delete Me", "acknowledge_last_household_deletion": True},
    )
    assert delete_response.status_code == 200
    assert db_session.scalar(select(Household).where(Household.id == household.id)) is None


def test_platform_admin_management_endpoints_require_platform_admin(client, db_session):
    member = create_user(
        db_session,
        email="non-admin@example.com",
        password=PASSWORD,
        display_name="Non Admin",
    )
    household = create_household(db_session, name="Member Household")
    create_membership(db_session, user=member, household=household, role_code="household_admin")

    login(client, email="non-admin@example.com")

    user_response = client.post(
        "/api/platform-admin/users",
        json={
            "email": "blocked@example.com",
            "display_name": "Blocked",
            "password": PASSWORD,
        },
    )
    assert user_response.status_code == 403

    household_response = client.post(
        "/api/platform-admin/households",
        json={"name": "Blocked Household"},
    )
    assert household_response.status_code == 403

    membership_response = client.post(
        f"/api/platform-admin/households/{household.external_id}/memberships",
        json={
            "user_external_id": member.external_id,
            "role": "household_user",
        },
    )
    assert membership_response.status_code == 403


def test_platform_admin_can_send_smtp_test_email(client, db_session, monkeypatch):
    admin = create_platform_admin(
        db_session,
        email="smtp-test-admin@example.com",
        password=PASSWORD,
        display_name="SMTP Test Admin",
    )
    login(client, email="smtp-test-admin@example.com")

    save_response = client.put(
        "/api/platform-admin/smtp",
        json={
            "host": "smtp.example.com",
            "port": 587,
            "username": "mailer",
            "password": "replace-me",
            "from_email": "pantry@example.com",
            "from_name": "Pantro",
            "test_recipient_email": "recipient@example.com",
            "security": "starttls",
            "is_enabled": True,
        },
    )
    assert save_response.status_code == 200

    delivered_to: list[str] = []
    monkeypatch.setattr(
        "app.api.routes.smtp_admin.send_smtp_test_email",
        lambda db: delivered_to.append("recipient@example.com") or "recipient@example.com",
    )

    response = client.post("/api/platform-admin/smtp/test-email", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["delivered_to"] == "recipient@example.com"
    assert delivered_to == ["recipient@example.com"]


def test_api_requests_record_usage_counters(client, db_session):
    response = client.get("/api/health")
    assert response.status_code == 200

    db_session.expire_all()
    counter = db_session.scalar(
        select(UsageCounter).where(
            UsageCounter.counter_key == "http_request:self_hosted:GET:/api/health:2xx"
        )
    )
    assert counter is not None
    assert counter.scope_type == "instance"
    assert counter.scope_key == "instance"
    assert counter.count == 1


def test_location_qr_links_use_configured_public_base_url_and_access_is_scoped(client, db_session):
    create_platform_admin(
        db_session,
        email="links-admin@example.com",
        password=PASSWORD,
        display_name="Links Admin",
    )
    member = create_user(
        db_session,
        email="links-member@example.com",
        password=PASSWORD,
        display_name="Links Member",
    )
    outsider = create_user(
        db_session,
        email="outsider@example.com",
        password=PASSWORD,
        display_name="Outsider",
    )
    household = create_household(db_session, name="Link Household")
    create_membership(db_session, user=member, household=household, role_code="household_user")

    group = create_location_group(db_session, household=household, actor=member, name="Kitchen")
    location = create_location(
        db_session,
        household=household,
        actor=member,
        location_group_external_id=group.external_id,
        name="Fridge",
    )

    login(client, email="links-member@example.com")
    initial_overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert initial_overview.status_code == 200
    initial_location = initial_overview.json()["locations"][0]
    assert initial_location["location_route"] == location.external_id
    assert initial_location["browser_url"] == f"http://testserver/locations/{location.external_id}"

    login(client, email="links-admin@example.com")
    update_response = client.put(
        "/api/platform-admin/settings/public-base-url",
        json={"public_base_url": "https://pantry.example.com"},
    )
    assert update_response.status_code == 200

    login(client, email="links-member@example.com")
    updated_overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert updated_overview.status_code == 200
    updated_location = updated_overview.json()["locations"][0]
    assert updated_location["browser_url"] == f"https://pantry.example.com/locations/{location.external_id}"

    access_response = client.get(f"/api/locations/{location.external_id}")
    assert access_response.status_code == 200
    access_payload = access_response.json()
    assert access_payload["browser_url"] == f"https://pantry.example.com/locations/{location.external_id}"
    assert access_payload["pantry_path"] == f"/app/households/{household.external_id}?location_external_id={location.external_id}"

    login(client, email="outsider@example.com")
    denied_response = client.get(f"/api/locations/{location.external_id}")
    assert denied_response.status_code == 404
