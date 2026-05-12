from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import threading
from time import monotonic
from typing import Any

import httpx
from pydantic import HttpUrl, TypeAdapter, ValidationError

from app.schemas.pantry import (
    ProductEnrichmentAttribution,
    ProductEnrichmentCandidate,
    ProductNutritionSummaryItem,
)
from app.services.pantry_normalization import normalize_barcode, normalize_lookup_name, require_text


OPEN_FOOD_FACTS_SOURCE = "open_food_facts"
OPEN_FOOD_FACTS_BASE_URL = "https://world.openfoodfacts.org"
OPEN_FOOD_FACTS_PRODUCT_FIELDS = ",".join(
    [
        "code",
        "product_name",
        "product_name_en",
        "generic_name",
        "generic_name_en",
        "image_front_url",
        "image_url",
        "ingredients_text",
        "ingredients_text_en",
        "ingredients_tags",
        "allergens",
        "allergens_from_ingredients",
        "allergens_tags",
        "traces",
        "traces_tags",
        "labels_tags",
        "categories_tags",
        "nutriments",
        "url",
    ]
)
_URL_ADAPTER = TypeAdapter(HttpUrl)
_NUTRITION_FIELDS = (
    ("energy-kcal", "Energy", "kcal"),
    ("fat", "Fat", "g"),
    ("saturated-fat", "Saturates", "g"),
    ("carbohydrates", "Carbs", "g"),
    ("sugars", "Sugars", "g"),
    ("fiber", "Fibre", "g"),
    ("proteins", "Protein", "g"),
    ("salt", "Salt", "g"),
)
_INGREDIENT_SPLIT_RE = re.compile(r"[,;]")


class OpenFoodFactsUnavailableError(RuntimeError):
    pass


