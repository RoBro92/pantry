from __future__ import annotations

import smtplib
from dataclasses import dataclass

from app.core.config import get_settings
from app.services.instance_settings import SMTP_SECURITY_SSL, SMTP_SECURITY_STARTTLS, resolve_smtp_config


@dataclass(frozen=True)
class SMTPTestResult:
    status: str
    ok: bool
    message: str | None


def run_smtp_connectivity_test(db_session) -> SMTPTestResult:
    settings = get_settings()
    config = resolve_smtp_config(db_session)
    if config.config_error:
        raise ValueError(config.config_error)
    if not config.is_configured or not config.host or config.port is None or not config.security:
        raise ValueError("SMTP is not configured well enough to test.")

    timeout = settings.smtp_timeout_seconds
    smtp_client: smtplib.SMTP | smtplib.SMTP_SSL | None = None
    try:
        if config.security == SMTP_SECURITY_SSL:
            smtp_client = smtplib.SMTP_SSL(config.host, config.port, timeout=timeout)
        else:
            smtp_client = smtplib.SMTP(config.host, config.port, timeout=timeout)

        smtp_client.ehlo()
        if config.security == SMTP_SECURITY_STARTTLS:
            smtp_client.starttls()
            smtp_client.ehlo()

        if config.username and config.password:
            smtp_client.login(config.username, config.password)

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
