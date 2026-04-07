from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import AppSettings, get_settings
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.instance_settings import get_instance_settings, get_or_create_instance_settings

VERSION_PATTERN = re.compile(
    r"^[vV]?(?P<core>\d+\.\d+\.\d+)(?:-(?P<prerelease>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)
RELEASE_JSON_ASSET_NAME = "release.json"


@dataclass(frozen=True)
class ParsedVersion:
    core: tuple[int, int, int]
    prerelease: tuple[str, ...] | None


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    browser_download_url: str | None


@dataclass(frozen=True)
class ReleaseMetadata:
    tag_name: str
    version: str
    name: str | None
    html_url: str | None
    published_at: datetime | None
    body: str | None = None
    assets: tuple[ReleaseAsset, ...] = ()


@dataclass(frozen=True)
class ReleaseNotes:
    version: str
    release_tag: str
    release_name: str | None
    release_notes_url: str | None
    published_at: datetime | None
    changelog_summary: str | None
    breaking_change_notes: tuple[str, ...]
    manual_update_commands: tuple[str, ...]
    notes_source: str | None


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


def _github_headers(settings: AppSettings) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"Pantry/{settings.app_version}",
    }


def _release_api_url(repository: str, tag_name: str) -> str:
    return f"https://api.github.com/repos/{repository}/releases/tags/{tag_name}"


def _parse_release_payload(payload: dict[str, Any]) -> ReleaseMetadata:
    tag_name = str(payload.get("tag_name") or "").strip()
    if not tag_name:
        raise ValueError("Release metadata did not include tag_name.")

    version = tag_name[1:] if tag_name.lower().startswith("v") else tag_name
    assets: list[ReleaseAsset] = []
    for asset in payload.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "").strip()
        if not name:
            continue
        assets.append(
            ReleaseAsset(
                name=name,
                browser_download_url=(
                    str(asset.get("browser_download_url")).strip()
                    if asset.get("browser_download_url")
                    else None
                ),
            )
        )

    return ReleaseMetadata(
        tag_name=tag_name,
        version=version,
        name=str(payload.get("name")).strip() if payload.get("name") else None,
        html_url=str(payload.get("html_url")).strip() if payload.get("html_url") else None,
        published_at=_parse_datetime(payload.get("published_at")),
        body=str(payload.get("body")).strip() if payload.get("body") else None,
        assets=tuple(assets),
    )


def fetch_latest_release_metadata(settings: AppSettings) -> ReleaseMetadata:
    metadata_url, _ = _resolve_release_metadata_url(settings)
    if not metadata_url:
        raise ValueError("Release metadata source is not configured.")

    with httpx.Client(timeout=settings.release_check_timeout_seconds, follow_redirects=True) as client:
        response = client.get(metadata_url, headers=_github_headers(settings))
        response.raise_for_status()
        payload = response.json()

    return _parse_release_payload(payload)


def fetch_release_metadata_by_tag(settings: AppSettings, *, tag_name: str) -> ReleaseMetadata:
    if not settings.release_check_repository:
        raise ValueError("Release repository is not configured.")

    with httpx.Client(timeout=settings.release_check_timeout_seconds, follow_redirects=True) as client:
        response = client.get(
            _release_api_url(settings.release_check_repository, tag_name),
            headers=_github_headers(settings),
        )
        response.raise_for_status()
        payload = response.json()

    return _parse_release_payload(payload)


def _clean_markdown_line(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"^[>\-\*\+\d\.\)\s]+", "", cleaned)
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = cleaned.replace("**", "").replace("__", "").replace("*", "")
    return cleaned.strip()


