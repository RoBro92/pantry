from __future__ import annotations

from app.domain.roles import HOUSEHOLD_USER_ROLE
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

