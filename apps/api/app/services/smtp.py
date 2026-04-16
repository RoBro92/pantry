from __future__ import annotations

import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import get_settings
from app.services.instance_settings import (
    SMTP_SECURITY_SSL,
    SMTP_SECURITY_STARTTLS,
    resolve_smtp_config,
)


@dataclass(frozen=True)
class SMTPTestResult:
    status: str
    ok: bool
    message: str | None


def _open_smtp_client(*, host: str, port: int, security: str, timeout: int):
    if security == SMTP_SECURITY_SSL:
        smtp_client = smtplib.SMTP_SSL(host, port, timeout=timeout)
    else:
        smtp_client = smtplib.SMTP(host, port, timeout=timeout)

    smtp_client.ehlo()
    if security == SMTP_SECURITY_STARTTLS:
        smtp_client.starttls()
        smtp_client.ehlo()
    return smtp_client


def test_smtp_connection(
    *,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    security: str,
) -> SMTPTestResult:
    timeout = get_settings().smtp_timeout_seconds
    smtp_client: smtplib.SMTP | smtplib.SMTP_SSL | None = None
    try:
        smtp_client = _open_smtp_client(
            host=host,
            port=port,
            security=security,
            timeout=timeout,
        )

        if username and password:
            smtp_client.login(username, password)

        code, response = smtp_client.noop()
        message = response.decode("utf-8", errors="ignore") if isinstance(response, bytes) else str(response)
        return SMTPTestResult(
            status="passed" if 200 <= code < 400 else "failed",
            ok=200 <= code < 400,
            message=message or None,
        )
    except OSError as exc:
        return SMTPTestResult(status="failed", ok=False, message=str(exc))
    finally:
        if smtp_client is not None:
            try:
                smtp_client.quit()
            except OSError:
                pass


def run_smtp_connectivity_test(db_session) -> SMTPTestResult:
    config = resolve_smtp_config(db_session)
    if config.config_error:
        raise ValueError(config.config_error)
    if not config.is_configured or not config.host or config.port is None or not config.security:
        raise ValueError("SMTP is not configured well enough to test.")

    return test_smtp_connection(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        security=config.security,
    )


def send_email(
    db_session,
    *,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    settings = get_settings()
    config = resolve_smtp_config(db_session)
    if config.config_error:
        raise ValueError(config.config_error)
    if not config.is_configured or not config.host or config.port is None or not config.security:
        raise ValueError("SMTP is not configured well enough to send email.")
    if not config.from_email:
        raise ValueError("SMTP from email is required before sending email.")

    message = EmailMessage()
    message["To"] = to_email
    message["From"] = (
        formataddr((config.from_name, config.from_email))
        if config.from_name
        else config.from_email
    )
    message["Subject"] = subject
    message.set_content(body)

    smtp_client: smtplib.SMTP | smtplib.SMTP_SSL | None = None
    try:
        smtp_client = _open_smtp_client(
            host=config.host,
            port=config.port,
            security=config.security,
            timeout=settings.smtp_timeout_seconds,
        )
        if config.username and config.password:
            smtp_client.login(config.username, config.password)
        smtp_client.send_message(message)
    except OSError as exc:
        raise ValueError(f"Could not send email: {exc}") from exc
    finally:
        if smtp_client is not None:
            try:
                smtp_client.quit()
            except OSError:
                pass


def send_smtp_test_email(db_session) -> str:
    config = resolve_smtp_config(db_session)
    if not config.test_recipient_email:
        raise ValueError("Save an SMTP test recipient email before sending a test email.")

    timestamp = datetime.now(timezone.utc).isoformat()
    send_email(
        db_session,
        to_email=config.test_recipient_email,
        subject="Pantro SMTP test email",
        body=(
            "This is a Pantro SMTP test email.\n\n"
            f"Sender: {formataddr((config.from_name, config.from_email)) if config.from_name and config.from_email else config.from_email}\n"
            f"Sent at: {timestamp}\n"
        ),
    )
    return config.test_recipient_email
