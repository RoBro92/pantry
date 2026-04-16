from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.domain.ai import AI_PROVIDER_OLLAMA, AI_PROVIDER_OPENAI
from app.domain.roles import HOUSEHOLD_ADMIN_ROLE, HOUSEHOLD_USER_ROLE
from app.models.audit_event import AuditEvent
from app.models.product import Product
from app.models.product_enrichment import ProductEnrichment
from app.models.product_intelligence import ProductIntelligence
from app.models.product_intelligence_run import ProductIntelligenceRun
from app.schemas.pantry import ProductEnrichmentAttribution, ProductEnrichmentCandidate, ProductNutritionSummaryItem
from app.models.stock_lot import StockLot
from app.services.ai_config import upsert_instance_provider_config
from app.services.ai_providers import AIProviderHealth, StructuredCompletionResult
from app.services.ai_providers.errors import AIProviderError
from app.services.auth import create_household, create_membership, create_platform_admin, create_user
from app.services.pantry_catalog import create_location as create_location_record
from app.services.pantry_catalog import create_location_group as create_location_group_record
from app.services.pantry_catalog import create_product as create_product_record
from app.services.pantry_stock import add_stock_lot as add_stock_lot_record
from app.services.product_intelligence import (
    PRODUCT_INTELLIGENCE_EXECUTION_AI_GAP_FILL,
    PRODUCT_INTELLIGENCE_EXECUTION_DERIVED_ONLY,
    PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI,
    PRODUCT_INTELLIGENCE_SOURCE_PROVIDER_DERIVED,
    PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
    PRODUCT_INTELLIGENCE_PATH_AI_GAP_FILL,
    PRODUCT_INTELLIGENCE_PATH_DERIVED_ONLY,
    PRODUCT_INTELLIGENCE_PATH_FULL_AI,
    PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
    PRODUCT_INTELLIGENCE_SCOPE,
    ProductClassificationBatchOutput,
    ProductIntelligenceStaleness,
    build_product_intelligence_batch_source_payload,
    build_product_intelligence_execution_plan,
    build_product_intelligence_source_data_hash,
    build_product_intelligence_source_payload,
    get_product_intelligence_staleness,
    get_product_intelligence_runtime_trim_level,
    estimate_product_intelligence_tokens,
)
from app.services.product_intelligence_profiles import get_default_supported_model, resolve_product_intelligence_profile
from app.services.product_intelligence_runs import process_next_product_intelligence_run
from app.services.product_intelligence_runs import PreparedClassificationCandidate, _build_batches


PASSWORD = "correct horse battery"


def login(client, *, email: str, password: str = PASSWORD) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


def create_member_household(db_session, *, email: str, household_name: str):
    user = create_user(db_session, email=email, password=PASSWORD, display_name=email.split("@")[0].title())
    household = create_household(db_session, name=household_name)
    create_membership(
        db_session,
        user=user,
        household=household,
        role_code=HOUSEHOLD_USER_ROLE,
    )
    return user, household


def create_household_with_role(db_session, *, email: str, household_name: str, role_code: str):
    user = create_user(db_session, email=email, password=PASSWORD, display_name=email.split("@")[0].title())
    household = create_household(db_session, name=household_name)
    create_membership(
        db_session,
        user=user,
        household=household,
        role_code=role_code,
    )
    return user, household


def create_location_group(client, household_external_id: str, name: str) -> dict:
    response = client.post(
        f"/api/households/{household_external_id}/location-groups",
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()


def create_location(client, household_external_id: str, location_group_external_id: str, name: str) -> dict:
    response = client.post(
        f"/api/households/{household_external_id}/locations",
        json={"location_group_external_id": location_group_external_id, "name": name},
    )
    assert response.status_code == 201
    return response.json()


def create_product(client, household_external_id: str, **payload) -> dict:
    response = client.post(f"/api/households/{household_external_id}/products", json=payload)
    assert response.status_code == 201
    return response.json()


def update_product(client, household_external_id: str, product_external_id: str, **payload) -> dict:
    response = client.put(
        f"/api/households/{household_external_id}/products/{product_external_id}",
        json=payload,
    )
    assert response.status_code == 200
    return response.json()


def add_stock_lot(client, household_external_id: str, **payload) -> dict:
    response = client.post(f"/api/households/{household_external_id}/stock-lots", json=payload)
    assert response.status_code == 201
    return response.json()


def create_pantry_entry(client, household_external_id: str, **payload) -> dict:
    response = client.post(f"/api/households/{household_external_id}/pantry/entries", json=payload)
    assert response.status_code == 200
    return response.json()


def build_enrichment_candidate(
    *,
    source_product_id: str,
    source_product_name: str,
    match_status: str,
    match_confidence: float,
) -> ProductEnrichmentCandidate:
    return ProductEnrichmentCandidate(
        source_name="open_food_facts",
        source_product_id=source_product_id,
        source_barcode=source_product_id,
        source_product_name=source_product_name,
        source_product_url=f"https://world.openfoodfacts.org/product/{source_product_id}",
        product_image_url="https://images.example.test/product.jpg",
        enrichment_status="candidate",
        ingredients_text="Tomatoes, vinegar, barley malt",
        ingredient_tags=["tomatoes", "vinegar", "barley-malt"],
        ingredient_tokens=["tomatoes", "vinegar", "barley", "malt"],
        allergens_text="Gluten",
        traces_text="Mustard",
        allergen_tags=["Gluten"],
        trace_tags=["Mustard"],
        dietary_tags=["vegetarian"],
        nutriments_payload={"energy-kcal_100g": 100, "salt_100g": 1.2},
        nutrition_summary=[
            ProductNutritionSummaryItem(key="energy-kcal", label="Energy", value=100, unit="kcal"),
            ProductNutritionSummaryItem(key="salt", label="Salt", value=1.2, unit="g"),
        ],
        nutrition_summary_text="Energy 100 kcal per 100 g · Salt 1.2 g per 100 g",
        labels=["Vegetarian"],
        categories=["Brown Sauces"],
        match_status=match_status,
        match_confidence=match_confidence,
        incomplete_fields=[],
        warnings=[],
        attribution=ProductEnrichmentAttribution(
            source_name="open_food_facts",
            source_label="Open Food Facts",
            source_url="https://world.openfoodfacts.org",
            product_url=f"https://world.openfoodfacts.org/product/{source_product_id}",
            data_notice="Community-contributed Open Food Facts data may be incomplete or inaccurate.",
            license_name="Open Database License",
            license_url="https://opendatacommons.org/licenses/odbl/",
        ),
    )


def _stub_product_intelligence_output(product_name: str) -> dict[str, object]:
    if "sauce" in product_name.lower():
        return {
            "confidence": 0.92,
            "rationale_short": "Condiment evidence is clear from the product and enrichment data.",
            "primary_ingredient_type": "Tomato",
            "ingredient_families": ["Tomato", "Vinegar"],
            "food_category": "Condiment",
            "dietary_tags": ["Vegetarian"],
            "allergen_tags": ["Gluten"],
            "recipe_role_tags": ["Sauce", "Seasoning"],
            "substitution_groups": ["Brown sauce"],
            "pantry_use_tags": ["Pantry staple", "Sauce builder", "Shelf stable"],
            "structured_metadata": {
                "product_format": "Bottled sauce",
                "storage_profile": "Shelf stable",
                "cuisine_tags": ["British"],
                "flavour_tags": ["Tangy", "Savoury"],
                "preparation_tags": ["Ready to use"],
            },
        }
    return {
        "confidence": 0.88,
        "rationale_short": "Core pantry staple with a clear starch role.",
        "primary_ingredient_type": "Wheat",
        "ingredient_families": ["Wheat"],
        "food_category": "Dry pasta",
        "dietary_tags": [],
        "allergen_tags": ["Gluten"],
        "recipe_role_tags": ["Carbohydrate", "Base"],
        "substitution_groups": ["Pasta"],
        "pantry_use_tags": ["Pantry staple", "Quick meal", "Shelf stable"],
        "structured_metadata": {
            "product_format": "Dried",
            "storage_profile": "Shelf stable",
            "cuisine_tags": ["Italian"],
            "flavour_tags": ["Neutral"],
            "preparation_tags": ["Boil"],
        },
    }


class StubProductIntelligenceAdapter:
    def __init__(self, *, fail_attempts: int = 0, omitted_product_external_ids: set[str] | None = None):
        self.fail_attempts = fail_attempts
        self.omitted_product_external_ids = omitted_product_external_ids or set()
        self.batches: list[list[str]] = []
        self.product_payloads: list[list[dict[str, object]]] = []

    def generate_structured_output(self, request) -> StructuredCompletionResult:
        if self.fail_attempts > 0:
            self.fail_attempts -= 1
            request_obj = httpx.Request("POST", "http://ollama.test/api/chat")
            raise httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=request_obj,
                response=httpx.Response(429, request=request_obj),
            )

        products = request.user_payload["products"]
        self.batches.append([product["product_external_id"] for product in products])
        self.product_payloads.append(list(products))
        output = {
            "items": [
                {
                    "product_external_id": product["product_external_id"],
                    **_stub_product_intelligence_output(product["product"]["name"]),
                }
                for product in products
                if product["product_external_id"] not in self.omitted_product_external_ids
            ]
        }
        return StructuredCompletionResult(
            output_text=str(output),
            parsed_output=output,
            provider_request_id="req_product_intelligence_stub",
        )


def install_stub_product_intelligence_provider(
    db_session,
    monkeypatch,
    *,
    adapter: StubProductIntelligenceAdapter | None = None,
) -> StubProductIntelligenceAdapter:
    stub_adapter = adapter or StubProductIntelligenceAdapter()
    platform_admin = create_platform_admin(
        db_session,
        email="platform-admin@example.com",
        password=PASSWORD,
        display_name="Platform Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=platform_admin,
        provider_type=AI_PROVIDER_OLLAMA,
        base_url="http://ollama.test",
        default_model="llama3.2",
        api_key=None,
        is_enabled=True,
    )
    monkeypatch.setattr(
        "app.services.product_intelligence_runs.refresh_provider_health",
        lambda db, config: AIProviderHealth(
            is_healthy=True,
            status="healthy",
            message=None,
            models=["llama3.2"],
            capabilities={"supports_structured_output": True},
        ),
    )
    monkeypatch.setattr(
        "app.services.product_intelligence_runs.build_ai_provider_adapter",
        lambda runtime: stub_adapter,
    )
    return stub_adapter


def test_pantry_overview_aggregates_and_supports_search_and_filters(client, db_session):
    user, household = create_household_with_role(
        db_session,
        email="cook@example.com",
        household_name="Cook Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    hidden_user, hidden_household = create_member_household(
        db_session,
        email="other@example.com",
        household_name="Other Household",
    )

    login(client, email="cook@example.com")

    pantry_group = create_location_group(client, household.external_id, "Kitchen Pantry")
    freezer_group = create_location_group(client, household.external_id, "Freezer")
    shelf = create_location(client, household.external_id, pantry_group["external_id"], "Top Shelf")
    drawer = create_location(client, household.external_id, freezer_group["external_id"], "Drawer")
    product = create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="Count",
        aliases=["Spaghetti", "Dry Pasta"],
        barcodes=["00123"],
    )

    add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="2.500",
        expires_on=str(date.today() + timedelta(days=5)),
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=drawer["external_id"],
        quantity="1.000",
        expires_on=str(date.today() + timedelta(days=20)),
    )

    hidden_group = create_location_group_record(
        db_session,
        household=hidden_household,
        actor=hidden_user,
        name="Hidden Pantry",
    )
    hidden_location = create_location_record(
        db_session,
        household=hidden_household,
        actor=hidden_user,
        location_group_external_id=hidden_group.external_id,
        name="Back Shelf",
    )
    hidden_product = create_product_record(
        db_session,
        household=hidden_household,
        actor=hidden_user,
        name="Beans",
        default_unit="can",
        aliases=[],
        barcodes=[],
    )
    add_stock_lot_record(
        db_session,
        household=hidden_household,
        actor=hidden_user,
        product_external_id=hidden_product.external_id,
        location_external_id=hidden_location.external_id,
        quantity=Decimal("4.000"),
        note=None,
        purchased_on=None,
        expires_on=None,
    )

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert overview.status_code == 200
    payload = overview.json()

    assert payload["counts"]["location_group_count"] == 2
    assert payload["counts"]["location_count"] == 2
    assert payload["counts"]["product_count"] == 1
    assert payload["counts"]["active_lot_count"] == 2
    assert payload["counts"]["near_expiry_lot_count"] == 1
    assert len(payload["products"]) == 1
    assert Decimal(payload["products"][0]["total_quantity"]) == Decimal("3.500")
    assert {location["location_name"] for location in payload["products"][0]["locations"]} == {"Top Shelf", "Drawer"}
    assert len(payload["recent_events"]) >= 4

    alias_search = client.get(
        f"/api/households/{household.external_id}/pantry/overview",
        params={"q": "spaghetti"},
    )
    assert alias_search.status_code == 200
    assert alias_search.json()["products"][0]["product_name"] == "Pasta"

    barcode_search = client.get(
        f"/api/households/{household.external_id}/pantry/overview",
        params={"q": "00123"},
    )
    assert barcode_search.status_code == 200
    assert barcode_search.json()["products"][0]["product_name"] == "Pasta"

    freezer_only = client.get(
        f"/api/households/{household.external_id}/pantry/overview",
        params={"location_group_external_id": freezer_group["external_id"]},
    )
    assert freezer_only.status_code == 200
    freezer_payload = freezer_only.json()
    assert len(freezer_payload["stock_lots"]) == 1
    assert freezer_payload["stock_lots"][0]["location_name"] == "Drawer"

    near_expiry = client.get(
        f"/api/households/{household.external_id}/pantry/near-expiry",
        params={"days": 7},
    )
    assert near_expiry.status_code == 200
    near_expiry_payload = near_expiry.json()
    assert len(near_expiry_payload["lots"]) == 1
    assert near_expiry_payload["lots"][0]["location_name"] == "Top Shelf"


