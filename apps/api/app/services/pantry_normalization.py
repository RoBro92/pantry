from __future__ import annotations

import re


def compact_whitespace(value: str) -> str:
    return " ".join(value.split())


def require_text(value: str, *, field_name: str) -> str:
    normalized = compact_whitespace(value)
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def normalize_lookup_name(value: str) -> str:
    return require_text(value, field_name="Value").casefold()


def normalize_unit(value: str) -> str:
    return require_text(value, field_name="Unit").casefold()


def normalize_barcode(value: str) -> str:
    stripped = re.sub(r"[\s-]+", "", value).upper()
    if not stripped:
        raise ValueError("Barcode is required.")
    return stripped


def dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
