from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.core.config import AppSettings, get_settings

VERSION_PATTERN = re.compile(
    r"^[vV]?(?P<core>\d+\.\d+\.\d+)(?:-(?P<prerelease>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


@dataclass(frozen=True)
class ParsedVersion:
    core: tuple[int, int, int]
    prerelease: tuple[str, ...] | None


@dataclass(frozen=True)
class ReleaseMetadata:
    tag_name: str
    version: str
    name: str | None
    html_url: str | None
    published_at: datetime | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_version(value: str) -> ParsedVersion | None:
    match = VERSION_PATTERN.match(value.strip())
    if match is None:
        return None

    core = tuple(int(part) for part in match.group("core").split("."))
    prerelease_raw = match.group("prerelease")
    prerelease = tuple(prerelease_raw.split(".")) if prerelease_raw else None
    return ParsedVersion(core=core, prerelease=prerelease)


def _compare_prerelease(left: tuple[str, ...] | None, right: tuple[str, ...] | None) -> int:
    if left is None and right is None:
        return 0
    if left is None:
        return 1
    if right is None:
        return -1

    for index in range(min(len(left), len(right))):
        left_part = left[index]
        right_part = right[index]
        if left_part == right_part:
            continue

        left_is_number = left_part.isdigit()
        right_is_number = right_part.isdigit()
        if left_is_number and right_is_number:
            return (int(left_part) > int(right_part)) - (int(left_part) < int(right_part))
        if left_is_number != right_is_number:
            return -1 if left_is_number else 1
        return (left_part > right_part) - (left_part < right_part)

    return (len(left) > len(right)) - (len(left) < len(right))


def compare_versions(current: str, latest: str) -> int | None:
    left = _parse_version(current)
    right = _parse_version(latest)
    if left is None or right is None:
        return None

    if left.core != right.core:
        return (left.core > right.core) - (left.core < right.core)
    return _compare_prerelease(left.prerelease, right.prerelease)


def _resolve_release_metadata_url(settings: AppSettings) -> tuple[str | None, str | None]:
    if settings.release_check_metadata_url:
        return settings.release_check_metadata_url, settings.release_check_repository
    if settings.release_check_repository:
        return (
            f"https://api.github.com/repos/{settings.release_check_repository}/releases/latest",
            settings.release_check_repository,
        )
    return None, None


def fetch_latest_release_metadata(settings: AppSettings) -> ReleaseMetadata:
    metadata_url, _ = _resolve_release_metadata_url(settings)
    if not metadata_url:
        raise ValueError("Release metadata source is not configured.")

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"Pantry/{settings.app_version}",
    }
    with httpx.Client(timeout=settings.release_check_timeout_seconds, follow_redirects=True) as client:
        response = client.get(metadata_url, headers=headers)
        response.raise_for_status()

    payload = response.json()
    tag_name = str(payload.get("tag_name") or "").strip()
    if not tag_name:
        raise ValueError("Release metadata did not include tag_name.")

    version = tag_name[1:] if tag_name.lower().startswith("v") else tag_name
    return ReleaseMetadata(
        tag_name=tag_name,
        version=version,
        name=str(payload.get("name")).strip() if payload.get("name") else None,
        html_url=str(payload.get("html_url")).strip() if payload.get("html_url") else None,
        published_at=_parse_datetime(payload.get("published_at")),
    )


def build_release_check_summary() -> dict[str, object]:
    settings = get_settings()
    checked_at = _utc_now()
    metadata_url, repository = _resolve_release_metadata_url(settings)

    summary: dict[str, object] = {
        "configured": settings.release_check_enabled,
        "source_type": "github_releases_latest" if settings.release_check_enabled else None,
        "repository": repository,
        "current_version": settings.app_version,
        "latest_version": None,
        "release_tag": None,
        "release_name": None,
        "release_notes_url": None,
        "published_at": None,
        "checked_at": checked_at,
        "status": "not_configured",
        "update_available": None,
        "message": "Release metadata source is not configured for this installation.",
    }

    if not metadata_url:
        return summary

    try:
        metadata = fetch_latest_release_metadata(settings)
    except httpx.HTTPStatusError as exc:
        summary["status"] = "unavailable"
        summary["message"] = f"Release metadata request failed with status {exc.response.status_code}."
        return summary
    except httpx.HTTPError:
        summary["status"] = "unavailable"
        summary["message"] = "Release metadata request failed."
        return summary
    except ValueError as exc:
        summary["status"] = "unavailable"
        summary["message"] = str(exc)
        return summary

    summary.update(
        latest_version=metadata.version,
        release_tag=metadata.tag_name,
        release_name=metadata.name,
        release_notes_url=metadata.html_url,
        published_at=metadata.published_at,
    )

    comparison = compare_versions(settings.app_version, metadata.version)
    if comparison is None:
        summary["status"] = "comparison_unavailable"
        summary["message"] = "Current or latest version could not be compared safely."
        return summary

    if comparison < 0:
        summary["status"] = "update_available"
        summary["update_available"] = True
        summary["message"] = "A newer release is available for manual operator review."
        return summary

    if comparison > 0:
        summary["status"] = "ahead_of_latest_release"
        summary["update_available"] = False
        summary["message"] = "This install is newer than the latest published release metadata."
        return summary

    summary["status"] = "up_to_date"
    summary["update_available"] = False
    summary["message"] = "This install matches the latest published release metadata."
    return summary