def test_product_intelligence_run_supports_product_and_unclassified_modes(client, db_session, monkeypatch):
    _, household = create_household_with_role(
        db_session,
        email="classification@example.com",
        household_name="Classification Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    stub_adapter = install_stub_product_intelligence_provider(db_session, monkeypatch)
    login(client, email="classification@example.com")

    sauce = create_product(
        client,
        household.external_id,
        name="Brown sauce",
        default_unit="bottle",
        aliases=["HP sauce"],
        barcodes=["5000111046244"],
        manual_ingredient_tags=["Tomatoes", "Vinegar"],
    )
    pasta = create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="pack",
        aliases=["Spaghetti"],
        barcodes=[],
    )

    initial_status = client.get(f"/api/households/{household.external_id}/product-intelligence/status")
    assert initial_status.status_code == 200
    assert initial_status.json()["counts"] == {
        "total_product_count": 2,
        "classified_product_count": 0,
        "stale_product_count": 0,
        "unclassified_product_count": 2,
    }

    product_run = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "product", "product_external_id": sauce["external_id"]},
    )
    assert product_run.status_code == 200
    product_run_payload = product_run.json()
    assert product_run_payload["status"] == "queued"
    assert product_run_payload["total_candidates"] == 1
    assert product_run_payload["processed_count"] == 0
    assert product_run_payload["created"] is True

    queued_run = db_session.scalar(select(ProductIntelligenceRun))
    assert queued_run is not None
    assert queued_run.status == "queued"

    assert process_next_product_intelligence_run() is True
    assert stub_adapter.batches == [[sauce["external_id"]]]

    product_run_detail = client.get(
        f"/api/households/{household.external_id}/product-intelligence/runs/{product_run_payload['external_id']}"
    )
    assert product_run_detail.status_code == 200
    product_run_detail_payload = product_run_detail.json()
    assert product_run_detail_payload["status"] == "completed"
    assert product_run_detail_payload["classified_count"] == 1
    assert product_run_detail_payload["items"][0]["status"] == "classified"
    assert product_run_detail_payload["items"][0]["intelligence"]["food_category"] == "Condiment"

    intelligence_record = db_session.scalar(select(ProductIntelligence).where(ProductIntelligence.product_id.is_not(None)))
    assert intelligence_record is not None
    assert intelligence_record.food_category == "Condiment"

    unclassified_run = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "unclassified"},
    )
    assert unclassified_run.status_code == 200
    unclassified_payload = unclassified_run.json()
    assert unclassified_payload["status"] == "queued"
    assert unclassified_payload["total_candidates"] == 2

    assert process_next_product_intelligence_run() is True
    assert stub_adapter.batches[-1] == [pasta["external_id"]]

    unclassified_detail = client.get(
        f"/api/households/{household.external_id}/product-intelligence/runs/{unclassified_payload['external_id']}"
    )
    assert unclassified_detail.status_code == 200
    unclassified_detail_payload = unclassified_detail.json()
    assert unclassified_detail_payload["status"] == "completed"
    assert unclassified_detail_payload["processed_count"] == 2
    assert unclassified_detail_payload["classified_count"] == 1
    assert unclassified_detail_payload["skipped_count"] == 1
    assert {item["status"] for item in unclassified_detail_payload["items"]} == {"classified", "skipped"}

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert overview.status_code == 200
    products = overview.json()["products"]
    intelligence_by_name = {item["product_name"]: item["intelligence"] for item in products}
    assert intelligence_by_name["Brown sauce"]["food_category"] == "Condiment"
    assert intelligence_by_name["Pasta"]["food_category"] == "Dry pasta"

    refreshed_status = client.get(f"/api/households/{household.external_id}/product-intelligence/status")
    assert refreshed_status.status_code == 200
    assert refreshed_status.json()["latest_run"]["external_id"] == unclassified_payload["external_id"]


def test_product_intelligence_marks_stale_after_material_product_update(client, db_session, monkeypatch):
    _, household = create_household_with_role(
        db_session,
        email="classification-stale@example.com",
        household_name="Classification Stale Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    install_stub_product_intelligence_provider(db_session, monkeypatch)
    login(client, email="classification-stale@example.com")

    product = create_product(
        client,
        household.external_id,
        name="Brown sauce",
        default_unit="bottle",
        aliases=[],
        barcodes=["5000111046244"],
        manual_ingredient_tags=["Tomatoes"],
    )

    classify = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "product", "product_external_id": product["external_id"]},
    )
    assert classify.status_code == 200
    assert process_next_product_intelligence_run() is True

    updated = update_product(
        client,
        household.external_id,
        product["external_id"],
        name="Brown sauce",
        default_unit="bottle",
        aliases=["Breakfast sauce"],
        barcodes=["5000111046244"],
        notes="Use on bacon rolls.",
        manual_ingredient_tags=["Tomatoes", "Vinegar"],
    )
    assert updated["intelligence"]["is_stale"] is True
    assert "source_product_data_changed" in updated["intelligence"]["stale_reasons"]

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert overview.status_code == 200
    intelligence = overview.json()["catalog_products"][0]["intelligence"]
    assert intelligence["is_stale"] is True
    assert "source_product_data_changed" in intelligence["stale_reasons"]


def test_product_intelligence_run_derives_high_confidence_off_staples_without_ai(
    client,
    db_session,
    monkeypatch,
):
    _, household = create_household_with_role(
        db_session,
        email="classification-derived@example.com",
        household_name="Classification Derived Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    stub_adapter = install_stub_product_intelligence_provider(db_session, monkeypatch)
    login(client, email="classification-derived@example.com")

    product = create_product(
        client,
        household.external_id,
        name="Chickpeas",
        default_unit="can",
        aliases=[],
        barcodes=["1234567890123"],
    )
    stored_product = db_session.scalar(select(Product).where(Product.external_id == product["external_id"]))
    assert stored_product is not None
    db_session.add(
        ProductEnrichment(
            household_id=household.id,
            product=stored_product,
            source_name="open_food_facts",
            source_product_id="1234567890123",
            source_barcode="1234567890123",
            source_product_name="Chickpeas in water",
            ingredients_text="Chickpeas, water, salt",
            ingredient_tags=[],
            allergen_tags=[],
            dietary_tags=["vegan"],
            categories=["Legumes", "Chickpeas"],
            match_status="barcode_exact",
            match_confidence=1.0,
        )
    )
    db_session.commit()

    queued = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "all"},
    )
    assert queued.status_code == 200

    assert process_next_product_intelligence_run() is True
    assert stub_adapter.batches == []

    run_detail = client.get(
        f"/api/households/{household.external_id}/product-intelligence/runs/{queued.json()['external_id']}"
    )
    assert run_detail.status_code == 200
    payload = run_detail.json()
    assert payload["classified_count"] == 1
    assert payload["batch_count"] == 0
    assert payload["items"][0]["message"] == "Derived product intelligence saved from OFF facts."
    assert payload["items"][0]["intelligence"]["source_provider"] == PRODUCT_INTELLIGENCE_SOURCE_PROVIDER_DERIVED
    assert payload["items"][0]["intelligence"]["food_category"] == "Legumes"


def test_product_intelligence_run_uses_ai_gap_fill_for_semantic_off_products(
    client,
    db_session,
    monkeypatch,
):
    _, household = create_household_with_role(
        db_session,
        email="classification-gap-fill@example.com",
        household_name="Classification Gap Fill Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    stub_adapter = install_stub_product_intelligence_provider(db_session, monkeypatch)
    login(client, email="classification-gap-fill@example.com")

    product = create_product(
        client,
        household.external_id,
        name="Brown sauce",
        default_unit="bottle",
        aliases=["HP sauce"],
        barcodes=["5000111046244"],
    )
    stored_product = db_session.scalar(select(Product).where(Product.external_id == product["external_id"]))
    assert stored_product is not None
    db_session.add(
        ProductEnrichment(
            household_id=household.id,
            product=stored_product,
            source_name="open_food_facts",
            source_product_id="5000111046244",
            source_barcode="5000111046244",
            source_product_name="HP Brown Sauce",
            ingredients_text="Tomatoes, vinegar, barley malt",
            ingredient_tags=["tomatoes", "vinegar", "barley-malt"],
            allergen_tags=["Gluten"],
            dietary_tags=["vegetarian"],
            categories=["Condiments", "Sauces", "Brown Sauces"],
            match_status="barcode_exact",
            match_confidence=1.0,
        )
    )
    db_session.commit()

    queued = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "all"},
    )
    assert queued.status_code == 200

    assert process_next_product_intelligence_run() is True
    assert stub_adapter.batches == [[product["external_id"]]]
    assert stub_adapter.product_payloads[0][0]["classification_strategy"] == PRODUCT_INTELLIGENCE_EXECUTION_AI_GAP_FILL

    intelligence = db_session.scalar(select(ProductIntelligence).where(ProductIntelligence.product_id == stored_product.id))
    assert intelligence is not None
    assert intelligence.source_provider == AI_PROVIDER_OLLAMA
    assert intelligence.food_category == "Brown Sauces"
    assert intelligence.dietary_tags == ["Vegetarian"]
    assert intelligence.recipe_role_tags == ["Sauce", "Seasoning"]


def test_product_intelligence_run_keeps_manual_products_on_full_ai_path(
    client,
    db_session,
    monkeypatch,
):
    _, household = create_household_with_role(
        db_session,
        email="classification-manual-path@example.com",
        household_name="Classification Manual Path Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    stub_adapter = install_stub_product_intelligence_provider(db_session, monkeypatch)
    login(client, email="classification-manual-path@example.com")

    product = create_product(
        client,
        household.external_id,
        name="Bacon",
        default_unit="pack",
        aliases=[],
        barcodes=[],
        manual_ingredient_tags=["Pork"],
    )

    queued = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "all"},
    )
    assert queued.status_code == 200

    assert process_next_product_intelligence_run() is True
    assert stub_adapter.batches == [[product["external_id"]]]
    assert stub_adapter.product_payloads[0][0]["classification_strategy"] == PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI

    stored_product = db_session.scalar(select(Product).where(Product.external_id == product["external_id"]))
    assert stored_product is not None
    intelligence = db_session.scalar(select(ProductIntelligence).where(ProductIntelligence.product_id == stored_product.id))
    assert intelligence is not None
    assert intelligence.source_provider == AI_PROVIDER_OLLAMA


