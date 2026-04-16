from __future__ import annotations

import json

from sqlalchemy import delete, select

from app.domain.ai import AI_HEALTH_HEALTHY
from app.models import Base, Role
from app.models.ai_provider_config import AIProviderConfig
from app.models.household import Household
from app.models.instance_setting import InstanceSetting
from app.models.location import Location
from app.models.location_group import LocationGroup
from app.models.membership import Membership
from app.models.setup_state import SetupState
from app.models.user import User
from app.services.ai_providers import AIProviderHealth
from app.services.secrets import decrypt_secret
from app.services.smtp import SMTPTestResult


def _save_required_setup_steps(client):
    response = client.put("/api/setup/wizard/welcome", json={"acknowledged": True})
    assert response.status_code == 200

    response = client.put(
        "/api/setup/wizard/users",
        json={
            "admin_login": "owner",
            "admin_display_name": "Owner",
            "admin_password": "correct horse battery",
            "initial_users": [
                {
                    "stage_id": "user-1",
                    "login": "alex",
                    "display_name": "Alex",
                    "password": "correct horse battery",
                }
            ],
        },
    )
    assert response.status_code == 200

    response = client.put(
        "/api/setup/wizard/household",
        json={
            "household_name": "Brown Household",
            "location_group_name": "Kitchen",
            "storage_locations": ["Fridge", "Freezer", "Pantry shelf"],
            "household_assignments": [{"stage_user_id": "user-1", "role": "household_user"}],
        },
    )
    assert response.status_code == 200


def test_setup_status_reports_uninitialized_install(client):
    response = client.get("/api/setup/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_initialized"] is False
    assert payload["has_staged_progress"] is False
    assert payload["stage"] == "not_started"


def test_setup_wizard_persists_staged_progress(client):
    _save_required_setup_steps(client)

    response = client.get("/api/setup/wizard")
    assert response.status_code == 200
    payload = response.json()
    assert payload["welcome_acknowledged"] is True
    assert payload["admin_user"]["login"] == "owner"
    assert payload["admin_user"]["password_saved"] is True
    assert payload["initial_users"][0]["login"] == "alex"
    assert payload["household_name"] == "Brown Household"
    assert payload["rooms"] == [
        {
            "stage_id": "room-1",
            "name": "Kitchen",
            "storage_locations": ["Fridge", "Freezer", "Pantry shelf"],
        }
    ]
    assert payload["storage_locations"] == ["Fridge", "Freezer", "Pantry shelf"]
    assert payload["public_base_url"] is None
    assert payload["can_complete"] is True
    assert [step["key"] for step in payload["status"]["steps"]] == [
        "welcome",
        "users",
        "dietary",
        "household",
        "public_url",
        "ai",
        "smtp",
        "review",
    ]
    assert payload["status"]["steps"][0]["title"] == "Install selection"
    step_states = {step["key"]: step["is_complete"] for step in payload["status"]["steps"]}
    assert step_states["welcome"] is True
    assert step_states["users"] is True
    assert step_states["dietary"] is False
    assert step_states["household"] is True
    assert step_states["public_url"] is False
    assert step_states["ai"] is False
    assert step_states["smtp"] is False


def test_setup_wizard_prefills_local_ai_and_smtp_from_env(client, db_session, monkeypatch):
    monkeypatch.setenv("PANTRY_LOCAL_AI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("PANTRY_LOCAL_AI_DEFAULT_MODEL", "gpt-5.4-mini")
    monkeypatch.setenv("PANTRY_LOCAL_AI_API_KEY", "openai-local-test-key")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PORT", "587")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_USERNAME", "mailer")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_FROM_EMAIL", "pantro@example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_FROM_NAME", "Pantro")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_SECURITY", "starttls")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_ENABLED", "true")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PASSWORD_RESET_ENABLED", "true")

    response = client.get("/api/setup/wizard")
    assert response.status_code == 200

    payload = response.json()
    assert payload["ai_config"] == {
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-5.4-mini",
        "is_enabled": True,
        "has_api_key": True,
    }
    assert payload["smtp_config"] == {
        "host": "smtp.example.com",
        "port": 587,
        "username": "mailer",
        "has_password": True,
        "from_email": "pantro@example.com",
        "from_name": "Pantro",
        "security": "starttls",
        "is_enabled": True,
        "password_reset_enabled": True,
    }

    save_response = client.put("/api/setup/wizard/welcome", json={"acknowledged": True})
    assert save_response.status_code == 200

    setup_state = db_session.scalar(select(SetupState))
    assert setup_state is not None
    assert decrypt_secret(setup_state.encrypted_ai_api_key) == "openai-local-test-key"
    assert decrypt_secret(setup_state.encrypted_smtp_password) == "smtp-password"


