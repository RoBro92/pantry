from __future__ import annotations

import re

LOOKUP_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
LOOKUP_TOKEN_EQUIVALENTS = {
    "mayo": ("mayonnaise",),
}


def compact_whitespace(value: str) -> str:
    return " ".join(value.split())


def require_text(value: str, *, field_name: str) -> str:
    normalized = compact_whitespace(value)
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def normalize_lookup_name(value: str) -> str:
    return require_text(value, field_name="Value").casefold()


def lookup_tokens(value: str) -> list[str]:
    normalized = normalize_lookup_name(value)
    return LOOKUP_TOKEN_PATTERN.findall(normalized)


def expand_lookup_name_variants(value: str) -> list[str]:
    normalized = normalize_lookup_name(value)
    tokens = LOOKUP_TOKEN_PATTERN.findall(normalized)
    if not tokens:
        return [normalized]

    token_variants: set[tuple[str, ...]] = {tuple(tokens)}
    for index, token in enumerate(tokens):
        replacements = LOOKUP_TOKEN_EQUIVALENTS.get(token, ())
        if not replacements:
            continue
        current_variants = list(token_variants)
        for token_variant in current_variants:
            for replacement in replacements:
                next_variant = list(token_variant)
                next_variant[index] = replacement
                token_variants.add(tuple(next_variant))

    results = [normalized]
    seen = {normalized}
    for token_variant in token_variants:
        candidate = " ".join(token_variant)
        if candidate in seen:
            continue
        seen.add(candidate)
        results.append(candidate)
    return results


def lookup_token_signature(value: str) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(lookup_tokens(value))))


def lookup_token_overlap(left: str, right: str) -> float:
    left_tokens = set(lookup_tokens(left))
    right_tokens = set(lookup_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens), 1)


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


def normalize_text_tags(values: list[str], *, field_name: str) -> list[str]:
    cleaned: list[str] = []
    seen_normalized: set[str] = set()
    for value in values:
        if not value or not value.strip():
            continue
        display_value = require_text(value, field_name=field_name)
        normalized_value = normalize_lookup_name(display_value)
        if normalized_value in seen_normalized:
            continue
        seen_normalized.add(normalized_value)
        cleaned.append(display_value)
    return cleaned