def test_product_intelligence_run_reports_paths_and_token_diagnostics(client, db_session, monkeypatch):
    _, household = create_household_with_role(
        db_session,
        email="classification-diagnostics@example.com",
        household_name="Classification Diagnostics Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    stub_adapter = install_stub_product_intelligence_provider(db_session, monkeypatch)
    login(client, email="classification-diagnostics@example.com")

    chickpeas = create_product(
        client,
        household.external_id,
        name="Chickpeas",
        default_unit="can",
        aliases=[],
        barcodes=["1234567890123"],
    )
    sauce = create_product(
        client,
        household.external_id,
        name="Brown sauce",
        default_unit="bottle",
        aliases=["HP sauce"],
        barcodes=["5000111046244"],
    )
    bacon = create_product(
        client,
        household.external_id,
        name="Bacon",
        default_unit="pack",
        aliases=[],
        barcodes=[],
        notes="Smoked rashers for quick breakfasts.",
        manual_ingredient_tags=["Pork"],
    )

    chickpeas_product = db_session.scalar(select(Product).where(Product.external_id == chickpeas["external_id"]))
    sauce_product = db_session.scalar(select(Product).where(Product.external_id == sauce["external_id"]))
    bacon_product = db_session.scalar(select(Product).where(Product.external_id == bacon["external_id"]))
    assert chickpeas_product is not None
    assert sauce_product is not None
    assert bacon_product is not None

    db_session.add_all(
        [
            ProductEnrichment(
                household_id=household.id,
                product=chickpeas_product,
                source_name="open_food_facts",
                source_product_id="1234567890123",
                source_barcode="1234567890123",
                source_product_name="Chickpeas in water",
                ingredients_text="Chickpeas, water, salt",
                ingredient_tags=[],
                allergen_tags=[],
                dietary_tags=["vegan"],
                categories=["Legumes", "Chickpeas"],
                match_status="barcode_exact",
                match_confidence=1.0,
            ),
            ProductEnrichment(
                household_id=household.id,
                product=sauce_product,
                source_name="open_food_facts",
                source_product_id="5000111046244",
                source_barcode="5000111046244",
                source_product_name="HP Brown Sauce",
                ingredients_text="Tomatoes, vinegar, barley malt",
                ingredient_tags=["tomatoes", "vinegar", "barley-malt"],
                allergen_tags=["Gluten"],
                dietary_tags=["vegetarian"],
                categories=["Condiments", "Sauces", "Brown Sauces"],
                match_status="barcode_exact",
                match_confidence=1.0,
            ),
        ]
    )
    db_session.commit()

    queued = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "all"},
    )
    assert queued.status_code == 200

    assert process_next_product_intelligence_run() is True

    run_detail = client.get(
        f"/api/households/{household.external_id}/product-intelligence/runs/{queued.json()['external_id']}"
    )
    assert run_detail.status_code == 200
    payload = run_detail.json()
    assert payload["status"] == "completed"
    assert payload["diagnostics"]["path_counts"] == {
        "derived_only": 1,
        "ai_gap_fill": 1,
        "full_ai": 1,
    }
    assert payload["diagnostics"]["ai_batch_count"] == 2
    assert payload["diagnostics"]["completed_ai_batch_count"] == 2
    assert payload["diagnostics"]["token_summary"]["approx_total_tokens"] > 0
    assert {batch["path"] for batch in payload["diagnostics"]["batches"]} == {
        PRODUCT_INTELLIGENCE_PATH_AI_GAP_FILL,
        PRODUCT_INTELLIGENCE_PATH_FULL_AI,
    }
    item_paths = {item["product_name"]: item["path"] for item in payload["items"]}
    assert item_paths == {
        "Bacon": PRODUCT_INTELLIGENCE_PATH_FULL_AI,
        "Brown sauce": PRODUCT_INTELLIGENCE_PATH_AI_GAP_FILL,
        "Chickpeas": PRODUCT_INTELLIGENCE_PATH_DERIVED_ONLY,
    }
    assert chickpeas["external_id"] not in [external_id for batch in stub_adapter.batches for external_id in batch]


def test_product_intelligence_source_payload_uses_ai_gap_fill_for_semantic_off_products(db_session):
    actor, household = create_household_with_role(
        db_session,
        email="classification-payload@example.com",
        household_name="Classification Payload Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    product = create_product_record(
        db_session,
        household=household,
        actor=actor,
        name="Brown sauce",
        default_unit="bottle",
        aliases=["HP sauce", "Breakfast sauce"],
        barcodes=["5000111046244"],
        notes="Use sparingly with breakfast sandwiches.",
        manual_ingredient_tags=["Tomatoes"],
    )
    enrichment = ProductEnrichment(
        household_id=household.id,
        product=product,
        source_name="open_food_facts",
        source_product_id="5000111046244",
        source_barcode="5000111046244",
        source_product_name="HP Brown Sauce",
        ingredients_text="Tomatoes, vinegar, barley malt",
        ingredient_tags=["tomatoes", "vinegar", "barley-malt"],
        ingredient_tokens=["tomatoes", "vinegar", "barley", "malt"],
        allergen_tags=["Gluten"],
        trace_tags=["Mustard"],
        dietary_tags=["vegetarian"],
        labels=["Vegetarian"],
        categories=["Condiments", "Sauces", "Brown Sauces"],
        nutriments_payload={"energy-kcal_100g": 100, "salt_100g": 1.2},
        nutrition_summary=[
            {"label": "Energy", "value": 100, "unit": "kcal"},
            {"label": "Salt", "value": 1.2, "unit": "g"},
        ],
        nutrition_summary_text="Energy 100 kcal per 100 g · Salt 1.2 g per 100 g",
        match_status="barcode_exact",
        match_confidence=1.0,
    )
    db_session.add(enrichment)
    db_session.flush()

    payload = build_product_intelligence_source_payload(
        product,
        provider_type="ollama",
        model="llama3.2",
    )

    assert payload["classification_strategy"] == PRODUCT_INTELLIGENCE_EXECUTION_AI_GAP_FILL
    assert payload["product"]["name"] == "Brown sauce"
    assert payload["product"]["default_unit"] == "bottle"
    assert payload["product"]["aliases"] == ["HP sauce", "Breakfast sauce"]
    assert payload["product"]["manual_ingredient_tags"] == ["Tomatoes"]
    assert payload["derived_facts"]["food_category"] == "Brown Sauces"
    assert payload["derived_facts"]["dietary_tags"] == ["Vegetarian"]
    assert payload["derived_facts"]["allergen_tags"] == ["Gluten"]
    assert payload["gap_signals"]["source_product_name"] == "HP Brown Sauce"
    assert payload["gap_signals"]["ingredient_tags"] == ["tomatoes", "vinegar", "barley-malt"]
    assert payload["gap_signals"]["category_hint"] == "Brown Sauces"


def test_product_intelligence_source_payload_preserves_manual_products_without_enrichment(db_session):
    actor, household = create_household_with_role(
        db_session,
        email="classification-manual@example.com",
        household_name="Classification Manual Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    product = create_product_record(
        db_session,
        household=household,
        actor=actor,
        name="Butter beans",
        default_unit="can",
        aliases=["Tinned butter beans"],
        barcodes=[],
        notes="Good in quick soups and stews.",
        manual_ingredient_tags=["Beans", "Water"],
    )

    payload = build_product_intelligence_source_payload(
        product,
        provider_type="ollama",
        model="llama3.2",
    )

    assert payload["classification_strategy"] == PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI
    assert payload["product"]["name"] == "Butter beans"
    assert payload["product"]["aliases"] == ["Tinned butter beans"]
    assert payload["product"]["notes"] == "Good in quick soups and stews."
    assert payload["product"]["manual_ingredient_tags"] == ["Beans", "Water"]
    assert payload["enrichment"] is None


def test_product_intelligence_source_payload_derives_high_confidence_packaged_staples_without_ai(db_session):
    actor, household = create_household_with_role(
        db_session,
        email="classification-fallback@example.com",
        household_name="Classification Fallback Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    product = create_product_record(
        db_session,
        household=household,
        actor=actor,
        name="Chickpeas",
        default_unit="can",
        aliases=[],
        barcodes=["1234567890123"],
    )
    enrichment = ProductEnrichment(
        household_id=household.id,
        product=product,
        source_name="open_food_facts",
        source_product_id="1234567890123",
        source_barcode="1234567890123",
        source_product_name="Chickpeas in water",
        ingredients_text="Chickpeas, water, salt",
        ingredient_tags=[],
        allergen_tags=[],
        dietary_tags=["vegan"],
        categories=["Legumes", "Chickpeas"],
        match_status="barcode_exact",
        match_confidence=1.0,
    )
    db_session.add(enrichment)
    db_session.flush()

    payload = build_product_intelligence_source_payload(
        product,
        provider_type="ollama",
        model="llama3.2",
    )

    assert payload["classification_strategy"] == PRODUCT_INTELLIGENCE_EXECUTION_DERIVED_ONLY
    assert payload["derived_facts"]["food_category"] == "Legumes"
    assert payload["derived_facts"]["primary_ingredient_type"] == "Legumes"
    assert payload["derived_facts"]["structured_metadata"]["product_format"] == "Canned"
    assert payload["derived_facts"]["dietary_tags"] == ["Vegan"]


def test_product_intelligence_source_payload_keeps_weak_off_products_on_full_ai_path(db_session):
    actor, household = create_household_with_role(
        db_session,
        email="classification-weak-off@example.com",
        household_name="Classification Weak OFF Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    product = create_product_record(
        db_session,
        household=household,
        actor=actor,
        name="Tomato soup",
        default_unit="can",
        aliases=[],
        barcodes=["1234567890999"],
    )
    enrichment = ProductEnrichment(
        household_id=household.id,
        product=product,
        source_name="open_food_facts",
        source_product_id="1234567890999",
        source_barcode="1234567890999",
        source_product_name="Tomato soup",
        ingredients_text="Tomatoes, water",
        ingredient_tags=[],
        allergen_tags=[],
        dietary_tags=[],
        categories=["Soups"],
        match_status="name_search",
        match_confidence=0.68,
    )
    db_session.add(enrichment)
    db_session.flush()

    payload = build_product_intelligence_source_payload(
        product,
        provider_type="ollama",
        model="llama3.2",
    )

    assert payload["classification_strategy"] == PRODUCT_INTELLIGENCE_EXECUTION_FULL_AI
    assert payload["enrichment"]["category_hint"] == "Soups"
    assert payload["enrichment"]["ingredients_text"] == "Tomatoes, water"


def test_product_intelligence_execution_plan_prefers_derived_only_for_packaged_staples(db_session):
    actor, household = create_household_with_role(
        db_session,
        email="classification-derived@example.com",
        household_name="Classification Derived Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    product = create_product_record(
        db_session,
        household=household,
        actor=actor,
        name="Chickpeas",
        default_unit="can",
        aliases=[],
        barcodes=["1234567890123"],
    )
    db_session.add(
        ProductEnrichment(
            household_id=household.id,
            product=product,
            source_name="open_food_facts",
            source_product_id="1234567890123",
            source_barcode="1234567890123",
            source_product_name="Chickpeas in water",
            ingredients_text="Chickpeas, water, salt",
            ingredient_tags=[],
            allergen_tags=[],
            dietary_tags=["vegan"],
            categories=["Legumes", "Chickpeas"],
            match_status="barcode_exact",
            match_confidence=1.0,
        )
    )
    db_session.flush()

    plan = build_product_intelligence_execution_plan(
        product,
        provider_type="ollama",
        model="llama3.2",
    )

    assert plan.path == PRODUCT_INTELLIGENCE_PATH_DERIVED_ONLY
    assert plan.ai_payload is None
    assert plan.approx_input_tokens == 0
    assert plan.derived_output is not None
    assert plan.derived_output.food_category == "Legumes"
    assert plan.derived_output.structured_metadata.storage_profile == "Shelf stable"


def test_product_intelligence_execution_plan_uses_smaller_ai_gap_fill_payload_for_enriched_products(db_session):
    actor, household = create_household_with_role(
        db_session,
        email="classification-gap-fill@example.com",
        household_name="Classification Gap Fill Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    product = create_product_record(
        db_session,
        household=household,
        actor=actor,
        name="Chopped tomatoes",
        default_unit="can",
        aliases=["Tinned tomatoes", "Italian plum tomatoes"],
        barcodes=["1234567890123"],
        notes="Useful for sauces, soups, and braises.",
    )
    db_session.add(
        ProductEnrichment(
            household_id=household.id,
            product=product,
            source_name="open_food_facts",
            source_product_id="1234567890123",
            source_barcode="1234567890123",
            source_product_name="Chopped tomatoes in tomato juice",
            ingredients_text="Tomatoes, tomato juice",
            ingredient_tags=["tomatoes"],
            allergen_tags=[],
            dietary_tags=["vegan"],
            categories=["Tomatoes", "Chopped tomatoes"],
            match_status="barcode_exact",
            match_confidence=1.0,
        )
    )
    db_session.flush()

    plan = build_product_intelligence_execution_plan(
        product,
        provider_type="ollama",
        model="llama3.2",
    )
    full_payload = build_product_intelligence_batch_source_payload(
        product,
        trim_level=get_product_intelligence_runtime_trim_level(
            product,
            provider_type="ollama",
            model="llama3.2",
        ),
    )

    assert plan.path == PRODUCT_INTELLIGENCE_PATH_AI_GAP_FILL
    assert plan.ai_payload is not None
    assert plan.derived_output is not None
    assert plan.derived_output.dietary_tags == ["Vegan"]
    assert plan.derived_output.structured_metadata.storage_profile == "Shelf stable"
    assert plan.approx_input_tokens < estimate_product_intelligence_tokens(full_payload)


