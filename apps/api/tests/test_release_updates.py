from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import httpx

from app.core.config import get_settings, infer_release_check_repository
from app.services.auth import create_platform_admin
from app.services.releases import (
    ReleaseMetadata,
    build_release_check_summary,
    compare_versions,
)

PASSWORD = "correct horse battery"


def login(client, *, email: str, password: str = PASSWORD) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


def test_compare_versions_handles_semver_shapes():
    assert compare_versions("0.1.0", "0.1.1") == -1
    assert compare_versions("0.2.0", "0.1.9") == 1
    assert compare_versions("0.1.0", "v0.1.0") == 0
    assert compare_versions("0.1.0-rc.1", "0.1.0") == -1
    assert compare_versions("0.1.0", "bad-version") is None


def test_infer_release_check_repository_reads_origin_remote(monkeypatch, tmp_path):
    config_path = tmp_path / "config"
    config_path.write_text(
        '[remote "origin"]\n\turl = https://github.com/example/pantry.git\n',
        encoding="utf-8",
    )

    monkeypatch.setattr("app.core.config._resolve_git_config_path", lambda _: config_path)
    infer_release_check_repository.cache_clear()
    try:
        assert infer_release_check_repository() == "example/pantry"
    finally:
        infer_release_check_repository.cache_clear()


def test_build_release_check_summary_reports_update_available(monkeypatch):
    settings = replace(
        get_settings(),
        app_version="0.1.0",
        release_check_repository="example/pantry",
        release_check_metadata_url=None,
    )
    monkeypatch.setattr("app.services.releases.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.services.releases.fetch_latest_release_metadata",
        lambda _: ReleaseMetadata(
            tag_name="v0.1.1",
            version="0.1.1",
            name="Pantry v0.1.1",
            html_url="https://github.com/example/pantry/releases/tag/v0.1.1",
            published_at=datetime(2026, 4, 4, tzinfo=timezone.utc),
        ),
    )

    summary = build_release_check_summary()

    assert summary["configured"] is True
    assert summary["metadata_status"] == "available"
    assert summary["status"] == "update_available"
    assert summary["current_version"] == "0.1.0"
    assert summary["latest_version"] == "0.1.1"
    assert summary["release_tag"] == "v0.1.1"
    assert summary["release_notes_url"] == "https://github.com/example/pantry/releases/tag/v0.1.1"
    assert summary["update_available"] is True


def test_build_release_check_summary_fails_gracefully_when_metadata_unavailable(monkeypatch):
    settings = replace(
        get_settings(),
        app_version="0.1.0",
        release_check_repository="example/pantry",
        release_check_metadata_url=None,
    )
    monkeypatch.setattr("app.services.releases.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.services.releases.fetch_latest_release_metadata",
        lambda _: (_ for _ in ()).throw(
            httpx.HTTPStatusError(
                "404 Not Found",
                request=httpx.Request("GET", "https://api.github.com/repos/example/pantry/releases/latest"),
                response=httpx.Response(404),
            )
        ),
    )

    summary = build_release_check_summary()

    assert summary["configured"] is True
    assert summary["metadata_status"] == "release_missing"
    assert summary["status"] == "release_metadata_missing"
    assert summary["latest_version"] is None
    assert summary["update_available"] is None
    assert "github release metadata" in str(summary["message"]).lower()


def test_platform_admin_release_status_endpoint_returns_advisory_update_state(
    client,
    db_session,
    monkeypatch,
):
    create_platform_admin(
        db_session,
        email="release-admin@example.com",
        password=PASSWORD,
        display_name="Release Admin",
    )
    login(client, email="release-admin@example.com")

    settings = replace(
        get_settings(),
        app_version="0.1.0",
        release_check_repository="example/pantry",
        release_check_metadata_url=None,
    )
    monkeypatch.setattr("app.services.releases.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.services.releases.fetch_latest_release_metadata",
        lambda _: ReleaseMetadata(
            tag_name="v0.1.2",
            version="0.1.2",
            name="Pantry v0.1.2",
            html_url="https://github.com/example/pantry/releases/tag/v0.1.2",
            published_at=datetime(2026, 4, 4, tzinfo=timezone.utc),
        ),
    )

    response = client.get("/api/platform-admin/release-status")
    assert response.status_code == 200

    payload = response.json()
    assert payload["metadata_status"] == "available"
    assert payload["status"] == "update_available"
    assert payload["current_version"] == "0.1.0"
    assert payload["latest_version"] == "0.1.2"
    assert payload["update_available"] is True


def test_platform_admin_can_mark_current_release_notes_seen(client, db_session, monkeypatch):
    create_platform_admin(
        db_session,
        email="release-notes@example.com",
        password=PASSWORD,
        display_name="Release Notes Admin",
    )
    login(client, email="release-notes@example.com")

    settings = replace(
        get_settings(),
        app_version="0.1.2",
        release_check_repository="example/pantry",
        release_check_metadata_url=None,
    )
    monkeypatch.setattr("app.services.releases.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.services.releases.fetch_latest_release_metadata",
        lambda _: ReleaseMetadata(
            tag_name="v0.1.2",
            version="0.1.2",
            name="Pantry v0.1.2",
            html_url="https://github.com/example/pantry/releases/tag/v0.1.2",
            published_at=datetime(2026, 4, 4, tzinfo=timezone.utc),
        ),
    )
    monkeypatch.setattr(
        "app.services.releases.fetch_release_metadata_by_tag",
        lambda *_args, **_kwargs: ReleaseMetadata(
            tag_name="v0.1.2",
            version="0.1.2",
            name="Pantry v0.1.2",
            html_url="https://github.com/example/pantry/releases/tag/v0.1.2",
            published_at=datetime(2026, 4, 4, tzinfo=timezone.utc),
            body="## Breaking changes\n- Review this once\n",
        ),
    )

    initial = client.get("/api/platform-admin/release-status")
    assert initial.status_code == 200
    assert initial.json()["show_whats_new_prompt"] is True
    assert initial.json()["notes_seen_version"] is None

    mark_seen = client.post("/api/platform-admin/release-status/mark-seen", json={})
    assert mark_seen.status_code == 200
    payload = mark_seen.json()
    assert payload["show_whats_new_prompt"] is False
    assert payload["notes_seen_version"] == "0.1.2"
