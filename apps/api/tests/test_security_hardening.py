from __future__ import annotations

import json
import socket
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings, validate_production_settings
from app.models.base import utc_now
from app.models.import_job import ImportJob
from app.models.import_source_file import ImportSourceFile
from app.models.user import User
from app.services.auth import create_household, create_membership, create_platform_admin, create_user
from app.services.backups import load_staged_backup
from app.services.import_processing import _claim_next_import_job
from app.services.import_storage import resolve_storage_path
from app.services.recipe_url_imports import _fetch_recipe_html
from app.services.runtime_status import RedisHealthSnapshot, check_redis_health, publish_worker_heartbeat, read_worker_heartbeat

PASSWORD = "correct horse battery"


def login(client, *, email: str, password: str = PASSWORD) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


def create_member_household(db_session, *, email: str, household_name: str):
    user = create_user(db_session, email=email, password=PASSWORD, display_name=email.split("@")[0].title())
    household = create_household(db_session, name=household_name)
    create_membership(
        db_session,
        user=user,
        household=household,
        role_code="household_admin",
    )
    return user, household


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/recipe",
        "http://localhost/recipe",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/recipe",
        "http://[::1]/recipe",
        "http://[fd00::1]/recipe",
    ],
)
def test_recipe_url_import_rejects_private_network_targets(client, db_session, url):
    _, household = create_member_household(
        db_session,
        email="recipe-ssrf@example.com",
        household_name="Recipe SSRF Household",
    )
    login(client, email="recipe-ssrf@example.com")

    response = client.post(
        f"/api/households/{household.external_id}/recipe-imports/url",
        json={"url": url},
    )

    assert response.status_code == 400
    assert "private" in response.json()["detail"].lower() or "local" in response.json()["detail"].lower()


def test_recipe_html_fetch_rejects_private_final_url(monkeypatch):
    import httpx

    class StubClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, headers):
            del url, headers
            return httpx.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                content=b"<html><title>Local</title></html>",
                request=httpx.Request("GET", "http://127.0.0.1/admin"),
            )

    monkeypatch.setattr("app.services.recipe_url_imports.httpx.Client", StubClient)
    monkeypatch.setattr(
        "app.services.network_policy.socket.getaddrinfo",
        lambda host, port, *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 443))
        ],
    )

    with pytest.raises(ValueError, match="private|local"):
        _fetch_recipe_html("https://recipes.example/import")


def test_import_storage_rejects_paths_outside_storage_root():
    settings = get_settings()

    with pytest.raises(ValueError, match="storage path"):
        resolve_storage_path(settings, "../outside.json")

    with pytest.raises(ValueError, match="storage path"):
        resolve_storage_path(settings, "/etc/passwd")


def test_staged_backup_stage_id_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    try:
        settings = get_settings()
        outside = Path(settings.backup_storage_root) / "outside.json"
        outside.write_text(
            json.dumps(
                {
                    "format": "pantry.backup.bundle",
                    "format_version": 1,
                    "scope": "instance",
                    "app_version": "0.0.0-test",
                    "exported_at": "2026-04-01T00:00:00+00:00",
                    "tables": {"roles": []},
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="stage"):
            load_staged_backup(settings, stage_id="../outside")
    finally:
        get_settings.cache_clear()


def test_restore_upload_rejects_unsafe_import_source_storage_paths(client, db_session):
    admin = create_platform_admin(
        db_session,
        email="restore-path-admin@example.com",
        password=PASSWORD,
        display_name="Restore Path Admin",
    )
    _, household = create_member_household(
        db_session,
        email="restore-path-member@example.com",
        household_name="Restore Path Household",
    )
    login(client, email=admin.email)

    upload = client.post(
        f"/api/households/{household.external_id}/imports/uploads",
        data={"source_type": "structured_import"},
        files={"file": ("safe.json", json.dumps({"lines": ["Milk"]}), "application/json")},
    )
    assert upload.status_code == 201

    export_response = client.get("/api/platform-admin/backups/export/instance")
    assert export_response.status_code == 200
    bundle = json.loads(export_response.text)
    assert bundle["tables"]["import_source_files"]
    bundle["tables"]["import_source_files"][0]["storage_path"] = "../outside.json"

    response = client.post(
        "/api/platform-admin/backups/restore-upload",
        files={"file": ("unsafe-restore.json", json.dumps(bundle), "application/json")},
    )

    assert response.status_code == 400
    assert "storage path" in response.json()["detail"].lower()


def test_ready_endpoint_checks_database_migrations_and_redis(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.health.check_redis_health",
        lambda: RedisHealthSnapshot(status="ok", latency_ms=1.0, message=None),
    )

    response = client.get("/api/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"]["status"] == "ok"
    assert payload["migrations"]["status"] == "ok"
    assert payload["redis"]["status"] == "ok"


def test_stale_processing_import_jobs_can_be_reclaimed(db_session):
    _, household = create_member_household(
        db_session,
        email="stale-import@example.com",
        household_name="Stale Import Household",
    )
    stale_job = ImportJob(
        household_id=household.id,
        source_type="structured_import",
        source_label="stale.json",
        status="processing",
        processing_started_at=utc_now() - timedelta(hours=1),
        failure_message="Worker disappeared.",
    )
    db_session.add(stale_job)
    db_session.commit()
    original_started_at = stale_job.processing_started_at

    claimed = _claim_next_import_job(db_session)

    assert claimed is not None
    assert claimed.id == stale_job.id
    assert claimed.status == "processing"
    assert claimed.failure_message is None
    assert original_started_at is not None
    assert claimed.processing_started_at > original_started_at


def test_runtime_status_closes_redis_clients(monkeypatch):
    closed_clients = []

    class FakeRedis:
        def setex(self, key, ttl, value):
            del key, ttl, value

        def get(self, key):
            del key
            return json.dumps(
                {
                    "service": "worker",
                    "environment": "test",
                    "version": "0.0.0-test",
                    "mode": "poller",
                    "poll_interval_seconds": 5,
                    "started_at": utc_now().isoformat(),
                    "last_seen_at": utc_now().isoformat(),
                    "status": "ok",
                }
            )

        def ping(self):
            return True

        def close(self):
            closed_clients.append(self)

    monkeypatch.setattr("app.services.runtime_status.get_redis_client", lambda: FakeRedis())

    publish_worker_heartbeat(
        service="worker",
        environment="test",
        version="0.0.0-test",
        mode="poller",
        poll_interval_seconds=5,
        started_at=utc_now(),
    )
    assert read_worker_heartbeat() is not None
    assert check_redis_health().status == "ok"
    assert len(closed_clients) == 3


def test_production_settings_reject_placeholder_or_shared_secrets():
    settings = replace(
        get_settings(),
        environment="production",
        session_secret_key="change-me-for-production",
        settings_encryption_key=None,
    )

    with pytest.raises(ValueError, match="SESSION_SECRET_KEY"):
        validate_production_settings(settings)

    settings = replace(
        get_settings(),
        environment="production",
        session_secret_key="x" * 40,
        settings_encryption_key="x" * 40,
    )

    with pytest.raises(ValueError, match="SETTINGS_ENCRYPTION_KEY"):
        validate_production_settings(settings)


def test_setup_mutation_endpoints_close_after_setup_completion(client, db_session):
    create_platform_admin(
        db_session,
        email="setup-closed-admin@example.com",
        password=PASSWORD,
        display_name="Setup Closed Admin",
    )

    response = client.put("/api/setup/wizard/welcome", json={"acknowledged": True})

    assert response.status_code == 403
    assert "already been completed" in response.json()["detail"]