def test_product_intelligence_execution_plan_keeps_manual_products_on_full_ai(db_session):
    actor, household = create_household_with_role(
        db_session,
        email="classification-full-ai@example.com",
        household_name="Classification Full AI Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    product = create_product_record(
        db_session,
        household=household,
        actor=actor,
        name="Bacon",
        default_unit="pack",
        aliases=["Smoked bacon"],
        barcodes=[],
        notes="Rashers for sandwiches and breakfasts.",
        manual_ingredient_tags=["Pork"],
    )

    plan = build_product_intelligence_execution_plan(
        product,
        provider_type="ollama",
        model="llama3.2",
    )

    assert plan.path == PRODUCT_INTELLIGENCE_PATH_FULL_AI
    assert plan.ai_payload is not None
    assert plan.approx_input_tokens > 0


def test_product_intelligence_staleness_uses_runtime_payload_fields_only(db_session):
    actor, household = create_household_with_role(
        db_session,
        email="classification-hash@example.com",
        household_name="Classification Hash Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    product = create_product_record(
        db_session,
        household=household,
        actor=actor,
        name="Brown sauce",
        default_unit="bottle",
        aliases=[],
        barcodes=["5000111046244"],
    )
    enrichment = ProductEnrichment(
        household_id=household.id,
        product=product,
        source_name="open_food_facts",
        source_product_id="5000111046244",
        source_barcode="5000111046244",
        source_product_name="HP Brown Sauce",
        ingredients_text="Tomatoes, vinegar, barley malt",
        ingredient_tags=["tomatoes", "vinegar", "barley-malt"],
        allergen_tags=["Gluten"],
        dietary_tags=["vegetarian"],
        categories=["Condiments", "Sauces", "Brown Sauces"],
        labels=["Vegetarian"],
        nutriments_payload={"energy-kcal_100g": 100},
        nutrition_summary=[{"label": "Energy", "value": 100, "unit": "kcal"}],
    )
    db_session.add(enrichment)
    db_session.flush()

    intelligence = ProductIntelligence(
        household_id=household.id,
        product_id=product.id,
        source_provider="ollama",
        source_model="llama3.2",
        classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
        classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
        schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
        source_data_hash=build_product_intelligence_source_data_hash(
            product,
            provider_type="ollama",
            model="llama3.2",
        ),
        classified_at=product.updated_at,
    )
    db_session.add(intelligence)
    db_session.flush()

    enrichment.labels = ["Organic"]
    enrichment.nutrition_summary = [
        {"label": "Energy", "value": 150, "unit": "kcal"},
        {"label": "Salt", "value": 2.1, "unit": "g"},
    ]
    enrichment.nutriments_payload = {"energy-kcal_100g": 150, "salt_100g": 2.1}
    assert get_product_intelligence_staleness(product, intelligence).is_stale is False

    enrichment.ingredient_tags = ["tomatoes", "molasses"]
    staleness = get_product_intelligence_staleness(product, intelligence)
    assert staleness.is_stale is True
    assert "source_product_data_changed" in staleness.reasons


def test_product_intelligence_worker_batches_requests_and_recovers_from_429s(client, db_session, monkeypatch):
    _, household = create_household_with_role(
        db_session,
        email="classification-batch@example.com",
        household_name="Classification Batch Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    stub_adapter = install_stub_product_intelligence_provider(
        db_session,
        monkeypatch,
        adapter=StubProductIntelligenceAdapter(fail_attempts=2),
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "app.services.product_intelligence_runs.time.sleep",
        lambda seconds: sleep_calls.append(round(float(seconds), 2)),
    )
    login(client, email="classification-batch@example.com")

    for index in range(7):
        create_product(
            client,
            household.external_id,
            name=f"Pasta {index}",
            default_unit="pack",
            aliases=[],
            barcodes=[],
            notes="Long pantry note " * 20,
        )

    queued = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "all"},
    )
    assert queued.status_code == 200

    assert process_next_product_intelligence_run() is True

    run_detail = client.get(
        f"/api/households/{household.external_id}/product-intelligence/runs/{queued.json()['external_id']}"
    )
    assert run_detail.status_code == 200
    payload = run_detail.json()
    assert payload["status"] == "completed"
    assert payload["classified_count"] == 7
    assert payload["failed_count"] == 0
    assert len(stub_adapter.batches) == 3
    assert all(len(batch) <= 3 for batch in stub_adapter.batches)
    assert any("Retrying batch" in event["message"] for event in payload["events"])
    assert payload["diagnostics"]["path_counts"]["full_ai"] == 7
    assert payload["diagnostics"]["retry_count"] >= 2
    assert payload["diagnostics"]["rate_limit_count"] >= 2
    assert len(sleep_calls) >= 2


def test_product_intelligence_run_reports_partial_success_when_batch_output_omits_a_product(
    client, db_session, monkeypatch
):
    _, household = create_household_with_role(
        db_session,
        email="classification-partial@example.com",
        household_name="Classification Partial Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="classification-partial@example.com")
    sauce = create_product(
        client,
        household.external_id,
        name="Brown sauce",
        default_unit="bottle",
        aliases=[],
        barcodes=["5000111046244"],
    )
    pasta = create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="pack",
        aliases=[],
        barcodes=[],
    )
    install_stub_product_intelligence_provider(
        db_session,
        monkeypatch,
        adapter=StubProductIntelligenceAdapter(omitted_product_external_ids={pasta["external_id"]}),
    )

    queued = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "all"},
    )
    assert queued.status_code == 200

    assert process_next_product_intelligence_run() is True

    run_detail = client.get(
        f"/api/households/{household.external_id}/product-intelligence/runs/{queued.json()['external_id']}"
    )
    assert run_detail.status_code == 200
    payload = run_detail.json()
    assert payload["status"] == "partially_completed"
    assert payload["classified_count"] == 1
    assert payload["failed_count"] == 1
    assert {item["status"] for item in payload["items"]} == {"classified", "failed"}
    assert sauce["external_id"] in {item["product_external_id"] for item in payload["items"]}


def test_product_intelligence_run_surfaces_friendly_openai_errors(client, db_session, monkeypatch):
    _, household = create_household_with_role(
        db_session,
        email="classification-openai-error@example.com",
        household_name="Classification OpenAI Error Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    platform_admin = create_platform_admin(
        db_session,
        email="classification-openai-admin@example.com",
        password=PASSWORD,
        display_name="OpenAI Classification Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=platform_admin,
        provider_type=AI_PROVIDER_OPENAI,
        base_url="https://api.openai.com/v1",
        default_model="gpt-5.4-mini",
        api_key="openai-secret",
        is_enabled=True,
    )
    monkeypatch.setattr(
        "app.services.product_intelligence_runs.refresh_provider_health",
        lambda db, config: AIProviderHealth(
            is_healthy=True,
            status="healthy",
            message=None,
            models=["gpt-5.4-mini"],
            capabilities={"supports_structured_output": True},
        ),
    )

    class FailingOpenAIClassificationAdapter(StubProductIntelligenceAdapter):
        def generate_structured_output(self, request) -> StructuredCompletionResult:
            request_obj = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            response = httpx.Response(
                400,
                request=request_obj,
                text='{"error":{"message":"Invalid schema for response_format json_schema"}}',
            )
            raise httpx.HTTPStatusError("400 Client Error", request=request_obj, response=response)

    monkeypatch.setattr(
        "app.services.product_intelligence_runs.build_ai_provider_adapter",
        lambda runtime: FailingOpenAIClassificationAdapter(),
    )

    login(client, email="classification-openai-error@example.com")
    create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="pack",
        aliases=[],
        barcodes=[],
    )

    queued = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "all"},
    )
    assert queued.status_code == 200

    assert process_next_product_intelligence_run() is True

    run_detail = client.get(
        f"/api/households/{household.external_id}/product-intelligence/runs/{queued.json()['external_id']}"
    )
    assert run_detail.status_code == 200
    payload = run_detail.json()
    assert payload["status"] == "failed"
    assert "gpt-5.4-mini" in payload["last_error"]
    assert "gpt-4.1-mini" in payload["last_error"]
    assert "gpt-5.4" in payload["last_error"]
    assert "400 Bad Request" not in payload["last_error"]
    assert "https://api.openai.com/v1/chat/completions" not in payload["last_error"]


@pytest.mark.parametrize("default_model", ["gpt-4.1-mini", "gpt-5.4-mini", "gpt-5.4"])
def test_product_intelligence_run_supports_recommended_openai_models(
    client,
    db_session,
    monkeypatch,
    default_model,
):
    model_slug = default_model.replace(".", "-")
    _, household = create_household_with_role(
        db_session,
        email=f"classification-openai-{model_slug}@example.com",
        household_name=f"Classification {default_model} Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    platform_admin = create_platform_admin(
        db_session,
        email=f"classification-openai-{model_slug}-admin@example.com",
        password=PASSWORD,
        display_name="OpenAI Classification Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=platform_admin,
        provider_type=AI_PROVIDER_OPENAI,
        base_url="https://api.openai.com/v1",
        default_model=default_model,
        api_key="openai-secret",
        is_enabled=True,
    )
    monkeypatch.setattr(
        "app.services.product_intelligence_runs.refresh_provider_health",
        lambda db, config: AIProviderHealth(
            is_healthy=True,
            status="healthy",
            message=None,
            models=["gpt-4.1-mini", "gpt-5.4-mini", "gpt-5.4"],
            capabilities={"supports_structured_output": True},
        ),
    )

    class SuccessfulOpenAIClassificationAdapter(StubProductIntelligenceAdapter):
        def generate_structured_output(self, request) -> StructuredCompletionResult:
            assert request.model == default_model
            return super().generate_structured_output(request)

    monkeypatch.setattr(
        "app.services.product_intelligence_runs.build_ai_provider_adapter",
        lambda runtime: SuccessfulOpenAIClassificationAdapter(),
    )

    login(client, email=f"classification-openai-{model_slug}@example.com")
    create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="pack",
        aliases=[],
        barcodes=[],
    )

    queued = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "all"},
    )
    assert queued.status_code == 200

    assert process_next_product_intelligence_run() is True

    run_detail = client.get(
        f"/api/households/{household.external_id}/product-intelligence/runs/{queued.json()['external_id']}"
    )
    assert run_detail.status_code == 200
    payload = run_detail.json()
    assert payload["status"] == "completed"
    assert payload["classified_count"] == 1
    assert payload["default_model"] == default_model


def test_product_intelligence_run_does_not_call_supported_openai_model_unsupported_for_token_param_errors(
    client, db_session, monkeypatch
):
    _, household = create_household_with_role(
        db_session,
        email="classification-openai-token-error@example.com",
        household_name="Classification OpenAI Token Error Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    platform_admin = create_platform_admin(
        db_session,
        email="classification-openai-token-admin@example.com",
        password=PASSWORD,
        display_name="OpenAI Token Error Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=platform_admin,
        provider_type=AI_PROVIDER_OPENAI,
        base_url="https://api.openai.com/v1",
        default_model="gpt-5.4-mini",
        api_key="openai-secret",
        is_enabled=True,
    )
    monkeypatch.setattr(
        "app.services.product_intelligence_runs.refresh_provider_health",
        lambda db, config: AIProviderHealth(
            is_healthy=True,
            status="healthy",
            message=None,
            models=["gpt-4.1-mini", "gpt-5.4-mini", "gpt-5.4"],
            capabilities={"supports_structured_output": True},
        ),
    )

    class FailingOpenAITokenAdapter(StubProductIntelligenceAdapter):
        def generate_structured_output(self, request) -> StructuredCompletionResult:
            request_obj = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            response = httpx.Response(
                400,
                request=request_obj,
                text=(
                    '{"error":{"message":"Unsupported parameter: \\"max_tokens\\" is not supported with this model. '
                    'Use \\"max_completion_tokens\\" instead."}}'
                ),
            )
            raise httpx.HTTPStatusError("400 Client Error", request=request_obj, response=response)

    monkeypatch.setattr(
        "app.services.product_intelligence_runs.build_ai_provider_adapter",
        lambda runtime: FailingOpenAITokenAdapter(),
    )

    login(client, email="classification-openai-token-error@example.com")
    create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="pack",
        aliases=[],
        barcodes=[],
    )

    queued = client.post(
        f"/api/households/{household.external_id}/product-intelligence/classify",
        json={"mode": "all"},
    )
    assert queued.status_code == 200

    assert process_next_product_intelligence_run() is True

    run_detail = client.get(
        f"/api/households/{household.external_id}/product-intelligence/runs/{queued.json()['external_id']}"
    )
    assert run_detail.status_code == 200
    payload = run_detail.json()
    assert payload["status"] == "failed"
    assert "structured request parameters" in payload["last_error"]
    assert "gpt-5.4-mini' is not a good fit" not in payload["last_error"]
    assert "Use one of Pantry's supported OpenAI models" not in payload["last_error"]
    assert "400 Bad Request" not in payload["last_error"]


