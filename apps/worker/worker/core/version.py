from __future__ import annotations

from pathlib import Path


def read_repo_version(*, fallback: str = "0.0.0-dev") -> str:
    version_path = Path(__file__).resolve().parents[4] / "VERSION"
    try:
        value = version_path.read_text(encoding="utf-8").strip()
    except OSError:
        return fallback
    return value or fallback
