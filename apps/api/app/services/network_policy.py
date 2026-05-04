from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


def _host_is_local_name(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    return normalized == "localhost" or normalized.endswith(".localhost")


def _address_is_private(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(
        [
            address.is_loopback,
            address.is_private,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        ]
    )


def _validate_hostname_address(hostname: str) -> None:
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return

    if _address_is_private(address):
        raise ValueError("Recipe URL must not target private, local, or reserved network addresses.")


def _validate_resolved_addresses(hostname: str, *, port: int | None) -> None:
    try:
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Recipe URL host could not be resolved.") from exc

    if not results:
        raise ValueError("Recipe URL host could not be resolved.")

    for result in results:
        address_text = result[4][0]
        try:
            address = ipaddress.ip_address(address_text)
        except ValueError as exc:
            raise ValueError("Recipe URL host resolved to an invalid address.") from exc
        if _address_is_private(address):
            raise ValueError("Recipe URL must not target private, local, or reserved network addresses.")


def validate_public_http_url(value: str, *, field_name: str = "URL", resolve_host: bool = False) -> str:
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError(f"{field_name} must use http or https.")
    if not parsed.hostname:
        raise ValueError(f"{field_name} must include a host.")
    if parsed.username or parsed.password:
        raise ValueError(f"{field_name} must not include embedded credentials.")

    hostname = parsed.hostname
    if _host_is_local_name(hostname):
        raise ValueError(f"{field_name} must not target local hostnames.")
    _validate_hostname_address(hostname)
    if resolve_host:
        _validate_resolved_addresses(hostname, port=parsed.port)

    return value