def test_product_classification_batch_output_coerces_nullable_openai_fields():
    parsed = ProductClassificationBatchOutput.model_validate(
        {
            "items": [
                {
                    "product_external_id": "prd_test",
                    "confidence": 0.91,
                    "rationale_short": "Short rationale",
                    "primary_ingredient_type": "pork",
                    "ingredient_families": ["meat"],
                    "food_category": "cured meat",
                    "dietary_tags": None,
                    "allergen_tags": None,
                    "recipe_role_tags": ["protein"],
                    "substitution_groups": ["cured pork"],
                    "pantry_use_tags": ["breakfast"],
                    "structured_metadata": {
                        "product_format": "sliced meat",
                        "storage_profile": "refrigerated",
                        "cuisine_tags": None,
                        "flavour_tags": ["smoky"],
                        "preparation_tags": None,
                    },
                }
            ]
        }
    )

    item = parsed.items[0]
    assert item.dietary_tags == []
    assert item.allergen_tags == []
    assert item.structured_metadata.cuisine_tags == []
    assert item.structured_metadata.preparation_tags == []


def test_product_intelligence_profiles_choose_gemini_default_and_token_aware_batches(db_session):
    actor, household = create_household_with_role(
        db_session,
        email="classification-profiles@example.com",
        household_name="Classification Profiles Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    large_product = create_product_record(
        db_session,
        household=household,
        actor=actor,
        name="Large pantry product",
        default_unit="pack",
        aliases=[],
        barcodes=[],
    )

    profile = resolve_product_intelligence_profile("gemini", "gemini-2.5-flash")
    assert profile.profile_label == "gemini_2_5_flash"
    assert get_default_supported_model("gemini") == "gemini-2.5-flash"

    large_candidate = PreparedClassificationCandidate(
        product=large_product,
        path=PRODUCT_INTELLIGENCE_PATH_FULL_AI,
        trim_level=0,
        payload={"product_external_id": large_product.external_id},
        approx_input_tokens=4_000,
        approx_output_tokens=profile.per_product_output_tokens,
        staleness=ProductIntelligenceStaleness(is_stale=False, reasons=[]),
        existing_intelligence=None,
        derived_output=None,
    )
    second_candidate = PreparedClassificationCandidate(
        product=large_product,
        path=PRODUCT_INTELLIGENCE_PATH_FULL_AI,
        trim_level=0,
        payload={"product_external_id": "second"},
        approx_input_tokens=2_800,
        approx_output_tokens=profile.per_product_output_tokens,
        staleness=ProductIntelligenceStaleness(is_stale=False, reasons=[]),
        existing_intelligence=None,
        derived_output=None,
    )
    third_candidate = PreparedClassificationCandidate(
        product=large_product,
        path=PRODUCT_INTELLIGENCE_PATH_FULL_AI,
        trim_level=0,
        payload={"product_external_id": "third"},
        approx_input_tokens=1_000,
        approx_output_tokens=profile.per_product_output_tokens,
        staleness=ProductIntelligenceStaleness(is_stale=False, reasons=[]),
        existing_intelligence=None,
        derived_output=None,
    )

    batches = _build_batches([large_candidate, second_candidate, third_candidate], profile=profile)
    assert len(batches) == 2
    assert [candidate.approx_input_tokens for candidate in batches[0]] == [4_000]
    assert [candidate.approx_input_tokens for candidate in batches[1]] == [2_800, 1_000]