def _parse_body_release_notes(body: str | None) -> tuple[str | None, tuple[str, ...]]:
    if not body or not body.strip():
        return None, ()

    summary_parts: list[str] = []
    list_candidates: list[str] = []
    breaking_notes: list[str] = []
    in_breaking_section = False

    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        heading_match = re.match(r"^#+\s*(.+)$", stripped)
        if heading_match:
            heading = _clean_markdown_line(heading_match.group(1))
            in_breaking_section = "breaking" in heading.casefold()
            continue

        cleaned = _clean_markdown_line(stripped)
        if not cleaned:
            continue

        if in_breaking_section:
            breaking_notes.append(cleaned)
            continue

        if stripped.startswith(("-", "*", "+")) or re.match(r"^\d+[\.\)]\s+", stripped):
            list_candidates.append(cleaned)
            continue

        if len(" ".join(summary_parts)) < 320:
            summary_parts.append(cleaned)

    if not breaking_notes:
        for candidate in list_candidates:
            if "breaking" in candidate.casefold():
                breaking_notes.append(candidate)

    summary: str | None = None
    if summary_parts:
        summary = " ".join(summary_parts[:2]).strip()
    elif list_candidates:
        summary = " ".join(list_candidates[:3]).strip()

    return summary or None, tuple(dict.fromkeys(note for note in breaking_notes if note))


def _default_manual_update_commands() -> tuple[str, ...]:
    return (
        "./infra/scripts/update-pantry.sh",
        "docker compose -f infra/compose/pantry.yml pull && docker compose -f infra/compose/pantry.yml up -d && docker compose -f infra/compose/pantry.yml exec api alembic upgrade head",
    )


def _release_json_asset_url(metadata: ReleaseMetadata) -> str | None:
    for asset in metadata.assets:
        if asset.name == RELEASE_JSON_ASSET_NAME and asset.browser_download_url:
            return asset.browser_download_url
    return None


def _load_release_json_asset(settings: AppSettings, metadata: ReleaseMetadata) -> dict[str, Any] | None:
    asset_url = _release_json_asset_url(metadata)
    if not asset_url:
        return None

    with httpx.Client(timeout=settings.release_check_timeout_seconds, follow_redirects=True) as client:
        response = client.get(asset_url, headers={"User-Agent": f"Pantry/{settings.app_version}"})
        response.raise_for_status()
        payload = response.json()

    return payload if isinstance(payload, dict) else None


def _normalize_release_json_commands(payload: dict[str, Any]) -> tuple[str, ...]:
    commands = payload.get("manual_update_commands")
    if not isinstance(commands, list):
        return ()
    normalized = [str(command).strip() for command in commands if str(command).strip()]
    return tuple(dict.fromkeys(normalized))


def build_release_notes(settings: AppSettings, metadata: ReleaseMetadata) -> ReleaseNotes:
    try:
        release_json = _load_release_json_asset(settings, metadata)
    except (httpx.HTTPError, ValueError):
        release_json = None

    if release_json:
        summary = str(release_json.get("summary")).strip() if release_json.get("summary") else None
        breaking = tuple(
            str(item).strip()
            for item in release_json.get("breaking_changes") or []
            if str(item).strip()
        )
        commands = _normalize_release_json_commands(release_json)
        if summary or breaking or commands:
            return ReleaseNotes(
                version=metadata.version,
                release_tag=metadata.tag_name,
                release_name=metadata.name,
                release_notes_url=metadata.html_url,
                published_at=metadata.published_at,
                changelog_summary=summary,
                breaking_change_notes=breaking,
                manual_update_commands=commands or _default_manual_update_commands(),
                notes_source="release_json_asset",
            )

    summary, breaking_notes = _parse_body_release_notes(metadata.body)
    return ReleaseNotes(
        version=metadata.version,
        release_tag=metadata.tag_name,
        release_name=metadata.name,
        release_notes_url=metadata.html_url,
        published_at=metadata.published_at,
        changelog_summary=summary,
        breaking_change_notes=breaking_notes,
        manual_update_commands=_default_manual_update_commands(),
        notes_source="github_release_body" if (summary or breaking_notes) else "default_commands",
    )


def _release_notes_dict(notes: ReleaseNotes | None) -> dict[str, object] | None:
    if notes is None:
        return None
    return {
        "version": notes.version,
        "release_tag": notes.release_tag,
        "release_name": notes.release_name,
        "release_notes_url": notes.release_notes_url,
        "published_at": notes.published_at,
        "changelog_summary": notes.changelog_summary,
        "breaking_change_notes": list(notes.breaking_change_notes),
        "manual_update_commands": list(notes.manual_update_commands),
        "notes_source": notes.notes_source,
    }