def test_setup_finalize_runs_initial_integration_checks_for_local_env(client, db_session, monkeypatch):
    monkeypatch.setenv("PANTRY_LOCAL_AI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("PANTRY_LOCAL_AI_DEFAULT_MODEL", "gpt-5.4-mini")
    monkeypatch.setenv("PANTRY_LOCAL_AI_API_KEY", "openai-local-test-key")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PORT", "587")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_USERNAME", "mailer")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_FROM_EMAIL", "pantro@example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_FROM_NAME", "Pantro")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_SECURITY", "starttls")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_ENABLED", "true")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_TEST_RECIPIENT_EMAIL", "test@example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PASSWORD_RESET_ENABLED", "true")

    def stub_refresh_provider_health(db, config):
        del db
        config.health_status = AI_HEALTH_HEALTHY
        config.health_error = None
        config.available_model_count = 1
        config.capabilities = {"supports_structured_output": True}
        return AIProviderHealth(
            is_healthy=True,
            status=AI_HEALTH_HEALTHY,
            message=None,
            models=["gpt-5.4-mini"],
            capabilities={"supports_structured_output": True},
        )

    monkeypatch.setattr(
        "app.services.instance_integration_checks.refresh_provider_health",
        stub_refresh_provider_health,
    )
    monkeypatch.setattr(
        "app.services.instance_integration_checks.run_smtp_connectivity_test",
        lambda db: SMTPTestResult(status="passed", ok=True, message="250 OK"),
    )

    _save_required_setup_steps(client)

    finalize_response = client.post("/api/setup/wizard/finalize")
    assert finalize_response.status_code == 200

    ai_config = db_session.scalar(select(AIProviderConfig))
    assert ai_config is not None
    assert ai_config.health_status == AI_HEALTH_HEALTHY

    instance_settings = db_session.scalar(select(InstanceSetting))
    assert instance_settings is not None
    assert instance_settings.smtp_host == "smtp.example.com"
    assert instance_settings.smtp_test_recipient_email == "test@example.com"
    assert instance_settings.password_reset_enabled is True
    assert instance_settings.smtp_last_test_status == "passed"