def test_pantry_overview_supports_product_pagination_metadata(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="pagination@example.com",
        household_name="Pagination Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="pagination@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    for index in range(12):
        product = create_product(
            client,
            household.external_id,
            name=f"Product {index:02d}",
            default_unit="count",
            aliases=[],
            barcodes=[],
        )
        add_stock_lot(
            client,
            household.external_id,
            product_external_id=product["external_id"],
            location_external_id=shelf["external_id"],
            quantity="1.000",
        )

    response = client.get(
        f"/api/households/{household.external_id}/pantry/overview",
        params={"page": 2, "page_size": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 10
    assert payload["page_count"] == 2
    assert payload["matched_product_count"] == 12
    assert len(payload["products"]) == 2


def test_product_creation_rejects_alias_name_collision(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="collision@example.com",
        household_name="Collision Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="collision@example.com")

    first = client.post(
        f"/api/households/{household.external_id}/products",
        json={
            "name": "Rice",
            "default_unit": "bag",
            "aliases": ["Long Grain"],
            "barcodes": ["12345"],
        },
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/households/{household.external_id}/products",
        json={
            "name": " long   grain ",
            "default_unit": "bag",
            "aliases": [],
            "barcodes": [],
        },
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "Rice already uses that name or alias."


def test_pantry_entry_creates_product_and_first_stock_lot_in_one_flow(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="entry-create@example.com",
        household_name="Entry Create Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="entry-create@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")

    payload = create_pantry_entry(
        client,
        household.external_id,
        name="Beef mince",
        quantity="1.500",
        unit="kg",
        location_external_id=shelf["external_id"],
        aliases=["Ground beef", "Minced beef"],
        product_notes="Freeze in flat packs for faster defrosting.",
        purchased_on="2026-04-01",
        expires_on="2026-04-03",
        note="Family pack",
    )

    assert payload["status"] == "created"
    assert payload["product"]["name"] == "Beef mince"
    assert payload["product"]["default_unit"] == "kg"
    assert payload["product"]["notes"] == "Freeze in flat packs for faster defrosting."
    assert payload["lot"]["product_name"] == "Beef mince"
    assert payload["lot"]["location_name"] == "Shelf"
    assert payload["lot"]["note"] == "Family pack"


def test_product_update_replaces_product_metadata_and_notes(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="product-update@example.com",
        household_name="Product Update Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="product-update@example.com")

    product = create_product(
        client,
        household.external_id,
        name="Soup base",
        default_unit="jar",
        aliases=["Base stock"],
        barcodes=["10001"],
        notes="Original notes",
        manual_ingredient_tags=["Onion"],
    )

    updated = update_product(
        client,
        household.external_id,
        product["external_id"],
        name="Rich soup base",
        default_unit="pack",
        aliases=["Broth base", "Stock concentrate"],
        barcodes=["20002"],
        notes="Use half a pack for weeknight soups.",
        manual_ingredient_tags=["Onion", "Celery"],
    )

    assert updated["name"] == "Rich soup base"
    assert updated["default_unit"] == "pack"
    assert updated["aliases"] == ["Broth base", "Stock concentrate"]
    assert updated["barcodes"] == ["20002"]
    assert updated["notes"] == "Use half a pack for weeknight soups."
    assert updated["manual_ingredient_tags"] == ["Onion", "Celery"]

    overview = client.get(
        f"/api/households/{household.external_id}/pantry/overview",
        params={"q": "broth base"},
    )
    assert overview.status_code == 200
    assert overview.json()["catalog_products"][0]["notes"] == "Use half a pack for weeknight soups."

    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.action == "product.updated")
    ).all()
    assert len(events) == 1


def test_pantry_entry_detects_existing_product_then_adds_new_stock_lot(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="entry-existing@example.com",
        household_name="Entry Existing Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="entry-existing@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    freezer = create_location(client, household.external_id, room["external_id"], "Freezer")

    first_entry = create_pantry_entry(
        client,
        household.external_id,
        name="Beef mince",
        quantity="1.000",
        unit="kg",
        location_external_id=shelf["external_id"],
        aliases=["Ground beef"],
        note="First pack",
    )
    assert first_entry["status"] == "created"

    duplicate_attempt = create_pantry_entry(
        client,
        household.external_id,
        name="Beef mince",
        quantity="0.750",
        unit="kg",
        location_external_id=freezer["external_id"],
        aliases=[],
        note="Second pack",
    )
    assert duplicate_attempt["status"] == "existing_product"
    assert duplicate_attempt["matched_product"]["name"] == "Beef mince"

    confirmed_duplicate = create_pantry_entry(
        client,
        household.external_id,
        name="Beef mince",
        quantity="0.750",
        unit="kg",
        location_external_id=freezer["external_id"],
        aliases=[],
        note="Second pack",
        existing_product_external_id=duplicate_attempt["matched_product"]["external_id"],
    )
    assert confirmed_duplicate["status"] == "added_to_existing"
    assert confirmed_duplicate["lot"]["location_name"] == "Freezer"

    overview = client.get(
        f"/api/households/{household.external_id}/pantry/overview",
        params={"q": "ground beef"},
    )
    assert overview.status_code == 200
    product_payload = overview.json()["products"][0]
    assert product_payload["product_name"] == "Beef mince"
    assert len(product_payload["stock_lots"]) == 2
    assert {lot["location_name"] for lot in product_payload["stock_lots"]} == {"Shelf", "Freezer"}


def test_pantry_entry_persists_manual_ingredient_tags_and_matches_existing_barcode(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="entry-barcode@example.com",
        household_name="Entry Barcode Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="entry-barcode@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    fridge = create_location(client, household.external_id, room["external_id"], "Fridge")

    first_entry = create_pantry_entry(
        client,
        household.external_id,
        name="Brown sauce",
        quantity="1.000",
        unit="bottle",
        location_external_id=shelf["external_id"],
        barcode="5000111046244",
        aliases=["HP sauce"],
        manual_ingredient_tags=["Tomatoes", "Vinegar"],
    )
    assert first_entry["status"] == "created"
    assert first_entry["product"]["manual_ingredient_tags"] == ["Tomatoes", "Vinegar"]

    duplicate_attempt = create_pantry_entry(
        client,
        household.external_id,
        name="HP brown sauce",
        quantity="1.000",
        unit="bottle",
        location_external_id=fridge["external_id"],
        barcode="5000111046244",
        aliases=["Breakfast sauce"],
        manual_ingredient_tags=["Barley malt"],
    )
    assert duplicate_attempt["status"] == "existing_product"
    assert duplicate_attempt["matched_product"]["name"] == "Brown sauce"

    confirmed_duplicate = create_pantry_entry(
        client,
        household.external_id,
        name="HP brown sauce",
        quantity="1.000",
        unit="bottle",
        location_external_id=fridge["external_id"],
        barcode="5000111046244",
        aliases=["Breakfast sauce"],
        manual_ingredient_tags=["Barley malt"],
        existing_product_external_id=duplicate_attempt["matched_product"]["external_id"],
    )
    assert confirmed_duplicate["status"] == "added_to_existing"
    assert "saved aliases: Breakfast sauce" in confirmed_duplicate["message"]
    assert "saved manual ingredients" in confirmed_duplicate["message"]

    overview = client.get(
        f"/api/households/{household.external_id}/pantry/overview",
        params={"q": "5000111046244"},
    )
    assert overview.status_code == 200
    product_payload = overview.json()["products"][0]
    assert product_payload["product_name"] == "Brown sauce"
    assert sorted(product_payload["manual_ingredient_tags"]) == [
        "Barley malt",
        "Tomatoes",
        "Vinegar",
    ]
    assert "Breakfast sauce" in product_payload["aliases"]
    assert product_payload["barcodes"] == ["5000111046244"]
    assert len(product_payload["stock_lots"]) == 2


def test_pantry_entry_reports_alias_conflicts(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="entry-alias@example.com",
        household_name="Entry Alias Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="entry-alias@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")

    first_entry = create_pantry_entry(
        client,
        household.external_id,
        name="Pasta",
        quantity="2.000",
        unit="count",
        location_external_id=shelf["external_id"],
        aliases=["Dry pasta"],
    )
    assert first_entry["status"] == "created"

    conflict = create_pantry_entry(
        client,
        household.external_id,
        name="Beef mince",
        quantity="1.000",
        unit="kg",
        location_external_id=shelf["external_id"],
        aliases=["Dry pasta"],
    )
    assert conflict["status"] == "alias_conflict"
    assert conflict["alias_conflicts"] == [
        {
            "alias": "Dry pasta",
            "product_external_id": first_entry["product"]["external_id"],
            "product_name": "Pasta",
        }
    ]


def test_product_enrichment_preview_and_confirmed_persistence(client, db_session, monkeypatch):
    _, household = create_household_with_role(
        db_session,
        email="enrich@example.com",
        household_name="Enrichment Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="enrich@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")

    barcode_candidate = build_enrichment_candidate(
        source_product_id="5000111046244",
        source_product_name="HP Brown Sauce",
        match_status="barcode_exact",
        match_confidence=1.0,
    )
    name_candidates = [
        build_enrichment_candidate(
            source_product_id="5000111046244",
            source_product_name="HP Brown Sauce",
            match_status="name_search_candidate",
            match_confidence=0.93,
        ),
        build_enrichment_candidate(
            source_product_id="5000111046245",
            source_product_name="HP Fruity Brown Sauce",
            match_status="name_search_candidate",
            match_confidence=0.78,
        ),
    ]

    class StubOpenFoodFactsClient:
        def lookup_by_barcode(self, barcode: str):
            return barcode_candidate if barcode == "5000111046244" else None

        def search_by_name(self, product_name: str, *, limit: int = 5):
            return name_candidates if "hp" in product_name.lower() else []

        def fetch_product_by_id(self, source_product_id: str):
            for candidate in [barcode_candidate, *name_candidates]:
                if candidate.source_product_id == source_product_id:
                    return candidate
            return None

    monkeypatch.setattr(
        "app.services.product_enrichment.get_default_open_food_facts_client",
        lambda: StubOpenFoodFactsClient(),
    )

    preview = client.post(
        f"/api/households/{household.external_id}/pantry/enrichment/preview",
        json={"product_name": "HP brown sauce", "barcode": "5000111046244"},
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["status"] == "matched"
    assert preview_payload["candidates"][0]["source_product_name"] == "HP Brown Sauce"

    preview_fallback = client.post(
        f"/api/households/{household.external_id}/pantry/enrichment/preview",
        json={"product_name": "HP brown sauce", "barcode": None},
    )
    assert preview_fallback.status_code == 200
    assert preview_fallback.json()["status"] == "multiple_matches"
    assert len(preview_fallback.json()["candidates"]) == 2

    payload = create_pantry_entry(
        client,
        household.external_id,
        name="Brown sauce",
        quantity="1.000",
        unit="bottle",
        location_external_id=shelf["external_id"],
        barcode="5000111046244",
        aliases=["HP sauce"],
        confirmed_enrichment={
            "source_name": "open_food_facts",
            "source_product_id": "5000111046244",
            "match_status": "barcode_exact",
        },
    )

    assert payload["status"] == "created"
    assert payload["product"]["enrichment"]["source_name"] == "open_food_facts"
    assert payload["product"]["enrichment"]["source_product_name"] == "HP Brown Sauce"
    assert "Open Food Facts details linked." in payload["message"]

    stored_enrichment = db_session.scalar(select(ProductEnrichment))
    assert stored_enrichment is not None
    assert stored_enrichment.source_product_id == "5000111046244"
    assert stored_enrichment.enrichment_status == "linked"
    assert stored_enrichment.ingredients_text == "Tomatoes, vinegar, barley malt"
    assert stored_enrichment.ingredient_tags == ["tomatoes", "vinegar", "barley-malt"]
    assert stored_enrichment.ingredient_tokens == ["tomatoes", "vinegar", "barley", "malt"]
    assert stored_enrichment.dietary_tags == ["vegetarian"]
    assert stored_enrichment.nutriments_payload["salt_100g"] == 1.2
    assert stored_enrichment.nutrition_summary_text == "Energy 100 kcal per 100 g · Salt 1.2 g per 100 g"

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert overview.status_code == 200
    overview_payload = overview.json()
    assert overview_payload["products"][0]["enrichment"]["labels"] == ["Vegetarian"]
    assert overview_payload["products"][0]["enrichment"]["ingredient_tags"] == [
        "tomatoes",
        "vinegar",
        "barley-malt",
    ]
    assert overview_payload["products"][0]["enrichment"]["nutrition_summary_text"] == (
        "Energy 100 kcal per 100 g · Salt 1.2 g per 100 g"
    )


def test_existing_product_can_link_open_food_facts_enrichment_after_creation(client, db_session, monkeypatch):
    _, household = create_household_with_role(
        db_session,
        email="product-lookup@example.com",
        household_name="Product Lookup Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="product-lookup@example.com")

    product = create_product(
        client,
        household.external_id,
        name="HP brown sauce",
        default_unit="bottle",
        aliases=[],
        barcodes=["5000111046244"],
    )

    candidate = build_enrichment_candidate(
        source_product_id="5000111046244",
        source_product_name="HP Brown Sauce",
        match_status="barcode_exact",
        match_confidence=1.0,
    )

    class StubOpenFoodFactsClient:
        def fetch_product_by_id(self, source_product_id: str):
            return candidate if source_product_id == "5000111046244" else None

    monkeypatch.setattr(
        "app.services.product_enrichment.get_default_open_food_facts_client",
        lambda: StubOpenFoodFactsClient(),
    )

    response = client.post(
        f"/api/households/{household.external_id}/products/{product['external_id']}/enrichment",
        json={
            "source_name": "open_food_facts",
            "source_product_id": "5000111046244",
            "match_status": "barcode_exact",
        },
    )
    assert response.status_code == 200
    assert response.json()["enrichment"]["source_product_name"] == "HP Brown Sauce"

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert overview.status_code == 200
    assert overview.json()["products"][0]["enrichment"]["source_product_name"] == "HP Brown Sauce"


def test_shopping_item_product_creation_persists_confirmed_enrichment(client, db_session, monkeypatch):
    _, household = create_household_with_role(
        db_session,
        email="shopping-enrichment@example.com",
        household_name="Shopping Enrichment Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-enrichment@example.com")

    candidate = build_enrichment_candidate(
        source_product_id="5000111046244",
        source_product_name="Tomato Soup Deluxe",
        match_status="barcode_exact",
        match_confidence=1.0,
    )

    class StubOpenFoodFactsClient:
        def fetch_product_by_id(self, source_product_id: str):
            return candidate if source_product_id == candidate.source_product_id else None

    monkeypatch.setattr(
        "app.services.product_enrichment.get_default_open_food_facts_client",
        lambda: StubOpenFoodFactsClient(),
    )

    added = client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={"label": "Tomato soup", "quantity": "2.000", "unit": "can", "source_type": "manual"},
    )
    assert added.status_code == 201
    export_response = client.post(f"/api/households/{household.external_id}/shopping-list/export")
    assert export_response.status_code == 200
    pending_item = client.get(f"/api/households/{household.external_id}/shopping-list").json()["pending_lists"][0]["items"][0]

    product_response = client.post(
        f"/api/households/{household.external_id}/products",
        json={
            "name": "Tomato soup",
            "default_unit": "can",
            "aliases": [],
            "barcodes": ["5000111046244"],
            "notes": "Created from shopping reconciliation",
            "manual_ingredient_tags": [],
            "confirmed_enrichment": {
                "source_name": "open_food_facts",
                "source_product_id": "5000111046244",
                "match_status": "barcode_exact",
            },
        },
    )
    assert product_response.status_code == 201
    assert product_response.json()["enrichment"]["source_product_name"] == "Tomato Soup Deluxe"

    attached = client.post(
        f"/api/households/{household.external_id}/shopping-list/items/{pending_item['external_id']}/attach-product",
        json={"product_external_id": product_response.json()["external_id"]},
    )
    assert attached.status_code == 200
    attached_item = attached.json()["pending_lists"][0]["items"][0]
    assert attached_item["product_name"] == "Tomato soup"
    assert attached_item["product_external_id"] == product_response.json()["external_id"]

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert overview.status_code == 200
    assert overview.json()["products"][0]["enrichment"]["source_product_name"] == "Tomato Soup Deluxe"


def test_move_stock_preserves_identity_on_full_move_and_splits_on_partial_move(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="move@example.com",
        household_name="Move Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="move@example.com")

    pantry_group = create_location_group(client, household.external_id, "Pantry")
    shelf = create_location(client, household.external_id, pantry_group["external_id"], "Shelf")
    drawer = create_location(client, household.external_id, pantry_group["external_id"], "Drawer")
    product = create_product(
        client,
        household.external_id,
        name="Olive Oil",
        default_unit="bottle",
        aliases=[],
        barcodes=[],
    )
    lot = add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="5.000",
    )["lot"]

    full_move = client.post(
        f"/api/households/{household.external_id}/stock-lots/{lot['external_id']}/move",
        json={"quantity": "5.000", "destination_location_external_id": drawer["external_id"]},
    )
    assert full_move.status_code == 200
    full_payload = full_move.json()
    assert full_payload["lot"]["external_id"] == lot["external_id"]
    assert full_payload["lot"]["location_name"] == "Drawer"
    assert full_payload["created_lot"] is None

    partial_move = client.post(
        f"/api/households/{household.external_id}/stock-lots/{lot['external_id']}/move",
        json={"quantity": "2.000", "destination_location_external_id": shelf["external_id"]},
    )
    assert partial_move.status_code == 200
    partial_payload = partial_move.json()
    assert partial_payload["lot"]["external_id"] == lot["external_id"]
    assert Decimal(partial_payload["lot"]["quantity"]) == Decimal("3.000")
    assert partial_payload["lot"]["location_name"] == "Drawer"
    assert partial_payload["created_lot"] is not None
    assert partial_payload["created_lot"]["location_name"] == "Shelf"
    assert Decimal(partial_payload["created_lot"]["quantity"]) == Decimal("2.000")

    events = db_session.scalars(select(AuditEvent).where(AuditEvent.action == "stock.moved")).all()
    assert len(events) == 2
    preserved_flags = sorted(event.event_metadata["preserved_lot_identity"] for event in events)
    assert preserved_flags == [False, True]


def test_remove_stock_depletes_lot_and_excludes_it_from_active_views(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="remove@example.com",
        household_name="Remove Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="remove@example.com")

    group = create_location_group(client, household.external_id, "Pantry")
    location = create_location(client, household.external_id, group["external_id"], "Shelf")
    product = create_product(
        client,
        household.external_id,
        name="Tomatoes",
        default_unit="can",
        aliases=[],
        barcodes=[],
    )
    lot = add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=location["external_id"],
        quantity="2.000",
    )["lot"]

    removed = client.post(
        f"/api/households/{household.external_id}/stock-lots/{lot['external_id']}/remove",
        json={"quantity": "2.000"},
    )
    assert removed.status_code == 200
    assert Decimal(removed.json()["lot"]["quantity"]) == Decimal("0.000")

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert overview.status_code == 200
    assert overview.json()["counts"]["active_lot_count"] == 0
    assert overview.json()["stock_lots"] == []
    assert overview.json()["counts"]["out_of_stock_product_count"] == 1
    assert overview.json()["products"][0]["stock_status"] == "out_of_stock"
    assert overview.json()["products"][0]["stock_lots"] == []

    stored_lot = db_session.scalar(select(StockLot).where(StockLot.external_id == lot["external_id"]))
    assert stored_lot is not None
    assert stored_lot.depleted_at is not None


def test_household_shopping_list_accepts_product_entries_and_status_changes(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping@example.com",
        household_name="Shopping Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    product = create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="count",
        aliases=[],
        barcodes=[],
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="2.000",
    )

    added = client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={
            "product_external_id": product["external_id"],
            "source_type": "pantry_product",
        },
    )
    assert added.status_code == 201
    added_payload = added.json()
    assert added_payload["active_list"]["unresolved_item_count"] == 1
    assert added_payload["active_list"]["items"][0]["product_name"] == "Pasta"
    assert added_payload["active_list"]["items"][0]["status"] == "open"

    export_response = client.post(f"/api/households/{household.external_id}/shopping-list/export")
    assert export_response.status_code == 200
    assert "[ ] Pasta" in export_response.text

    pending_snapshot = client.get(f"/api/households/{household.external_id}/shopping-list")
    assert pending_snapshot.status_code == 200
    pending_payload = pending_snapshot.json()
    assert pending_payload["active_list"]["unresolved_item_count"] == 0
    assert len(pending_payload["pending_lists"]) == 1
    item_external_id = pending_payload["pending_lists"][0]["items"][0]["external_id"]

    reconciled = client.put(
        f"/api/households/{household.external_id}/shopping-list/items/{item_external_id}",
        json={"status": "purchased"},
    )
    assert reconciled.status_code == 200
    reconciled_payload = reconciled.json()
    assert reconciled_payload["pending_lists"] == []
    assert reconciled_payload["history_lists"][0]["purchased_item_count"] == 1
    assert reconciled_payload["history_lists"][0]["items"][0]["status"] == "purchased"


def test_pantry_duplicate_check_matches_similarity_and_allows_separate_product(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="duplicate-check@example.com",
        household_name="Duplicate Check Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="duplicate-check@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")

    first_entry = create_pantry_entry(
        client,
        household.external_id,
        name="Beef mince",
        quantity="1.000",
        unit="kg",
        location_external_id=shelf["external_id"],
    )
    assert first_entry["status"] == "created"

    duplicate_check = client.post(
        f"/api/households/{household.external_id}/pantry/entries/duplicate-check",
        json={"name": "Mince beef"},
    )
    assert duplicate_check.status_code == 200
    duplicate_payload = duplicate_check.json()
    assert duplicate_payload["status"] == "matched"
    assert duplicate_payload["duplicate_match_reason"] == "name_similarity"
    assert duplicate_payload["can_keep_separate_product"] is True
    assert duplicate_payload["matched_product"]["name"] == "Beef mince"

    separate_product = create_pantry_entry(
        client,
        household.external_id,
        name="Mince beef",
        quantity="0.500",
        unit="kg",
        location_external_id=shelf["external_id"],
        allow_separate_product=True,
    )
    assert separate_product["status"] == "created"
    assert separate_product["product"]["name"] == "Mince beef"

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert overview.status_code == 200
    assert len(overview.json()["products"]) == 2


def test_stock_lot_update_and_buy_more_adds_shopping_item(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="lot-actions@example.com",
        household_name="Lot Actions Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="lot-actions@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    freezer = create_location(client, household.external_id, room["external_id"], "Freezer")
    product = create_product(
        client,
        household.external_id,
        name="Peas",
        default_unit="bag",
        aliases=[],
        barcodes=[],
    )
    lot = add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="2.000",
    )["lot"]

    updated = client.put(
        f"/api/households/{household.external_id}/stock-lots/{lot['external_id']}",
        json={
            "location_external_id": freezer["external_id"],
            "quantity": "3.000",
            "note": "Frozen backup",
            "purchased_on": "2026-04-01",
            "expires_on": "2026-10-01",
        },
    )
    assert updated.status_code == 200
    updated_payload = updated.json()["lot"]
    assert updated_payload["location_name"] == "Freezer"
    assert updated_payload["quantity"] == "3.000"
    assert updated_payload["note"] == "Frozen backup"

    buy_more = client.post(
        f"/api/households/{household.external_id}/stock-lots/{lot['external_id']}/buy-more"
    )
    assert buy_more.status_code == 200
    assert buy_more.json()["lot"]["is_depleted"] is True

    shopping_snapshot = client.get(f"/api/households/{household.external_id}/shopping-list")
    assert shopping_snapshot.status_code == 200
    shopping_payload = shopping_snapshot.json()
    assert shopping_payload["active_list"]["items"][0]["product_name"] == "Peas"
    assert shopping_payload["active_list"]["items"][0]["quantity"] == "3.000"


def test_stock_lots_merge_only_when_location_unit_and_expiry_match(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="merge@example.com",
        household_name="Merge Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="merge@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    fridge = create_location(client, household.external_id, room["external_id"], "Fridge")
    product = create_product(
        client,
        household.external_id,
        name="Milk",
        default_unit="bottle",
        aliases=[],
        barcodes=[],
    )

    first = add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
        expires_on="2026-05-01",
    )
    merged_same_expiry = add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="2.000",
        expires_on="2026-05-01",
    )
    merged_without_expiry = add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=fridge["external_id"],
        quantity="1.000",
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=fridge["external_id"],
        quantity="3.000",
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
        expires_on="2026-05-10",
    )

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert overview.status_code == 200
    product_payload = overview.json()["products"][0]
    assert product_payload["lot_count"] == 3
    assert {lot["expires_on"] for lot in product_payload["stock_lots"] if lot["location_name"] == "Shelf"} == {
        "2026-05-01",
        "2026-05-10",
    }
    same_expiry_lot = next(
        lot
        for lot in product_payload["stock_lots"]
        if lot["location_name"] == "Shelf" and lot["expires_on"] == "2026-05-01"
    )
    no_expiry_lot = next(
        lot for lot in product_payload["stock_lots"] if lot["location_name"] == "Fridge"
    )
    assert same_expiry_lot["quantity"] == "3.000"
    assert no_expiry_lot["quantity"] == "4.000"


def test_shopping_list_pending_merge_return_and_finalize_lifecycle(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-lifecycle@example.com",
        household_name="Shopping Lifecycle Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-lifecycle@example.com")

    first_item = client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={"label": "Milk", "quantity": "1.000", "unit": "bottle", "source_type": "manual"},
    )
    assert first_item.status_code == 201
    first_export = client.post(f"/api/households/{household.external_id}/shopping-list/export")
    assert first_export.status_code == 200
    assert "[ ] Milk (1 bottle)" in first_export.text

    second_item = client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={"label": "Bread", "quantity": "1.000", "unit": "loaf", "source_type": "manual"},
    )
    assert second_item.status_code == 201
    second_export = client.post(f"/api/households/{household.external_id}/shopping-list/export")
    assert second_export.status_code == 200

    before_merge = client.get(f"/api/households/{household.external_id}/shopping-list")
    assert before_merge.status_code == 200
    before_merge_payload = before_merge.json()
    assert len(before_merge_payload["pending_lists"]) == 2

    merged = client.post(f"/api/households/{household.external_id}/shopping-list/pending/merge", json={})
    assert merged.status_code == 200
    merged_payload = merged.json()
    assert len(merged_payload["pending_lists"]) == 1
    pending_list = merged_payload["pending_lists"][0]
    assert {item["label"] for item in pending_list["items"]} == {"Milk", "Bread"}

    returned = client.post(
        f"/api/households/{household.external_id}/shopping-list/pending/{pending_list['external_id']}/return-to-active",
        json={},
    )
    assert returned.status_code == 200
    returned_payload = returned.json()
    assert returned_payload["active_list"]["unresolved_item_count"] == 2
    assert len(returned_payload["pending_lists"]) == 0

    third_export = client.post(f"/api/households/{household.external_id}/shopping-list/export")
    assert third_export.status_code == 200
    pending_snapshot = client.get(f"/api/households/{household.external_id}/shopping-list")
    assert pending_snapshot.status_code == 200
    pending_payload = pending_snapshot.json()
    pending_list = pending_payload["pending_lists"][0]

    milk_item = next(item for item in pending_list["items"] if item["label"] == "Milk")
    bread_item = next(item for item in pending_list["items"] if item["label"] == "Bread")
    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    milk_product = create_product(
        client,
        household.external_id,
        name="Milk",
        default_unit="bottle",
        aliases=[],
        barcodes=[],
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=milk_product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
    )
    attached_milk = client.post(
        f"/api/households/{household.external_id}/shopping-list/items/{milk_item['external_id']}/attach-product",
        json={"product_external_id": milk_product["external_id"]},
    )
    assert attached_milk.status_code == 200
    pending_list = attached_milk.json()["pending_lists"][0]
    milk_item = next(item for item in pending_list["items"] if item["label"] == "Milk")
    bread_item = next(item for item in pending_list["items"] if item["label"] == "Bread")

    mark_purchased = client.put(
        f"/api/households/{household.external_id}/shopping-list/items/{milk_item['external_id']}",
        json={"status": "purchased", "quantity": "2.000", "unit": "bottle"},
    )
    assert mark_purchased.status_code == 200
    mark_not_purchased = client.put(
        f"/api/households/{household.external_id}/shopping-list/items/{bread_item['external_id']}",
        json={"status": "not_purchased"},
    )
    assert mark_not_purchased.status_code == 200

    assert mark_not_purchased.status_code == 200
    finalized_payload = mark_not_purchased.json()
    assert len(finalized_payload["pending_lists"]) == 0
    assert finalized_payload["active_list"]["items"][0]["label"] == "Bread"
    assert finalized_payload["history_lists"][0]["lifecycle_state"] == "reconciled"


def test_active_shopping_list_item_can_be_removed(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-remove@example.com",
        household_name="Shopping Remove Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-remove@example.com")

    added = client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={"label": "Milk", "quantity": "1.000", "unit": "bottle", "source_type": "manual"},
    )
    assert added.status_code == 201
    item_external_id = added.json()["active_list"]["items"][0]["external_id"]

    removed = client.delete(
        f"/api/households/{household.external_id}/shopping-list/items/{item_external_id}"
    )
    assert removed.status_code == 200
    assert removed.json()["active_list"]["items"] == []


def test_reconciliation_writes_purchased_stock_back_into_pantry_and_reuses_location(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-writeback@example.com",
        household_name="Shopping Writeback Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-writeback@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    product = create_product(
        client,
        household.external_id,
        name="Juice",
        default_unit="bottle",
        aliases=[],
        barcodes=[],
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
    )

    added = client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={
            "product_external_id": product["external_id"],
            "quantity": "5.000",
            "unit": "bottle",
            "source_type": "pantry_product",
        },
    )
    assert added.status_code == 201
    export_response = client.post(f"/api/households/{household.external_id}/shopping-list/export")
    assert export_response.status_code == 200
    pending_item = client.get(f"/api/households/{household.external_id}/shopping-list").json()["pending_lists"][0]["items"][0]

    saved = client.put(
        f"/api/households/{household.external_id}/shopping-list/items/{pending_item['external_id']}",
        json={"status": "purchased", "quantity": "5.000", "unit": "bottle"},
    )
    assert saved.status_code == 200

    assert saved.status_code == 200
    assert len(saved.json()["pending_lists"]) == 0
    assert saved.json()["history_lists"][0]["lifecycle_state"] == "reconciled"

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    product_payload = overview.json()["products"][0]
    assert product_payload["stock_status"] == "in_stock"
    assert product_payload["total_quantity"] == "6.000"
    assert product_payload["stock_lots"][0]["location_name"] == "Shelf"


def test_bulk_reconcile_selected_writes_stock_back_returns_shortfall_and_finishes_cleanly(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-bulk@example.com",
        household_name="Shopping Bulk Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-bulk@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    product = create_product(
        client,
        household.external_id,
        name="Juice",
        default_unit="bottle",
        aliases=[],
        barcodes=[],
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
    )

    client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={
            "product_external_id": product["external_id"],
            "quantity": "5.000",
            "unit": "bottle",
            "source_type": "pantry_product",
        },
    )
    client.post(f"/api/households/{household.external_id}/shopping-list/export")

    pending_snapshot = client.get(f"/api/households/{household.external_id}/shopping-list").json()
    pending_list = pending_snapshot["pending_lists"][0]
    pending_item = pending_list["items"][0]

    bulk_reconcile = client.post(
        f"/api/households/{household.external_id}/shopping-list/pending/{pending_list['external_id']}/bulk",
        json={
            "action": "reconcile_selected",
            "items": [
                {
                    "item_external_id": pending_item["external_id"],
                    "quantity": "3.000",
                    "unit": "bottle",
                    "note": "Weekly top-up",
                }
            ],
        },
    )
    assert bulk_reconcile.status_code == 200
    bulk_payload = bulk_reconcile.json()
    assert bulk_payload["pending_lists"] == []
    assert bulk_payload["history_lists"][0]["lifecycle_state"] == "reconciled"
    assert bulk_payload["active_list"]["items"][0]["quantity"] == "2.000"
    assert bulk_payload["active_list"]["items"][0]["requested_quantity"] == "2.000"

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert overview.status_code == 200
    product_payload = overview.json()["products"][0]
    assert product_payload["total_quantity"] == "4.000"
    assert product_payload["stock_lots"][0]["location_name"] == "Shelf"

    after_finalize_overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert after_finalize_overview.status_code == 200
    assert after_finalize_overview.json()["products"][0]["total_quantity"] == "4.000"


def test_bulk_return_selected_and_delete_selected_update_pending_trip(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-bulk-return@example.com",
        household_name="Shopping Bulk Return Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-bulk-return@example.com")

    client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={"label": "Milk", "quantity": "1.000", "unit": "bottle", "source_type": "manual"},
    )
    client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={"label": "Bread", "quantity": "1.000", "unit": "loaf", "source_type": "manual"},
    )
    client.post(f"/api/households/{household.external_id}/shopping-list/export")

    pending_snapshot = client.get(f"/api/households/{household.external_id}/shopping-list").json()
    pending_list = pending_snapshot["pending_lists"][0]
    milk_item = next(item for item in pending_list["items"] if item["label"] == "Milk")
    bread_item = next(item for item in pending_list["items"] if item["label"] == "Bread")

    returned = client.post(
        f"/api/households/{household.external_id}/shopping-list/pending/{pending_list['external_id']}/bulk",
        json={
            "action": "return_selected",
            "items": [{"item_external_id": milk_item["external_id"], "note": "Buy later"}],
        },
    )
    assert returned.status_code == 200
    assert returned.json()["active_list"]["items"][0]["label"] == "Milk"

    deleted = client.post(
        f"/api/households/{household.external_id}/shopping-list/pending/{pending_list['external_id']}/bulk",
        json={
            "action": "delete_selected",
            "items": [{"item_external_id": bread_item["external_id"]}],
        },
    )
    assert deleted.status_code == 200
    assert deleted.json()["pending_lists"] == []
    assert deleted.json()["active_list"]["items"][0]["label"] == "Milk"
    assert deleted.json()["history_lists"][0]["lifecycle_state"] == "reconciled"


def test_bulk_reconcile_selected_rejects_zero_quantity(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-zero@example.com",
        household_name="Shopping Zero Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-zero@example.com")

    client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={"label": "Soup", "quantity": "2.000", "unit": "can", "source_type": "manual"},
    )
    client.post(f"/api/households/{household.external_id}/shopping-list/export")
    pending_snapshot = client.get(f"/api/households/{household.external_id}/shopping-list").json()
    pending_list = pending_snapshot["pending_lists"][0]
    pending_item = pending_list["items"][0]

    response = client.post(
        f"/api/households/{household.external_id}/shopping-list/pending/{pending_list['external_id']}/bulk",
        json={
            "action": "reconcile_selected",
            "items": [
                {
                    "item_external_id": pending_item["external_id"],
                    "quantity": "0.000",
                    "unit": "can",
                }
            ],
        },
    )
    assert response.status_code == 400
    assert "greater than zero" in response.json()["detail"]


