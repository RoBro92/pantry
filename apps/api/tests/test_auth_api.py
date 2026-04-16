from __future__ import annotations

import re

from app.domain.roles import HOUSEHOLD_USER_ROLE
from app.services.instance_settings import (
    record_smtp_test_result,
    upsert_password_reset_email_template,
    upsert_smtp_settings,
)
from app.services.auth import (
    authenticate_user,
    create_household,
    create_membership,
    create_platform_admin,
    create_user,
)


def test_login_session_and_logout(client, db_session):
    create_platform_admin(
        db_session,
        email="admin@example.com",
        password="correct horse battery",
        display_name="Admin",
    )

    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "correct horse battery"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["user"]["platform_role"] == "platform_admin"

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is True

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json() == {"ok": True}

    post_logout_session = client.get("/api/auth/session")
    assert post_logout_session.status_code == 401


def test_household_endpoint_enforces_membership_server_side(client, db_session):
    user = create_user(
        db_session,
        email="member@example.com",
        password="correct horse battery",
        display_name="Member",
    )
    allowed_household = create_household(db_session, name="Allowed Household")
    denied_household = create_household(db_session, name="Denied Household")
    create_membership(
        db_session,
        user=user,
        household=allowed_household,
        role_code=HOUSEHOLD_USER_ROLE,
    )

    login_response = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "correct horse battery"},
    )
    assert login_response.status_code == 200

    allowed_response = client.get(f"/api/households/{allowed_household.external_id}")
    assert allowed_response.status_code == 200
    assert allowed_response.json()["effective_role"] == HOUSEHOLD_USER_ROLE

    denied_response = client.get(f"/api/households/{denied_household.external_id}")
    assert denied_response.status_code == 404


def test_authenticate_user_normalizes_email(db_session):
    create_user(
        db_session,
        email="MixedCase@example.com",
        password="correct horse battery",
        display_name="Mixed Case",
    )

    user = authenticate_user(db_session, " mixedcase@example.com ", "correct horse battery")
    assert user is not None
    assert user.email == "mixedcase@example.com"


def test_logged_in_user_can_change_password_with_current_password(client, db_session):
    create_user(
        db_session,
        email="member@example.com",
        password="correct horse battery",
        display_name="Member",
    )

    login_response = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "correct horse battery"},
    )
    assert login_response.status_code == 200

    failed_change = client.post(
        "/api/auth/password/change",
        json={"current_password": "wrong password", "new_password": "new correct horse battery"},
    )
    assert failed_change.status_code == 400
    assert failed_change.json()["detail"] == "Your current password is incorrect."

    successful_change = client.post(
        "/api/auth/password/change",
        json={
            "current_password": "correct horse battery",
            "new_password": "new correct horse battery",
        },
    )
    assert successful_change.status_code == 200
    assert successful_change.json()["ok"] is True

    old_login = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "correct horse battery"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "new correct horse battery"},
    )
    assert new_login.status_code == 200


def test_logged_in_user_can_update_their_own_profile_details(client, db_session):
    create_user(
        db_session,
        email="member@example.com",
        password="correct horse battery",
        display_name="Member",
    )

    login_response = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "correct horse battery"},
    )
    assert login_response.status_code == 200

    update_response = client.patch(
        "/api/auth/profile",
        json={"email": "member-renamed", "display_name": "Updated Member"},
    )
    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["user"]["email"] == "member-renamed"
    assert payload["user"]["display_name"] == "Updated Member"

    old_login = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "correct horse battery"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        json={"email": "member-renamed", "password": "correct horse battery"},
    )
    assert new_login.status_code == 200


def test_password_reset_status_only_becomes_available_after_smtp_is_tested(client, db_session):
    admin = create_platform_admin(
        db_session,
        email="admin@example.com",
        password="correct horse battery",
        display_name="Admin",
    )

    unavailable = client.get("/api/auth/password-reset/status")
    assert unavailable.status_code == 200
    assert unavailable.json()["is_available"] is False

    upsert_smtp_settings(
        db_session,
        actor=admin,
        host="smtp.example.com",
        port=587,
        username="mailer",
        password="top-secret",
        from_email="pantro@example.com",
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

    still_unavailable = client.get("/api/auth/password-reset/status")
    assert still_unavailable.status_code == 200
    assert still_unavailable.json()["is_available"] is False
    assert "successful SMTP connectivity test" in still_unavailable.json()["reason"]

    record_smtp_test_result(db_session, actor=admin, status="passed", error=None)

    available = client.get("/api/auth/password-reset/status")
    assert available.status_code == 200
    assert available.json() == {
        "is_available": True,
        "requires_email_address": True,
        "reason": None,
    }


def test_password_reset_request_and_confirm_flow(client, db_session, monkeypatch):
    admin = create_platform_admin(
        db_session,
        email="admin@example.com",
        password="correct horse battery",
        display_name="Admin",
    )
    create_user(
        db_session,
        email="member@example.com",
        password="correct horse battery",
        display_name="Member",
    )
    upsert_smtp_settings(
        db_session,
        actor=admin,
        host="smtp.example.com",
        port=587,
        username="mailer",
        password="top-secret",
        from_email="pantro@example.com",
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

    captured_email: dict[str, str] = {}

    def fake_send_email(db_session, *, to_email: str, subject: str, body: str) -> None:
        captured_email["to_email"] = to_email
        captured_email["subject"] = subject
        captured_email["body"] = body

    monkeypatch.setattr("app.services.password_resets.send_email", fake_send_email)

    request_response = client.post(
        "/api/auth/password-reset/request",
        json={"email": "member@example.com"},
    )
    assert request_response.status_code == 200
    assert request_response.json()["message"].startswith("If we found an active Pantro account")
    assert captured_email["to_email"] == "member@example.com"
    assert "Reset your Pantro password" in captured_email["subject"]

    match = re.search(r"/reset-password\?token=([^\s]+)", captured_email["body"])
    assert match is not None
    token = match.group(1)

    status_response = client.get("/api/auth/password-reset/token-status", params={"token": token})
    assert status_response.status_code == 200
    assert status_response.json() == {"is_valid": True, "reason": None}

    confirm_response = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "password": "new correct horse battery"},
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["ok"] is True

    used_token_response = client.get(
        "/api/auth/password-reset/token-status",
        params={"token": token},
    )
    assert used_token_response.status_code == 200
    assert used_token_response.json()["is_valid"] is False

    old_login = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "correct horse battery"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "new correct horse battery"},
    )
    assert new_login.status_code == 200


def test_password_reset_request_stays_generic_for_username_only_accounts(
    client, db_session, monkeypatch
):
    admin = create_platform_admin(
        db_session,
        email="admin@example.com",
        password="correct horse battery",
        display_name="Admin",
    )
    create_user(
        db_session,
        email="username-only",
        password="correct horse battery",
        display_name="Username Only",
    )
    upsert_smtp_settings(
        db_session,
        actor=admin,
        host="smtp.example.com",
        port=587,
        username="mailer",
        password="top-secret",
        from_email="pantro@example.com",
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
        lambda *args, **kwargs: sent_messages.append("sent"),
    )

    response = client.post(
        "/api/auth/password-reset/request",
        json={"email": "username-only"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert sent_messages == []