def test_setup_household_step_supports_multiple_rooms_and_persists_them(client):
    response = client.put(
        "/api/setup/wizard/household",
        json={
            "household_name": "Brown Household",
            "rooms": [
                {
                    "stage_id": "room-kitchen",
                    "name": "Kitchen",
                    "storage_locations": ["Fridge", "Pantry shelf"],
                },
                {
                    "stage_id": "room-garage",
                    "name": "Garage",
                    "storage_locations": ["Freezer", "Bulk rack"],
                },
            ],
            "household_assignments": [],
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["rooms"] == [
        {
            "stage_id": "room-kitchen",
            "name": "Kitchen",
            "storage_locations": ["Fridge", "Pantry shelf"],
        },
        {
            "stage_id": "room-garage",
            "name": "Garage",
            "storage_locations": ["Freezer", "Bulk rack"],
        },
    ]
    assert payload["location_group_name"] == "Kitchen"
    assert payload["storage_locations"] == ["Fridge", "Pantry shelf"]
    step_states = {step["key"]: step["is_complete"] for step in payload["status"]["steps"]}
    assert step_states["household"] is True


def test_setup_users_endpoint_persists_incomplete_additional_users(client):
    response = client.put(
        "/api/setup/wizard/users",
        json={
            "admin_login": "owner",
            "admin_display_name": "Owner",
            "admin_password": "correct horse battery",
            "initial_users": [
                {
                    "stage_id": "user-blank",
                    "login": "",
                    "display_name": "Later User",
                    "password": None,
                }
            ],
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["initial_users"] == [
        {
            "stage_id": "user-blank",
            "login": "",
            "display_name": "Later User",
            "password_saved": False,
            "is_platform_admin": False,
        }
    ]
    assert payload["can_complete"] is False
    step_states = {step["key"]: step["is_complete"] for step in payload["status"]["steps"]}
    assert step_states["users"] is False


def test_setup_public_url_can_be_cleared_without_marking_step_complete(client):
    response = client.put(
        "/api/setup/wizard/public-url",
        json={"public_base_url": ""},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["public_base_url"] is None
    step_states = {step["key"]: step["is_complete"] for step in payload["status"]["steps"]}
    assert step_states["public_url"] is False


def test_setup_optional_steps_can_be_marked_skipped_and_report_complete(client):
    response = client.put(
        "/api/setup/wizard/public-url",
        json={"public_base_url": "", "mark_skipped": True},
    )
    assert response.status_code == 200

    response = client.put(
        "/api/setup/wizard/dietary",
        json={
            "household_preferences": [],
            "user_preferences": [],
            "mark_skipped": True,
        },
    )
    assert response.status_code == 200

    response = client.put(
        "/api/setup/wizard/ai",
        json={
            "provider_type": None,
            "base_url": None,
            "default_model": None,
            "api_key": None,
            "is_enabled": False,
            "mark_skipped": True,
        },
    )
    assert response.status_code == 200

    response = client.put(
        "/api/setup/wizard/smtp",
        json={
            "host": None,
            "port": None,
            "username": None,
            "password": None,
            "from_email": None,
            "from_name": None,
            "security": None,
            "is_enabled": False,
            "mark_skipped": True,
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert sorted(payload["skipped_optional_steps"]) == ["ai", "dietary", "public_url", "smtp"]
    step_states = {step["key"]: step["is_complete"] for step in payload["status"]["steps"]}
    assert step_states["public_url"] is True
    assert step_states["dietary"] is True
    assert step_states["ai"] is True
    assert step_states["smtp"] is True


def test_setup_dietary_none_counts_as_complete_without_persisting_fake_preferences(client, db_session):
    _save_required_setup_steps(client)

    response = client.put(
        "/api/setup/wizard/dietary",
        json={
            "household_preferences": ["None", "Vegan"],
            "user_preferences": [{"stage_user_id": "user-1", "preferences": ["None", "Dairy-free"]}],
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["household_dietary_preferences"] == ["None"]
    assert payload["user_dietary_preferences"] == [
        {
            "stage_user_id": "user-1",
            "preferences": ["None"],
        }
    ]
    step_states = {step["key"]: step["is_complete"] for step in payload["status"]["steps"]}
    assert step_states["dietary"] is True

    finalize_response = client.post("/api/setup/wizard/finalize")
    assert finalize_response.status_code == 200

    users = db_session.scalars(select(User).order_by(User.email)).all()
    assert users[0].dietary_preferences is None

    household = db_session.scalar(select(Household))
    assert household is not None
    assert household.dietary_preferences is None


def test_setup_finalize_commits_all_staged_data_and_authenticates(client, db_session):
    _save_required_setup_steps(client)

    response = client.put(
        "/api/setup/wizard/public-url",
        json={"public_base_url": "https://pantro.example.com"},
    )
    assert response.status_code == 200

    response = client.put(
        "/api/setup/wizard/dietary",
        json={
            "household_preferences": ["vegetarian", "nut allergy"],
            "user_preferences": [{"stage_user_id": "user-1", "preferences": ["dairy-free"]}],
        },
    )
    assert response.status_code == 200

    response = client.put(
        "/api/setup/wizard/ai",
        json={
            "provider_type": "ollama",
            "base_url": "http://ollama.local:11434",
            "default_model": "llama3.2",
            "is_enabled": True,
        },
    )
    assert response.status_code == 200

    response = client.put(
        "/api/setup/wizard/smtp",
        json={
            "host": "smtp.example.com",
            "port": 587,
            "username": "mailer",
            "password": "smtp-password",
            "from_email": "pantro@example.com",
            "from_name": "Pantro",
            "security": "starttls",
            "is_enabled": True,
        },
    )
    assert response.status_code == 200

    finalize_response = client.post("/api/setup/wizard/finalize")
    assert finalize_response.status_code == 200
    payload = finalize_response.json()
    assert payload["user"]["email"] == "owner"
    assert payload["user"]["platform_role"] == "platform_admin"

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["user"]["email"] == "owner"
    assert len(session_response.json()["memberships"]) == 1

    setup_status = client.get("/api/setup/status").json()
    assert setup_status["is_initialized"] is True
    assert setup_status["stage"] == "completed"

    users = db_session.scalars(select(User).order_by(User.email)).all()
    assert [user.email for user in users] == ["alex", "owner"]
    assert users[0].dietary_preferences == ["dairy-free"]

    household = db_session.scalar(select(Household))
    assert household is not None
    assert household.name == "Brown Household"
    assert household.dietary_preferences == ["vegetarian", "nut allergy"]

    memberships = db_session.scalars(select(Membership)).all()
    assert len(memberships) == 2

    locations = db_session.scalars(select(Location).order_by(Location.name)).all()
    assert [location.name for location in locations] == ["Freezer", "Fridge", "Pantry shelf"]

    instance_settings = db_session.scalar(select(InstanceSetting))
    assert instance_settings is not None
    assert instance_settings.public_base_url == "https://pantro.example.com"
    assert instance_settings.smtp_host == "smtp.example.com"
    assert instance_settings.smtp_username == "mailer"
    assert instance_settings.encrypted_smtp_password is not None

    ai_config = db_session.scalar(select(AIProviderConfig))
    assert ai_config is not None
    assert ai_config.provider_type == "ollama"
    assert ai_config.base_url == "http://ollama.local:11434"

    setup_state = db_session.scalar(select(SetupState))
    assert setup_state is not None
    assert setup_state.status == "completed"
    assert setup_state.payload == {}
    assert setup_state.encrypted_ai_api_key is None
    assert setup_state.encrypted_smtp_password is None


def test_setup_smtp_step_can_run_connectivity_test(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.setup.test_smtp_connection",
        lambda **_: SMTPTestResult(status="passed", ok=True, message="250 OK"),
    )

    response = client.post(
        "/api/setup/wizard/smtp/test",
        json={
            "host": "smtp.example.com",
            "port": 587,
            "username": "mailer",
            "password": "smtp-password",
            "from_email": "pantro@example.com",
            "from_name": "Pantro",
            "security": "starttls",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "passed"
    assert payload["message"] == "250 OK"


def test_setup_finalize_creates_multiple_room_groups_when_rooms_are_staged(client, db_session):
    response = client.put(
        "/api/setup/wizard/welcome",
        json={"acknowledged": True},
    )
    assert response.status_code == 200

    response = client.put(
        "/api/setup/wizard/users",
        json={
            "admin_login": "owner",
            "admin_display_name": "Owner",
            "admin_password": "correct horse battery",
            "initial_users": [],
        },
    )
    assert response.status_code == 200

    response = client.put(
        "/api/setup/wizard/household",
        json={
            "household_name": "Brown Household",
            "rooms": [
                {
                    "stage_id": "room-kitchen",
                    "name": "Kitchen",
                    "storage_locations": ["Fridge", "Pantry shelf"],
                },
                {
                    "stage_id": "room-garage",
                    "name": "Garage",
                    "storage_locations": ["Freezer"],
                },
            ],
            "household_assignments": [],
        },
    )
    assert response.status_code == 200

    finalize_response = client.post("/api/setup/wizard/finalize")
    assert finalize_response.status_code == 200

    room_groups = db_session.scalars(select(LocationGroup).order_by(LocationGroup.name)).all()
    assert [room.name for room in room_groups] == ["Garage", "Kitchen"]

    locations = db_session.scalars(select(Location).order_by(Location.name)).all()
    assert [location.name for location in locations] == ["Freezer", "Fridge", "Pantry shelf"]


def test_setup_finalize_allows_optional_steps_to_be_skipped(client, db_session):
    _save_required_setup_steps(client)

    finalize_response = client.post("/api/setup/wizard/finalize")
    assert finalize_response.status_code == 200

    instance_settings = db_session.scalar(select(InstanceSetting))
    assert instance_settings is not None
    assert instance_settings.public_base_url is None

    assert db_session.scalar(select(AIProviderConfig)) is None
    assert db_session.scalar(select(SetupState)).status == "completed"


def test_setup_finalize_rejects_incomplete_state_without_creating_users(client, db_session):
    response = client.post("/api/setup/wizard/finalize")
    assert response.status_code == 400
    assert "Setup is incomplete." in response.json()["detail"]
    assert db_session.scalar(select(User)) is None


def test_login_is_blocked_until_setup_is_complete(client):
    response = client.post("/api/auth/login", json={"identifier": "owner", "password": "correct horse battery"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Pantro setup is not complete yet. Finish the setup wizard first."


def test_setup_restore_path_stages_backup_and_only_completes_on_success(client, db_session):
    _save_required_setup_steps(client)
    finalize_response = client.post("/api/setup/wizard/finalize")
    assert finalize_response.status_code == 200

    export_response = client.get("/api/platform-admin/backups/export/instance")
    assert export_response.status_code == 200
    bundle = json.loads(export_response.text)

    for table in reversed(Base.metadata.sorted_tables):
        if table.name == Role.__tablename__:
            continue
        db_session.execute(delete(table))
    db_session.commit()

    welcome_response = client.put("/api/setup/wizard/welcome", json={"acknowledged": True})
    assert welcome_response.status_code == 200

    upload_response = client.post(
        "/api/setup/wizard/restore-upload",
        files={"file": ("restore-bundle.json", json.dumps(bundle), "application/json")},
    )
    assert upload_response.status_code == 200
    staged_payload = upload_response.json()
    assert staged_payload["installation_mode"] == "restore_backup"
    assert staged_payload["staged_restore"]["supported_for_restore"] is True
    assert staged_payload["can_complete"] is True

    restored_finalize = client.post("/api/setup/wizard/finalize")
    assert restored_finalize.status_code == 200
    assert restored_finalize.json()["user"]["email"] == "owner"

    restored_users = db_session.scalars(select(User).order_by(User.email)).all()
    assert [user.email for user in restored_users] == ["alex", "owner"]
    restored_household = db_session.scalar(select(Household))
    assert restored_household is not None
    assert restored_household.name == "Brown Household"


def test_setup_restore_accepts_known_compatible_previous_schema_bundle(client, db_session):
    _save_required_setup_steps(client)
    finalize_response = client.post("/api/setup/wizard/finalize")
    assert finalize_response.status_code == 200

    export_response = client.get("/api/platform-admin/backups/export/instance")
    assert export_response.status_code == 200
    bundle = json.loads(export_response.text)
    bundle["schema_revision"] = "20260407_000009"
    bundle["tables"].pop("product_enrichments", None)

    for table in reversed(Base.metadata.sorted_tables):
        if table.name == Role.__tablename__:
            continue
        db_session.execute(delete(table))
    db_session.commit()

    welcome_response = client.put("/api/setup/wizard/welcome", json={"acknowledged": True})
    assert welcome_response.status_code == 200

    upload_response = client.post(
        "/api/setup/wizard/restore-upload",
        files={"file": ("restore-bundle.json", json.dumps(bundle), "application/json")},
    )
    assert upload_response.status_code == 200
    staged_payload = upload_response.json()
    assert staged_payload["installation_mode"] == "restore_backup"
    assert staged_payload["staged_restore"]["supported_for_restore"] is True
    assert (
        "This backup predates product enrichment support. Product enrichment records will restore as empty."
        in staged_payload["staged_restore"]["warnings"]
    )
    assert staged_payload["can_complete"] is True

    restored_finalize = client.post("/api/setup/wizard/finalize")
    assert restored_finalize.status_code == 200
    assert restored_finalize.json()["user"]["email"] == "owner"

    restored_users = db_session.scalars(select(User).order_by(User.email)).all()
    assert [user.email for user in restored_users] == ["alex", "owner"]


def test_setup_restore_rejects_unknown_previous_schema_bundle(client, db_session):
    _save_required_setup_steps(client)
    finalize_response = client.post("/api/setup/wizard/finalize")
    assert finalize_response.status_code == 200

    export_response = client.get("/api/platform-admin/backups/export/instance")
    assert export_response.status_code == 200
    bundle = json.loads(export_response.text)
    bundle["schema_revision"] = "20260406_000008"
    bundle["tables"].pop("product_enrichments", None)

    for table in reversed(Base.metadata.sorted_tables):
        if table.name == Role.__tablename__:
            continue
        db_session.execute(delete(table))
    db_session.commit()

    welcome_response = client.put("/api/setup/wizard/welcome", json={"acknowledged": True})
    assert welcome_response.status_code == 200

    upload_response = client.post(
        "/api/setup/wizard/restore-upload",
        files={"file": ("restore-bundle.json", json.dumps(bundle), "application/json")},
    )
    assert upload_response.status_code == 200
    staged_payload = upload_response.json()
    assert staged_payload["staged_restore"]["supported_for_restore"] is False
    assert (
        "This backup was created from a different Pantro schema revision, and this version gap is not restore-compatible yet."
        in staged_payload["staged_restore"]["warnings"]
    )
