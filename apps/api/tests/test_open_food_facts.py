from __future__ import annotations

import httpx
import pytest

from app.services.open_food_facts import OpenFoodFactsClient, OpenFoodFactsUnavailableError


def test_barcode_lookup_maps_useful_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/product/5000111046244.json"
        assert "fields=" in str(request.url)
        return httpx.Response(
            200,
            json={
                "status": 1,
                "product": {
                    "code": "5000111046244",
                    "product_name": "HP Brown Sauce",
                    "image_front_url": "https://images.example.test/hp.jpg",
                    "ingredients_text": "Tomatoes, barley malt vinegar, molasses",
                    "allergens_from_ingredients": "Gluten",
                    "allergens_tags": ["en:gluten"],
                    "traces": "Mustard",
                    "traces_tags": ["en:mustard"],
                    "labels_tags": ["en:vegetarian"],
                    "categories_tags": ["en:brown-sauces"],
                    "nutriments": {
                        "energy-kcal_100g": 100,
                        "energy-kcal_unit": "kcal",
                        "salt_100g": 1.2,
                        "salt_unit": "g",
                    },
                    "url": "https://world.openfoodfacts.org/product/5000111046244/hp-brown-sauce",
                },
            },
        )

    client = OpenFoodFactsClient(transport=httpx.MockTransport(handler))
    candidate = client.lookup_by_barcode("5000111046244")

    assert candidate is not None
    assert candidate.source_product_id == "5000111046244"
    assert candidate.source_product_name == "HP Brown Sauce"
    assert candidate.match_status == "barcode_exact"
    assert candidate.match_confidence == 1.0
    assert candidate.allergen_tags == ["Gluten"]
    assert candidate.trace_tags == ["Mustard"]
    assert [item.key for item in candidate.nutrition_summary] == ["energy-kcal", "salt"]


def test_name_search_returns_multiple_candidates_and_marks_partial_data():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cgi/search.pl"
        return httpx.Response(
            200,
            json={
                "products": [
                    {
                        "code": "5000111046244",
                        "product_name": "HP Brown Sauce",
                        "ingredients_text": "Tomatoes, vinegar",
                        "allergens_tags": ["en:gluten"],
                        "labels_tags": ["en:vegetarian"],
                        "categories_tags": ["en:brown-sauces"],
                        "nutriments": {"energy-kcal_100g": 100, "energy-kcal_unit": "kcal"},
                        "url": "https://world.openfoodfacts.org/product/5000111046244/hp-brown-sauce",
                    },
                    {
                        "code": "5000111046245",
                        "product_name": "HP Fruity Brown Sauce",
                        "categories_tags": ["en:brown-sauces"],
                        "url": "https://world.openfoodfacts.org/product/5000111046245/hp-fruity-brown-sauce",
                    },
                ]
            },
        )

    client = OpenFoodFactsClient(transport=httpx.MockTransport(handler))
    candidates = client.search_by_name("HP brown sauce")

    assert len(candidates) == 2
    assert candidates[0].source_product_name == "HP Brown Sauce"
    assert candidates[0].match_status == "name_search_candidate"
    assert candidates[0].match_confidence is not None
    assert candidates[1].incomplete_fields == ["image", "ingredients", "allergens", "nutrition"]
    assert "Some Open Food Facts fields are missing for this product." in candidates[1].warnings


def test_no_match_returns_none_or_empty_list():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/api/v2/product/"):
            return httpx.Response(200, json={"status": 0, "status_verbose": "product not found"})
        return httpx.Response(200, json={"products": []})

    client = OpenFoodFactsClient(transport=httpx.MockTransport(handler))

    assert client.lookup_by_barcode("1234567890123") is None
    assert client.search_by_name("Nonexistent product") == []


def test_service_raises_unavailable_for_non_json_or_http_errors():
    def status_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    error_client = OpenFoodFactsClient(transport=httpx.MockTransport(status_handler))
    with pytest.raises(OpenFoodFactsUnavailableError):
        error_client.search_by_name("HP brown sauce")

    def html_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>oops</html>", headers={"content-type": "text/html"})

    html_client = OpenFoodFactsClient(transport=httpx.MockTransport(html_handler))
    with pytest.raises(OpenFoodFactsUnavailableError):
        html_client.lookup_by_barcode("5000111046244")