def test_reconciliation_can_return_shortfall_to_active_list(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-shortfall@example.com",
        household_name="Shopping Shortfall Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-shortfall@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    product = create_product(
        client,
        household.external_id,
        name="Tea bags",
        default_unit="box",
        aliases=[],
        barcodes=[],
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
    )

    added = client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={
            "product_external_id": product["external_id"],
            "quantity": "5.000",
            "unit": "box",
            "source_type": "pantry_product",
        },
    )
    assert added.status_code == 201
    client.post(f"/api/households/{household.external_id}/shopping-list/export")
    pending_snapshot = client.get(f"/api/households/{household.external_id}/shopping-list").json()
    pending_list = pending_snapshot["pending_lists"][0]
    pending_item = pending_list["items"][0]

    saved = client.put(
        f"/api/households/{household.external_id}/shopping-list/items/{pending_item['external_id']}",
        json={"status": "purchased", "quantity": "3.000", "unit": "box"},
    )
    assert saved.status_code == 200
    active_items = saved.json()["active_list"]["items"]
    assert len(active_items) == 1
    assert active_items[0]["quantity"] == "2.000"
    assert active_items[0]["requested_quantity"] == "2.000"


def test_reconciliation_blocks_purchased_new_items_without_attached_product(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-new-product@example.com",
        household_name="Shopping New Product Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-new-product@example.com")

    added = client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={"label": "Tomato soup", "quantity": "2.000", "unit": "can", "source_type": "manual"},
    )
    assert added.status_code == 201
    client.post(f"/api/households/{household.external_id}/shopping-list/export")
    pending_snapshot = client.get(f"/api/households/{household.external_id}/shopping-list").json()
    pending_list = pending_snapshot["pending_lists"][0]
    pending_item = pending_list["items"][0]

    saved = client.put(
        f"/api/households/{household.external_id}/shopping-list/items/{pending_item['external_id']}",
        json={"status": "purchased", "quantity": "2.000", "unit": "can"},
    )
    assert saved.status_code == 400
    assert "Create a Pantry product for Tomato soup" in saved.json()["detail"]