def _validate_remote_url(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return str(_URL_ADAPTER.validate_python(candidate))
    except ValidationError:
        return None


def _attribution(product_url: str | None) -> ProductEnrichmentAttribution:
    return ProductEnrichmentAttribution(
        source_name=OPEN_FOOD_FACTS_SOURCE,
        source_label="Open Food Facts",
        source_url=OPEN_FOOD_FACTS_BASE_URL,
        product_url=product_url,
        data_notice="Community-contributed Open Food Facts data may be incomplete or inaccurate.",
        license_name="Open Database License",
        license_url="https://opendatacommons.org/licenses/odbl/",
    )


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate or None


def _friendly_tag(value: str) -> str | None:
    tag = value.strip()
    if not tag:
        return None
    if ":" in tag:
        tag = tag.split(":", 1)[1]
    tag = tag.replace("-", " ").replace("_", " ").strip()
    if not tag:
        return None
    return " ".join(part.capitalize() if part != "and" else part for part in tag.split())


def _friendly_tags(values: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        if not isinstance(raw_value, str):
            continue
        tag = _friendly_tag(raw_value)
        if tag is None:
            continue
        normalized = tag.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(tag)
        if len(cleaned) >= limit:
            break
    return cleaned


def _normalized_token(value: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    normalized = " ".join(normalized.split())
    return normalized or None


def _ingredient_tags(payload: dict[str, Any], *, limit: int = 24) -> list[str]:
    tags = _friendly_tags(payload.get("ingredients_tags"), limit=limit)
    if tags:
        return tags

    ingredients_text = _clean_text(payload.get("ingredients_text")) or _clean_text(payload.get("ingredients_text_en"))
    if ingredients_text is None:
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for fragment in _INGREDIENT_SPLIT_RE.split(ingredients_text):
        candidate = fragment.strip(" .:-")
        if not candidate:
            continue
        normalized = candidate.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(candidate)
        if len(cleaned) >= limit:
            break
    return cleaned


def _ingredient_tokens(tags: list[str], *, limit: int = 32) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = _normalized_token(tag)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        tokens.append(normalized)
        if len(tokens) >= limit:
            break
    return tokens


def _nutrition_summary(nutriments: Any) -> list[ProductNutritionSummaryItem]:
    if not isinstance(nutriments, dict):
        return []

    summary: list[ProductNutritionSummaryItem] = []
    for key, label, default_unit in _NUTRITION_FIELDS:
        value = nutriments.get(f"{key}_100g")
        if value is None:
            value = nutriments.get(key)
        if not isinstance(value, (int, float)):
            continue

        unit = nutriments.get(f"{key}_unit")
        unit_value = unit if isinstance(unit, str) and unit.strip() else default_unit
        summary.append(
            ProductNutritionSummaryItem(
                key=key,
                label=label,
                value=round(float(value), 3),
                unit=unit_value,
            )
        )
    return summary


def _nutrition_summary_text(summary: list[ProductNutritionSummaryItem]) -> str | None:
    if not summary:
        return None
    return " · ".join(
        f"{item.label} {item.value}{f' {item.unit}' if item.unit else ''}"
        for item in summary[:6]
    )


def _dietary_tags(*, labels: list[str], allergen_tags: list[str], trace_tags: list[str]) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for value in [*labels, *allergen_tags, *trace_tags]:
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        tags.append(value)
    return tags[:12]


def _name_confidence(query_name: str, candidate_name: str | None) -> float | None:
    if not candidate_name:
        return None

    normalized_query = normalize_lookup_name(query_name)
    normalized_candidate = normalize_lookup_name(candidate_name)
    if not normalized_query or not normalized_candidate:
        return None
    if normalized_query == normalized_candidate:
        return 0.96
    if normalized_query in normalized_candidate or normalized_candidate in normalized_query:
        return 0.82

    query_tokens = set(normalized_query.split())
    candidate_tokens = set(normalized_candidate.split())
    overlap = len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)
    ratio = SequenceMatcher(a=normalized_query, b=normalized_candidate).ratio()
    return round(min(0.89, (ratio * 0.7) + (overlap * 0.3)), 3)


def _candidate_from_product(
    payload: dict[str, Any],
    *,
    match_status: str,
    match_confidence: float | None,
) -> ProductEnrichmentCandidate | None:
    source_product_id = _clean_text(payload.get("code"))
    if source_product_id is None:
        return None

    source_barcode = _clean_text(payload.get("code"))
    product_name = (
        _clean_text(payload.get("product_name"))
        or _clean_text(payload.get("product_name_en"))
        or _clean_text(payload.get("generic_name"))
        or _clean_text(payload.get("generic_name_en"))
    )
    product_url = _validate_remote_url(payload.get("url")) or (
        f"{OPEN_FOOD_FACTS_BASE_URL}/product/{source_product_id}"
    )
    image_url = _validate_remote_url(payload.get("image_front_url")) or _validate_remote_url(payload.get("image_url"))
    ingredients_text = _clean_text(payload.get("ingredients_text")) or _clean_text(payload.get("ingredients_text_en"))
    allergens_text = _clean_text(payload.get("allergens_from_ingredients")) or _clean_text(payload.get("allergens"))
    traces_text = _clean_text(payload.get("traces"))
    ingredient_tags = _ingredient_tags(payload)
    ingredient_tokens = _ingredient_tokens(ingredient_tags)
    allergen_tags = _friendly_tags(payload.get("allergens_tags"))
    trace_tags = _friendly_tags(payload.get("traces_tags"))
    labels = _friendly_tags(payload.get("labels_tags"))
    categories = _friendly_tags(payload.get("categories_tags"))
    dietary_tags = _dietary_tags(labels=labels, allergen_tags=allergen_tags, trace_tags=trace_tags)
    nutriments_payload = payload.get("nutriments") if isinstance(payload.get("nutriments"), dict) else {}
    nutrition_summary = _nutrition_summary(nutriments_payload)
    nutrition_summary_text = _nutrition_summary_text(nutrition_summary)

    incomplete_fields: list[str] = []
    if image_url is None:
        incomplete_fields.append("image")
    if ingredients_text is None:
        incomplete_fields.append("ingredients")
    if not allergen_tags and allergens_text is None:
        incomplete_fields.append("allergens")
    if not nutrition_summary:
        incomplete_fields.append("nutrition")

    warnings: list[str] = []
    if match_status != "barcode_exact":
        warnings.append("Name search matches are lower confidence than barcode matches.")
    if incomplete_fields:
        warnings.append("Some Open Food Facts fields are missing for this product.")

    return ProductEnrichmentCandidate(
        source_name=OPEN_FOOD_FACTS_SOURCE,
        source_product_id=source_product_id,
        source_barcode=source_barcode,
        source_product_name=product_name,
        source_product_url=product_url,
        product_image_url=image_url,
        enrichment_status="candidate",
        ingredients_text=ingredients_text,
        ingredient_tags=ingredient_tags,
        ingredient_tokens=ingredient_tokens,
        allergens_text=allergens_text,
        traces_text=traces_text,
        allergen_tags=allergen_tags,
        trace_tags=trace_tags,
        dietary_tags=dietary_tags,
        nutriments_payload=nutriments_payload,
        nutrition_summary=nutrition_summary,
        nutrition_summary_text=nutrition_summary_text,
        labels=labels,
        categories=categories,
        match_status=match_status,
        match_confidence=match_confidence,
        incomplete_fields=incomplete_fields,
        warnings=warnings,
        attribution=_attribution(product_url),
    )


@dataclass
class _CacheEntry:
    expires_at: float
    value: Any


@dataclass
class _InFlightRequest:
    event: threading.Event
    value: Any = None
    error: BaseException | None = None


class _OpenFoodFactsResponseCache:
    def __init__(self, *, ttl_seconds: float, max_cache_entries: int):
        self._ttl_seconds = ttl_seconds
        self._max_cache_entries = max_cache_entries
        self._entries: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._in_flight: dict[str, _InFlightRequest] = {}
        self._lock = threading.Lock()

    def get_or_reserve(self, key: str) -> tuple[str, Any | _InFlightRequest | None]:
        with self._lock:
            cached = self._get_cached_locked(key)
            if cached is not None:
                return "hit", cached

            in_flight = self._in_flight.get(key)
            if in_flight is not None:
                return "wait", in_flight

            in_flight = _InFlightRequest(event=threading.Event())
            self._in_flight[key] = in_flight
            return "leader", in_flight

    def complete(
        self,
        key: str,
        request: _InFlightRequest,
        *,
        value: Any = None,
        error: BaseException | None = None,
    ) -> None:
        with self._lock:
            if error is None:
                self._set_cached_locked(key, value)
                request.value = value
            else:
                request.error = error
            self._in_flight.pop(key, None)
            request.event.set()

    def wait_for(self, request: _InFlightRequest) -> Any:
        request.event.wait()
        if request.error is not None:
            raise request.error
        return request.value

    def _get_cached_locked(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= monotonic():
            self._entries.pop(key, None)
            return None
        self._entries.move_to_end(key)
        return entry.value

    def _set_cached_locked(self, key: str, value: Any) -> None:
        self._entries[key] = _CacheEntry(expires_at=monotonic() + self._ttl_seconds, value=value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_cache_entries:
            self._entries.popitem(last=False)


_SHARED_RESPONSE_CACHE = _OpenFoodFactsResponseCache(ttl_seconds=600.0, max_cache_entries=512)


class OpenFoodFactsClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        base_url: str = OPEN_FOOD_FACTS_BASE_URL,
        user_agent: str = "Pantro/1.0 (+https://github.com/RoBro92/pantry)",
        transport: httpx.BaseTransport | None = None,
        ttl_seconds: float = 600.0,
        max_cache_entries: int = 128,
        client_factory: Callable[[], httpx.Client] | None = None,
        shared_cache: bool | None = None,
    ):
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._transport = transport
        self._client_factory = client_factory
        should_share_cache = (
            shared_cache
            if shared_cache is not None
            else transport is None and client_factory is None
        )
        self._cache = (
            _SHARED_RESPONSE_CACHE
            if should_share_cache
            else _OpenFoodFactsResponseCache(ttl_seconds=ttl_seconds, max_cache_entries=max_cache_entries)
        )

    def fetch_product_by_id(self, source_product_id: str) -> ProductEnrichmentCandidate | None:
        response = self._request_json(
            f"/api/v2/product/{source_product_id}.json",
            params={"fields": OPEN_FOOD_FACTS_PRODUCT_FIELDS},
            cache_key=f"product:{source_product_id}",
        )
        product = response.get("product")
        if response.get("status") != 1 or not isinstance(product, dict):
            return None
        return _candidate_from_product(product, match_status="barcode_exact", match_confidence=1.0)

    def lookup_by_barcode(self, barcode: str) -> ProductEnrichmentCandidate | None:
        normalized_barcode = normalize_barcode(barcode)
        return self.fetch_product_by_id(normalized_barcode)

    def search_by_name(self, product_name: str, *, limit: int = 5) -> list[ProductEnrichmentCandidate]:
        query_name = require_text(product_name, field_name="Product name")
        response = self._request_json(
            "/cgi/search.pl",
            params={
                "search_terms": query_name,
                "search_simple": "1",
                "action": "process",
                "json": "1",
                "page_size": str(limit),
            },
            cache_key=f"search:{normalize_lookup_name(query_name)}:{limit}",
        )

        products = response.get("products")
        if not isinstance(products, list):
            return []

        matches: list[ProductEnrichmentCandidate] = []
        seen_source_ids: set[str] = set()
        for payload in products:
            if not isinstance(payload, dict):
                continue
            candidate_name = (
                _clean_text(payload.get("product_name"))
                or _clean_text(payload.get("product_name_en"))
                or _clean_text(payload.get("generic_name"))
                or _clean_text(payload.get("generic_name_en"))
            )
            confidence = _name_confidence(query_name, candidate_name)
            candidate = _candidate_from_product(
                payload,
                match_status="name_search_candidate",
                match_confidence=confidence,
            )
            if candidate is None or candidate.source_product_id in seen_source_ids:
                continue
            seen_source_ids.add(candidate.source_product_id)
            matches.append(candidate)

        matches.sort(
            key=lambda item: (
                item.match_confidence or 0.0,
                item.source_product_name or "",
                len(item.nutrition_summary),
            ),
            reverse=True,
        )
        return matches[:limit]

    def _request_json(self, path: str, *, params: dict[str, str], cache_key: str) -> dict[str, Any]:
        effective_cache_key = f"{self._base_url}:{cache_key}"
        cache_status, cached_or_request = self._cache.get_or_reserve(effective_cache_key)
        if cache_status == "hit":
            return cached_or_request
        if cache_status == "wait":
            return self._cache.wait_for(cached_or_request)
        in_flight_request = cached_or_request

        if self._client_factory is not None:
            client = self._client_factory()
        else:
            client = httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                follow_redirects=True,
                transport=self._transport,
                headers={
                    "Accept": "application/json",
                    "User-Agent": self._user_agent,
                },
            )

        try:
            with client:
                response = client.get(path, params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            error = OpenFoodFactsUnavailableError(
                f"Open Food Facts request failed with status {exc.response.status_code}."
            )
            self._cache.complete(effective_cache_key, in_flight_request, error=error)
            raise error from exc
        except httpx.HTTPError as exc:
            error = OpenFoodFactsUnavailableError("Open Food Facts request failed.")
            self._cache.complete(effective_cache_key, in_flight_request, error=error)
            raise error from exc
        except Exception as exc:
            self._cache.complete(effective_cache_key, in_flight_request, error=exc)
            raise

        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            error = OpenFoodFactsUnavailableError("Open Food Facts returned a non-JSON response.")
            self._cache.complete(effective_cache_key, in_flight_request, error=error)
            raise error

        try:
            payload = response.json()
        except ValueError as exc:
            error = OpenFoodFactsUnavailableError("Open Food Facts returned invalid JSON.")
            self._cache.complete(effective_cache_key, in_flight_request, error=error)
            raise error from exc
        except Exception as exc:
            self._cache.complete(effective_cache_key, in_flight_request, error=exc)
            raise

        if not isinstance(payload, dict):
            error = OpenFoodFactsUnavailableError("Open Food Facts returned an unexpected payload.")
            self._cache.complete(effective_cache_key, in_flight_request, error=error)
            raise error

        self._cache.complete(effective_cache_key, in_flight_request, value=payload)
        return payload
