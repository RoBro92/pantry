from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.auth import create_platform_admin, create_user
from app.services.instance_settings import (
    record_smtp_test_result,
    upsert_password_reset_email_template,
    upsert_smtp_settings,
)
from app.services.rate_limits import clear_local_rate_limits

PASSWORD = "correct horse battery"
PROXY_TOKEN = "test-proxy-token"


def _proxy_headers(scope: str, token: str = PROXY_TOKEN) -> dict[str, str]:
    return {
        "x-pantro-proxy-token": token,
        "x-pantro-client-scope": scope,
    }


class FakeRedis:
    def __init__(self, now):
        self.now = now
        self.values: dict[str, int] = {}
        self.expires_at: dict[str, float] = {}
        self.closed = False

    def _expire(self, key: str) -> None:
        expires_at = self.expires_at.get(key)
        if expires_at is not None and expires_at <= self.now():
            self.values.pop(key, None)
            self.expires_at.pop(key, None)

    def incr(self, key: str) -> int:
        self._expire(key)
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, seconds: int, nx: bool = False) -> bool:
        self._expire(key)
        if nx and key in self.expires_at:
            return False
        self.expires_at[key] = self.now() + seconds
        return True

    def ttl(self, key: str) -> int:
        self._expire(key)
        if key not in self.values:
            return -2
        expires_at = self.expires_at.get(key)
        if expires_at is None:
            return -1
        return int(expires_at - self.now())

    def get(self, key: str):
        self._expire(key)
        return self.values.get(key)

    def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.values:
                deleted += 1
            self.values.pop(key, None)
            self.expires_at.pop(key, None)
        return deleted

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def rate_limit_env(monkeypatch) -> Iterator[dict[str, float]]:
    now = {"value": 1000.0}
    fake_redis = FakeRedis(lambda: now["value"])
    monkeypatch.setenv("LOGIN_RATE_LIMIT_ATTEMPTS", "2")
    monkeypatch.setenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("PASSWORD_RESET_RATE_LIMIT_ATTEMPTS", "2")
    monkeypatch.setenv("PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("SETUP_MUTATION_RATE_LIMIT_ATTEMPTS", "1")
    monkeypatch.setenv("SETUP_MUTATION_RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    clear_local_rate_limits()
    monkeypatch.setattr("app.services.rate_limits.time.time", lambda: now["value"])
    monkeypatch.setattr("app.services.rate_limits.get_redis_client", lambda: fake_redis)
    try:
        yield now
    finally:
        get_settings.cache_clear()
        clear_local_rate_limits()


def _configure_password_reset(db_session, monkeypatch) -> dict[str, str]:
    admin = create_platform_admin(
        db_session,
        email="reset-admin@example.com",
        password=PASSWORD,
        display_name="Reset Admin",
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
    return captured_email


def _extract_reset_token(body: str) -> str:
    match = re.search(r"/reset-password\?token=([^\s]+)", body)
    assert match is not None
    return match.group(1)


def test_login_rate_limit_blocks_and_resets_without_account_enumeration(client, db_session, rate_limit_env):
    create_platform_admin(
        db_session,
        email="limited-admin@example.com",
        password=PASSWORD,
        display_name="Limited Admin",
    )

    for _ in range(2):
        response = client.post(
            "/api/auth/login",
            json={"email": "limited-admin@example.com", "password": "wrong password"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid username or password."

    blocked_existing = client.post(
        "/api/auth/login",
        json={"email": "limited-admin@example.com", "password": "wrong password"},
    )
    blocked_missing = client.post(
        "/api/auth/login",
        json={"email": "missing-admin@example.com", "password": "wrong password"},
    )
    assert blocked_existing.status_code == 429
    assert blocked_missing.status_code == 429
    assert blocked_existing.json() == blocked_missing.json()
    assert "account" not in blocked_existing.json()["detail"].lower()

    rate_limit_env["value"] += 61
    allowed_again = client.post(
        "/api/auth/login",
        json={"email": "limited-admin@example.com", "password": "wrong password"},
    )
    assert allowed_again.status_code == 401


def test_successful_logins_do_not_consume_failed_login_rate_limits(client, db_session, rate_limit_env):
    create_platform_admin(
        db_session,
        email="successful-limited-admin@example.com",
        password=PASSWORD,
        display_name="Successful Limited Admin",
    )

    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"email": "successful-limited-admin@example.com", "password": PASSWORD},
        )
        assert response.status_code == 200


def test_successful_login_does_not_clear_shared_ip_failure_limit(client, db_session, rate_limit_env):
    create_platform_admin(
        db_session,
        email="ip-limited-admin@example.com",
        password=PASSWORD,
        display_name="IP Limited Admin",
    )

    first_failure = client.post(
        "/api/auth/login",
        json={"email": "missing-one@example.com", "password": "wrong password"},
    )
    assert first_failure.status_code == 401

    valid_login = client.post(
        "/api/auth/login",
        json={"email": "ip-limited-admin@example.com", "password": PASSWORD},
    )
    assert valid_login.status_code == 200

    second_failure = client.post(
        "/api/auth/login",
        json={"email": "missing-two@example.com", "password": "wrong password"},
    )
    assert second_failure.status_code == 401

    blocked = client.post(
        "/api/auth/login",
        json={"email": "missing-three@example.com", "password": "wrong password"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many authentication attempts. Please wait before trying again."


def test_login_rate_limit_uses_authenticated_proxy_client_scope(
    client, db_session, monkeypatch, rate_limit_env
):
    monkeypatch.setenv("INTERNAL_API_PROXY_TOKEN", PROXY_TOKEN)
    get_settings.cache_clear()
    create_platform_admin(
        db_session,
        email="proxy-limited-admin@example.com",
        password=PASSWORD,
        display_name="Proxy Limited Admin",
    )

    for _ in range(2):
        attempted_email = f"missing-proxy-{_}@example.com"
        response = client.post(
            "/api/auth/login",
            json={"email": attempted_email, "password": "wrong password"},
            headers=_proxy_headers("198.51.100.10"),
        )
        assert response.status_code == 401

    blocked_same_scope = client.post(
        "/api/auth/login",
        json={"email": "missing-proxy-blocked@example.com", "password": "wrong password"},
        headers=_proxy_headers("198.51.100.10"),
    )
    allowed_other_scope = client.post(
        "/api/auth/login",
        json={"email": "missing-proxy-other@example.com", "password": "wrong password"},
        headers=_proxy_headers("198.51.100.11"),
    )

    assert blocked_same_scope.status_code == 429
    assert allowed_other_scope.status_code == 401


def test_login_rate_limit_ignores_unauthenticated_proxy_client_scope(
    client, db_session, monkeypatch, rate_limit_env
):
    monkeypatch.setenv("INTERNAL_API_PROXY_TOKEN", PROXY_TOKEN)
    get_settings.cache_clear()
    create_platform_admin(
        db_session,
        email="spoofed-proxy-admin@example.com",
        password=PASSWORD,
        display_name="Spoofed Proxy Admin",
    )

    for scope in ("198.51.100.20", "198.51.100.21"):
        response = client.post(
            "/api/auth/login",
            json={"email": f"spoofed-{scope}@example.com", "password": "wrong password"},
            headers=_proxy_headers(scope, token="wrong-token"),
        )
        assert response.status_code == 401

    blocked_same_peer = client.post(
        "/api/auth/login",
        json={"email": "spoofed-blocked@example.com", "password": "wrong password"},
        headers=_proxy_headers("198.51.100.22", token="wrong-token"),
    )
    assert blocked_same_peer.status_code == 429


def test_password_reset_request_rate_limit_blocks_and_resets_generically(
    client, db_session, monkeypatch, rate_limit_env
):
    create_user(
        db_session,
        email="reset-member@example.com",
        password=PASSWORD,
        display_name="Reset Member",
    )
    captured_email = _configure_password_reset(db_session, monkeypatch)

    first = client.post("/api/auth/password-reset/request", json={"email": "reset-member@example.com"})
    second = client.post("/api/auth/password-reset/request", json={"email": "missing@example.com"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert captured_email["to_email"] == "reset-member@example.com"

    blocked_existing = client.post(
        "/api/auth/password-reset/request",
        json={"email": "reset-member@example.com"},
    )
    blocked_missing = client.post(
        "/api/auth/password-reset/request",
        json={"email": "missing@example.com"},
    )
    assert blocked_existing.status_code == 429
    assert blocked_missing.status_code == 429
    assert blocked_existing.json() == blocked_missing.json()
    assert "account" not in blocked_existing.json()["detail"].lower()

    rate_limit_env["value"] += 61
    allowed_again = client.post(
        "/api/auth/password-reset/request",
        json={"email": "reset-member@example.com"},
    )
    assert allowed_again.status_code == 200


def test_setup_mutation_rate_limit_blocks_repeated_unauthenticated_setup_writes(
    client, db_session, rate_limit_env
):
    first = client.put("/api/setup/wizard/welcome", json={"acknowledged": True})
    second = client.put("/api/setup/wizard/welcome", json={"acknowledged": True})

    assert first.status_code == 200
    assert second.status_code == 429
    assert "too many" in second.json()["detail"].lower()


def test_setup_mutation_rate_limit_uses_authenticated_proxy_client_scope(
    client, monkeypatch, rate_limit_env
):
    monkeypatch.setenv("INTERNAL_API_PROXY_TOKEN", PROXY_TOKEN)
    get_settings.cache_clear()

    first_scope = client.put(
        "/api/setup/wizard/welcome",
        json={"acknowledged": True},
        headers=_proxy_headers("198.51.100.30"),
    )
    blocked_same_scope = client.put(
        "/api/setup/wizard/welcome",
        json={"acknowledged": True},
        headers=_proxy_headers("198.51.100.30"),
    )
    allowed_other_scope = client.put(
        "/api/setup/wizard/welcome",
        json={"acknowledged": True},
        headers=_proxy_headers("198.51.100.31"),
    )

    assert first_scope.status_code == 200
    assert blocked_same_scope.status_code == 429
    assert allowed_other_scope.status_code == 200


def test_password_change_revokes_other_existing_sessions(client, db_session):
    create_user(
        db_session,
        email="session-change@example.com",
        password=PASSWORD,
        display_name="Session Change",
    )
    second_client = TestClient(app, headers={"origin": "http://testserver"})

    assert client.post(
        "/api/auth/login",
        json={"email": "session-change@example.com", "password": PASSWORD},
    ).status_code == 200
    assert second_client.post(
        "/api/auth/login",
        json={"email": "session-change@example.com", "password": PASSWORD},
    ).status_code == 200

    change = client.post(
        "/api/auth/password/change",
        json={"current_password": PASSWORD, "new_password": "new correct horse battery"},
    )
    assert change.status_code == 200
    assert client.get("/api/auth/session").status_code == 200
    assert second_client.get("/api/auth/session").status_code == 401
    assert second_client.post(
        "/api/auth/login",
        json={"email": "session-change@example.com", "password": "new correct horse battery"},
    ).status_code == 200


def test_password_reset_revokes_existing_sessions(client, db_session, monkeypatch):
    create_user(
        db_session,
        email="session-reset@example.com",
        password=PASSWORD,
        display_name="Session Reset",
    )
    captured_email = _configure_password_reset(db_session, monkeypatch)
    old_session = TestClient(app, headers={"origin": "http://testserver"})
    assert old_session.post(
        "/api/auth/login",
        json={"email": "session-reset@example.com", "password": PASSWORD},
    ).status_code == 200

    reset_request = client.post(
        "/api/auth/password-reset/request",
        json={"email": "session-reset@example.com"},
    )
    assert reset_request.status_code == 200
    token = _extract_reset_token(captured_email["body"])

    reset_confirm = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "password": "new correct horse battery"},
    )
    assert reset_confirm.status_code == 200
    assert old_session.get("/api/auth/session").status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"email": "session-reset@example.com", "password": "new correct horse battery"},
    ).status_code == 200


def test_profile_email_change_revokes_other_existing_sessions(client, db_session):
    create_user(
        db_session,
        email="profile-session@example.com",
        password=PASSWORD,
        display_name="Profile Session",
    )
    second_client = TestClient(app, headers={"origin": "http://testserver"})
    assert client.post(
        "/api/auth/login",
        json={"email": "profile-session@example.com", "password": PASSWORD},
    ).status_code == 200
    assert second_client.post(
        "/api/auth/login",
        json={"email": "profile-session@example.com", "password": PASSWORD},
    ).status_code == 200

    update = client.patch(
        "/api/auth/profile",
        json={"email": "profile-session-renamed@example.com", "display_name": "Profile Session"},
    )
    assert update.status_code == 200
    assert client.get("/api/auth/session").status_code == 200
    assert second_client.get("/api/auth/session").status_code == 401


def test_csrf_origin_protection_allows_same_origin_and_configured_origins(
    db_session, monkeypatch
):
    create_platform_admin(
        db_session,
        email="csrf-admin@example.com",
        password=PASSWORD,
        display_name="CSRF Admin",
    )

    same_origin_client = TestClient(app, headers={"origin": "http://testserver"})
    same_origin = same_origin_client.post(
        "/api/auth/login",
        json={"email": "csrf-admin@example.com", "password": PASSWORD},
    )
    assert same_origin.status_code == 200

    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://trusted.example")
    get_settings.cache_clear()
    try:
        trusted_client = TestClient(app, headers={"origin": "https://trusted.example"})
        trusted = trusted_client.post(
            "/api/auth/login",
            json={"email": "csrf-admin@example.com", "password": PASSWORD},
        )
        assert trusted.status_code == 200
    finally:
        get_settings.cache_clear()


def test_csrf_origin_protection_rejects_missing_and_invalid_origins(db_session):
    create_platform_admin(
        db_session,
        email="csrf-reject-admin@example.com",
        password=PASSWORD,
        display_name="CSRF Reject Admin",
    )
    raw_client = TestClient(app)
    missing_origin = raw_client.post(
        "/api/auth/login",
        json={"email": "csrf-reject-admin@example.com", "password": PASSWORD},
    )
    invalid_origin = raw_client.post(
        "/api/auth/login",
        headers={"origin": "https://evil.example"},
        json={"email": "csrf-reject-admin@example.com", "password": PASSWORD},
    )
    safe_method = raw_client.get("/api/health")

    assert missing_origin.status_code == 403
    assert invalid_origin.status_code == 403
    assert missing_origin.json()["detail"] == invalid_origin.json()["detail"]
    assert safe_method.status_code == 200


def test_csrf_origin_protection_does_not_trust_request_host(db_session):
    create_platform_admin(
        db_session,
        email="csrf-host-admin@example.com",
        password=PASSWORD,
        display_name="CSRF Host Admin",
    )
    raw_client = TestClient(app)

    response = raw_client.post(
        "/api/auth/login",
        headers={"host": "evil.example", "origin": "http://evil.example"},
        json={"email": "csrf-host-admin@example.com", "password": PASSWORD},
    )

    assert response.status_code == 403