def test_finish_trip_can_return_remaining_unresolved_items_to_active_list(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-finish-return@example.com",
        household_name="Shopping Finish Return Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-finish-return@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    product = create_product(
        client,
        household.external_id,
        name="Milk",
        default_unit="bottle",
        aliases=[],
        barcodes=[],
    )

    client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={
            "product_external_id": product["external_id"],
            "quantity": "2.000",
            "unit": "bottle",
            "pantry_location_external_id": shelf["external_id"],
            "source_type": "pantry_product",
        },
    )
    client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={"label": "Bread", "quantity": "1.000", "unit": "loaf", "source_type": "manual"},
    )
    client.post(f"/api/households/{household.external_id}/shopping-list/export")
    pending_list = client.get(f"/api/households/{household.external_id}/shopping-list").json()["pending_lists"][0]
    milk_item = next(item for item in pending_list["items"] if item["label"] == "Milk")

    saved = client.put(
        f"/api/households/{household.external_id}/shopping-list/items/{milk_item['external_id']}",
        json={"status": "purchased", "quantity": "2.000", "unit": "bottle"},
    )
    assert saved.status_code == 200

    finished = client.post(
        f"/api/households/{household.external_id}/shopping-list/pending/{pending_list['external_id']}/finalize",
        json={"unresolved_action": "return_to_active", "return_shortfalls_to_active": False},
    )
    assert finished.status_code == 200
    payload = finished.json()
    assert payload["pending_lists"] == []
    assert payload["active_list"]["items"][0]["label"] == "Bread"
    assert payload["history_lists"][0]["lifecycle_state"] == "reconciled"


def test_finish_trip_can_delete_remaining_unresolved_items(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-finish-delete@example.com",
        household_name="Shopping Finish Delete Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-finish-delete@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")
    product = create_product(
        client,
        household.external_id,
        name="Milk",
        default_unit="bottle",
        aliases=[],
        barcodes=[],
    )

    client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={
            "product_external_id": product["external_id"],
            "quantity": "2.000",
            "unit": "bottle",
            "pantry_location_external_id": shelf["external_id"],
            "source_type": "pantry_product",
        },
    )
    client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={"label": "Bread", "quantity": "1.000", "unit": "loaf", "source_type": "manual"},
    )
    client.post(f"/api/households/{household.external_id}/shopping-list/export")
    pending_list = client.get(f"/api/households/{household.external_id}/shopping-list").json()["pending_lists"][0]
    milk_item = next(item for item in pending_list["items"] if item["label"] == "Milk")

    saved = client.put(
        f"/api/households/{household.external_id}/shopping-list/items/{milk_item['external_id']}",
        json={"status": "purchased", "quantity": "2.000", "unit": "bottle"},
    )
    assert saved.status_code == 200

    finished = client.post(
        f"/api/households/{household.external_id}/shopping-list/pending/{pending_list['external_id']}/finalize",
        json={"unresolved_action": "delete", "return_shortfalls_to_active": False},
    )
    assert finished.status_code == 200
    payload = finished.json()
    assert payload["pending_lists"] == []
    assert payload["active_list"]["items"] == []
    assert payload["history_lists"][0]["lifecycle_state"] == "reconciled"


def test_shopping_list_item_can_attach_product_after_manual_trip_entry(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-attach@example.com",
        household_name="Shopping Attach Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-attach@example.com")

    added = client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={"label": "Tomato soup", "quantity": "2.000", "unit": "can", "source_type": "manual"},
    )
    assert added.status_code == 201
    export_response = client.post(f"/api/households/{household.external_id}/shopping-list/export")
    assert export_response.status_code == 200
    pending_payload = client.get(f"/api/households/{household.external_id}/shopping-list").json()
    item_external_id = pending_payload["pending_lists"][0]["items"][0]["external_id"]

    product = create_product(
        client,
        household.external_id,
        name="Tomato soup",
        default_unit="can",
        aliases=[],
        barcodes=[],
    )

    attached = client.post(
        f"/api/households/{household.external_id}/shopping-list/items/{item_external_id}/attach-product",
        json={"product_external_id": product["external_id"]},
    )
    assert attached.status_code == 200
    attached_payload = attached.json()
    assert attached_payload["pending_lists"][0]["items"][0]["product_name"] == "Tomato soup"


def test_shopping_list_history_limit_supports_dedicated_history_page(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="shopping-history@example.com",
        household_name="Shopping History Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="shopping-history@example.com")

    for index in range(7):
        client.post(
            f"/api/households/{household.external_id}/shopping-list/items",
            json={
                "label": f"Trip item {index}",
                "quantity": "1.000",
                "unit": "pack",
                "source_type": "manual",
            },
        )
        client.post(f"/api/households/{household.external_id}/shopping-list/export")
        pending_list = client.get(f"/api/households/{household.external_id}/shopping-list").json()["pending_lists"][0]
        client.post(
            f"/api/households/{household.external_id}/shopping-list/pending/{pending_list['external_id']}/return-to-active",
            json={},
        )

    default_history = client.get(f"/api/households/{household.external_id}/shopping-list")
    assert default_history.status_code == 200
    assert len(default_history.json()["history_lists"]) == 6

    full_history = client.get(f"/api/households/{household.external_id}/shopping-list?history_limit=100")
    assert full_history.status_code == 200
    assert len(full_history.json()["history_lists"]) == 7


def test_household_admin_can_delete_product_and_dependent_pantry_records(client, db_session, monkeypatch):
    admin, household = create_household_with_role(
        db_session,
        email="delete-product-admin@example.com",
        household_name="Delete Product Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="delete-product-admin@example.com")

    room = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, room["external_id"], "Shelf")

    candidate = build_enrichment_candidate(
        source_product_id="5000111046244",
        source_product_name="HP Brown Sauce",
        match_status="barcode_exact",
        match_confidence=1.0,
    )

    class StubOpenFoodFactsClient:
        def fetch_product_by_id(self, source_product_id: str):
            return candidate if source_product_id == "5000111046244" else None

    monkeypatch.setattr(
        "app.services.product_enrichment.get_default_open_food_facts_client",
        lambda: StubOpenFoodFactsClient(),
    )

    product = create_product(
        client,
        household.external_id,
        name="Brown sauce",
        default_unit="bottle",
        aliases=["HP sauce"],
        barcodes=["5000111046244"],
        confirmed_enrichment={
            "source_name": "open_food_facts",
            "source_product_id": "5000111046244",
            "match_status": "barcode_exact",
        },
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
    )
    shopping_item = client.post(
        f"/api/households/{household.external_id}/shopping-list/items",
        json={
            "product_external_id": product["external_id"],
            "quantity": "1.000",
            "unit": "bottle",
            "source_type": "pantry_product",
        },
    )
    assert shopping_item.status_code == 201

    delete_response = client.delete(
        f"/api/households/{household.external_id}/products/{product['external_id']}"
    )
    assert delete_response.status_code == 200
    assert "Deleted Brown sauce" in delete_response.json()["message"]

    overview = client.get(f"/api/households/{household.external_id}/pantry/overview")
    assert overview.status_code == 200
    assert overview.json()["products"] == []

    assert db_session.scalar(select(ProductEnrichment)) is None
    assert db_session.scalar(select(StockLot)) is None

    shopping_payload = client.get(f"/api/households/{household.external_id}/shopping-list").json()
    assert shopping_payload["active_list"]["items"][0]["label"] == "Brown sauce"
    assert shopping_payload["active_list"]["items"][0]["product_external_id"] is None

    delete_audit = db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "product.deleted")
    )
    assert delete_audit is not None
    assert delete_audit.actor_user_id == admin.id


def test_household_user_cannot_delete_product_record(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="delete-product-user@example.com",
        household_name="Delete Product User Household",
        role_code=HOUSEHOLD_USER_ROLE,
    )
    login(client, email="delete-product-user@example.com")

    product = create_product_record(
        db_session,
        household=household,
        actor=create_user(db_session, email="shadow-admin@example.com", password=PASSWORD),
        name="Pasta",
        default_unit="count",
        aliases=[],
        barcodes=[],
    )

    response = client.delete(f"/api/households/{household.external_id}/products/{product.external_id}")
    assert response.status_code == 404


def test_pantry_endpoints_enforce_household_scoping(client, db_session):
    _, allowed_household = create_member_household(
        db_session,
        email="scope@example.com",
        household_name="Allowed",
    )
    denied_household = create_household(db_session, name="Denied")
    login(client, email="scope@example.com")

    allowed = client.get(f"/api/households/{allowed_household.external_id}/pantry/overview")
    denied = client.get(f"/api/households/{denied_household.external_id}/pantry/overview")

    assert allowed.status_code == 200
    assert denied.status_code == 404


def test_household_user_cannot_change_pantry_structure(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="pantry-user@example.com",
        household_name="Pantry User Household",
        role_code=HOUSEHOLD_USER_ROLE,
    )
    login(client, email="pantry-user@example.com")

    group_response = client.post(
        f"/api/households/{household.external_id}/location-groups",
        json={"name": "Kitchen"},
    )
    assert group_response.status_code == 404

    product_response = client.post(
        f"/api/households/{household.external_id}/products",
        json={"name": "Pasta", "default_unit": "count", "aliases": [], "barcodes": []},
    )
    assert product_response.status_code == 404


def test_household_admin_can_change_pantry_structure(client, db_session):
    _, household = create_household_with_role(
        db_session,
        email="pantry-admin@example.com",
        household_name="Pantry Admin Household",
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    login(client, email="pantry-admin@example.com")

    group_response = client.post(
        f"/api/households/{household.external_id}/location-groups",
        json={"name": "Kitchen"},
    )
    assert group_response.status_code == 201

    location_response = client.post(
        f"/api/households/{household.external_id}/locations",
        json={
            "location_group_external_id": group_response.json()["external_id"],
            "name": "Shelf A",
        },
    )
    assert location_response.status_code == 201

    product_response = client.post(
        f"/api/households/{household.external_id}/products",
        json={"name": "Pasta", "default_unit": "count", "aliases": [], "barcodes": []},
    )
    assert product_response.status_code == 201
