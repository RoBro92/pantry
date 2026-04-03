from __future__ import annotations

from app.services.auth import create_platform_admin


def test_setup_status_reports_uninitialized_install(client):
    response = client.get("/api/setup/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_initialized"] is False
    assert payload["can_bootstrap_platform_admin"] is True


def test_setup_bootstrap_creates_first_platform_admin_and_session(client, db_session):
    response = client.post(
        "/api/setup/bootstrap-platform-admin",
        json={
            "email": "first-admin@example.com",
            "display_name": "First Admin",
            "password": "correct horse battery",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "first-admin@example.com"
    assert payload["user"]["platform_role"] == "platform_admin"

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["user"]["email"] == "first-admin@example.com"


def test_setup_bootstrap_is_rejected_after_initialization(client, db_session):
    create_platform_admin(
        db_session,
        email="existing-admin@example.com",
        password="correct horse battery",
        display_name="Existing Admin",
    )

    response = client.post(
        "/api/setup/bootstrap-platform-admin",
        json={
            "email": "second-admin@example.com",
            "display_name": "Second Admin",
            "password": "correct horse battery",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Initial setup has already been completed."
