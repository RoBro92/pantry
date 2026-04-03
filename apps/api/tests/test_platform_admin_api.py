from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models.import_job import ImportJob
from app.models.instance_setting import InstanceSetting
from app.models.recipe import Recipe
from app.models.usage_counter import UsageCounter
from app.services.ai_config import upsert_instance_provider_config
from app.services.auth import create_household, create_membership, create_platform_admin, create_user
from app.services.instance_settings import upsert_public_base_url, upsert_smtp_settings
from app.services.pantry_catalog import create_location, create_location_group, create_product
from app.services.pantry_normalization import normalize_lookup_name
from app.services.pantry_stock import add_stock_lot
from app.services.runtime_status import RedisHealthSnapshot
from app.services.smtp import SMTPTestResult


PASSWORD = "correct horse battery"


def login(client, *, email: str, password: str = PASSWORD) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


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
        from_name="Pantry",
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
            "service": "pantry-worker",
            "version": "0.1.0",
            "mode": "import-poller",
            "poll_interval_seconds": 30,
            "started_at": datetime.now(timezone.utc),
            "last_seen_at": datetime.now(timezone.utc),
        },
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
            "from_name": "Pantry",
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