def build_release_check_summary(db: Session | None = None) -> dict[str, object]:
    settings = get_settings()
    checked_at = _utc_now()
    metadata_url, repository = _resolve_release_metadata_url(settings)
    stored_settings = get_instance_settings(db) if db is not None else None
    notes_seen_version = stored_settings.release_notes_seen_version if stored_settings else None
    notes_seen_at = stored_settings.release_notes_seen_at if stored_settings else None

    summary: dict[str, object] = {
        "configured": settings.release_check_enabled,
        "source_type": "github_releases_latest" if settings.release_check_enabled else None,
        "source_strategy": "GitHub Releases latest metadata with optional release.json asset enrichment. GHCR is image hosting only.",
        "repository": repository,
        "metadata_status": "not_configured",
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
        "latest_release": None,
        "current_release": None,
        "manual_update_commands": list(_default_manual_update_commands()),
        "notes_seen_version": notes_seen_version,
        "notes_seen_at": notes_seen_at,
        "show_whats_new_prompt": False,
    }

    if not metadata_url:
        return summary

    latest_metadata: ReleaseMetadata | None = None
    latest_notes: ReleaseNotes | None = None
    current_metadata: ReleaseMetadata | None = None
    current_notes: ReleaseNotes | None = None

    try:
        latest_metadata = fetch_latest_release_metadata(settings)
        latest_notes = build_release_notes(settings, latest_metadata)
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        summary["metadata_status"] = "release_missing" if status_code == 404 else "request_failed"
        summary["status"] = "release_metadata_missing" if status_code == 404 else "unavailable"
        summary["message"] = (
            "No published GitHub Release metadata is available for this repository yet. GHCR images may exist, but Pantry only uses GitHub Releases for advisory update metadata."
            if status_code == 404
            else f"Release metadata request failed with status {status_code}."
        )
        return summary
    except httpx.HTTPError:
        summary["metadata_status"] = "request_failed"
        summary["status"] = "unavailable"
        summary["message"] = "Release metadata request failed."
        return summary
    except ValueError as exc:
        summary["metadata_status"] = "request_failed"
        summary["status"] = "unavailable"
        summary["message"] = str(exc)
        return summary

    summary["metadata_status"] = "available"
    summary.update(
        latest_version=latest_metadata.version,
        release_tag=latest_metadata.tag_name,
        release_name=latest_metadata.name,
        release_notes_url=latest_metadata.html_url,
        published_at=latest_metadata.published_at,
        latest_release=_release_notes_dict(latest_notes),
        manual_update_commands=list(latest_notes.manual_update_commands if latest_notes else _default_manual_update_commands()),
    )

    current_tag = settings.app_version if settings.app_version.lower().startswith("v") else f"v{settings.app_version}"
    try:
        if latest_metadata.tag_name == current_tag:
            current_metadata = latest_metadata
            current_notes = latest_notes
        elif settings.release_check_repository:
            current_metadata = fetch_release_metadata_by_tag(settings, tag_name=current_tag)
            current_notes = build_release_notes(settings, current_metadata)
    except (httpx.HTTPError, ValueError):
        current_metadata = None
        current_notes = None

    summary["current_release"] = _release_notes_dict(current_notes)
    summary["show_whats_new_prompt"] = bool(
        current_notes and current_notes.version == settings.app_version and notes_seen_version != settings.app_version
    )

    comparison = compare_versions(settings.app_version, latest_metadata.version)
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
        summary["message"] = "This install is newer than the latest published GitHub Release metadata."
        return summary

    summary["status"] = "up_to_date"
    summary["update_available"] = False
    summary["message"] = "This install matches the latest published GitHub Release metadata."
    return summary


def mark_current_release_notes_seen(db: Session, *, actor: User) -> dict[str, object]:
    settings = get_settings()
    stored_settings = get_or_create_instance_settings(db)
    stored_settings.release_notes_seen_version = settings.app_version
    stored_settings.release_notes_seen_at = _utc_now()
    db.add(stored_settings)
    db.flush()
    record_audit_event(
        db,
        household=None,
        actor=actor,
        action="instance.release_notes.seen",
        target_type="instance_setting",
        target_external_id=stored_settings.external_id,
        event_metadata={"version": settings.app_version},
    )
    db.commit()
    db.refresh(stored_settings)
    return build_release_check_summary(db)
