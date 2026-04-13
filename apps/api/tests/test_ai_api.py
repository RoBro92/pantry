from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.domain.ai import AI_PROVIDER_OLLAMA, AI_PROVIDER_OPENAI
from app.domain.roles import HOUSEHOLD_ADMIN_ROLE
from app.models.audit_event import AuditEvent
from app.models.product import Product
from app.models.product_intelligence import ProductIntelligence
from app.models.stock_lot import StockLot
from app.schemas.pantry import ConfirmedProductEnrichmentRequest
from app.schemas.ai import AISuggestionRequest
from app.services.ai_config import upsert_instance_provider_config
from app.services.ai_context import build_household_ai_context
from app.services.product_enrichment import apply_confirmed_product_enrichment
from app.services.ai_providers import AIProviderHealth, StructuredCompletionResult
from app.services.ai_providers.errors import AIProviderError
from app.services.platform_features import FLAG_AI_SUGGESTIONS, upsert_feature_flag
from app.services.product_intelligence import (
    PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
    PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
    PRODUCT_INTELLIGENCE_SCOPE,
    build_product_intelligence_source_data_hash,
)
from app.services.auth import (
    create_household,
    create_membership,
    create_platform_admin,
    create_user,
)
from app.services.tenancy import resolve_household_access


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
        role_code=HOUSEHOLD_ADMIN_ROLE,
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


def add_stock_lot(client, household_external_id: str, **payload) -> dict:
    response = client.post(f"/api/households/{household_external_id}/stock-lots", json=payload)
    assert response.status_code == 201
    return response.json()


class StubAIProviderAdapter:
    def check_health(self) -> AIProviderHealth:
        return AIProviderHealth(
            is_healthy=True,
            status="healthy",
            message=None,
            models=["llama3.2"],
            capabilities={
                "supports_model_listing": True,
                "supports_structured_output": True,
            },
        )

    def list_models(self) -> list[str]:
        return ["llama3.2"]

    def generate_structured_output(self, request) -> StructuredCompletionResult:
        assert request.model == "llama3.2"
        assert request.user_payload["request"]["kind"] in {
            "meal_suggestions",
            "recipe_gap",
        }
        return StructuredCompletionResult(
            output_text='{"suggestions":[{"title":"Use the pasta","summary":"Cook pasta soon.","rationale":"It is already in the pantry.","pantry_product_names":["Pasta"],"expiring_product_names":["Tomatoes"],"missing_product_names":[],"extra_ingredient_names":["Lemon"],"substitution_ideas":["Swap basil for parsley"],"caution":"Check expiry dates before cooking."}]}',
            parsed_output={
                "suggestions": [
                    {
                        "title": "Use the pasta",
                        "summary": "Cook pasta soon.",
                        "rationale": "It is already in the pantry.",
                        "pantry_product_names": ["Pasta"],
                        "expiring_product_names": ["Tomatoes"],
                        "missing_product_names": [],
                        "extra_ingredient_names": ["Lemon"],
                        "substitution_ideas": ["Swap basil for parsley"],
                        "caution": "Check expiry dates before cooking.",
                    }
                ]
            },
            provider_request_id="req_stub_123",
        )


class FailingSuggestionAdapter(StubAIProviderAdapter):
    def generate_structured_output(self, request) -> StructuredCompletionResult:
        raise RuntimeError("Provider request timed out.")


def test_ai_context_assembly_uses_structured_pantry_and_recipe_data(client, db_session):
    user, household = create_member_household(
        db_session,
        email="ai-context@example.com",
        household_name="AI Context Household",
    )
    login(client, email="ai-context@example.com")

    pantry_group = create_location_group(client, household.external_id, "Pantry")
    shelf = create_location(client, household.external_id, pantry_group["external_id"], "Shelf")
    pasta = create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="count",
        aliases=[],
        barcodes=[],
    )
    tomatoes = create_product(
        client,
        household.external_id,
        name="Tomatoes",
        default_unit="can",
        aliases=[],
        barcodes=[],
    )

    add_stock_lot(
        client,
        household.external_id,
        product_external_id=pasta["external_id"],
        location_external_id=shelf["external_id"],
        quantity="2.000",
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=tomatoes["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
        expires_on=(date.today() + timedelta(days=2)).isoformat(),
    )

    recipe_response = client.post(
        f"/api/households/{household.external_id}/recipes",
        json={
            "title": "Simple Pasta",
            "notes": "Use pantry basics.",
            "ingredients": [
                {"name": "Pasta", "quantity": "1.000", "unit": "count"},
                {"name": "Tomatoes", "quantity": "1.000", "unit": "can"},
            ],
        },
    )
    assert recipe_response.status_code == 201
    recipe_external_id = recipe_response.json()["recipe"]["external_id"]

    access = resolve_household_access(
        db_session,
        household_external_id=household.external_id,
        user=user,
    )
    assert access is not None

    context_bundle = build_household_ai_context(
        db_session,
        access=access,
        request=AISuggestionRequest(
            kind="recipe_gap",
            limit=2,
            recipe_external_id=recipe_external_id,
        ),
    )

    assert context_bundle.snapshot.pantry_product_count == 2
    assert context_bundle.snapshot.active_lot_count == 2
    assert context_bundle.snapshot.near_expiry_lot_count == 1
    assert context_bundle.snapshot.recipe_title == "Simple Pasta"
    assert context_bundle.payload["pantry"]["fallback_products"][0]["product_name"] == "Pasta"
    assert context_bundle.payload["recipes"]["focused_recipe"]["title"] == "Simple Pasta"


def test_household_ai_routes_degrade_cleanly_without_provider_config(client, db_session):
    _, household = create_member_household(
        db_session,
        email="ai-unconfigured@example.com",
        household_name="AI Unconfigured Household",
    )
    login(client, email="ai-unconfigured@example.com")

    status_response = client.get(f"/api/households/{household.external_id}/ai/status")
    assert status_response.status_code == 200
    assert status_response.json()["available"] is False
    assert "No AI provider" in status_response.json()["reason"]

    suggestion_response = client.post(
        f"/api/households/{household.external_id}/ai/suggestions",
        json={"kind": "meal_suggestions", "limit": 2},
    )
    assert suggestion_response.status_code == 503
    assert "No AI provider" in suggestion_response.json()["detail"]


def test_ai_context_includes_product_enrichment_when_available(client, db_session, monkeypatch):
    user, household = create_member_household(
        db_session,
        email="ai-enrichment@example.com",
        household_name="AI Enrichment Household",
    )
    login(client, email="ai-enrichment@example.com")

    pantry_group = create_location_group(client, household.external_id, "Pantry")
    shelf = create_location(client, household.external_id, pantry_group["external_id"], "Shelf")
    product = create_product(
        client,
        household.external_id,
        name="Brown sauce",
        default_unit="bottle",
        aliases=[],
        barcodes=["5000111046244"],
    )

    class StubOpenFoodFactsClient:
        def fetch_product_by_id(self, source_product_id: str):
            from app.schemas.pantry import (
                ProductEnrichmentAttribution,
                ProductEnrichmentCandidate,
                ProductNutritionSummaryItem,
            )

            return ProductEnrichmentCandidate(
                source_name="open_food_facts",
                source_product_id=source_product_id,
                source_barcode=source_product_id,
                source_product_name="HP Brown Sauce",
                source_product_url=f"https://world.openfoodfacts.org/product/{source_product_id}",
                product_image_url="https://images.example.test/product.jpg",
                ingredients_text="Tomatoes, vinegar, barley malt",
                allergens_text="Gluten",
                traces_text="Mustard",
                allergen_tags=["Gluten"],
                trace_tags=["Mustard"],
                nutrition_summary=[
                    ProductNutritionSummaryItem(key="energy-kcal", label="Energy", value=100, unit="kcal")
                ],
                labels=["Vegetarian"],
                categories=["Brown Sauces"],
                match_status="barcode_exact",
                match_confidence=1.0,
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

    monkeypatch.setattr(
        "app.services.product_enrichment.get_default_open_food_facts_client",
        lambda: StubOpenFoodFactsClient(),
    )

    access = resolve_household_access(
        db_session,
        household_external_id=household.external_id,
        user=user,
    )
    assert access is not None

    stored_product = db_session.scalar(select(Product).where(Product.external_id == product["external_id"]))
    assert stored_product is not None

    apply_confirmed_product_enrichment(
        db_session,
        household=access.household,
        actor=user,
        product=stored_product,
        confirmed_enrichment=ConfirmedProductEnrichmentRequest(
            source_name="open_food_facts",
            source_product_id="5000111046244",
            match_status="barcode_exact",
        ),
    )
    db_session.commit()

    add_stock_lot(
        client,
        household.external_id,
        product_external_id=product["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
    )

    context_bundle = build_household_ai_context(
        db_session,
        access=access,
        request=AISuggestionRequest(kind="meal_suggestions", limit=2),
    )

    enrichment = context_bundle.payload["pantry"]["fallback_products"][0]["enrichment"]
    assert enrichment["ingredient_tags"] == []
    assert enrichment["allergen_tags"] == ["Gluten"]
    assert enrichment["categories"] == ["Brown Sauces"]
    assert context_bundle.payload["dietary_context"]["fallback_product_count"] == 1


def test_ai_context_prefers_classified_product_intelligence_with_fallback_for_unclassified_products(
    client,
    db_session,
):
    user, household = create_member_household(
        db_session,
        email="ai-classified-context@example.com",
        household_name="AI Classified Context Household",
    )
    household.dietary_preferences = ["Vegetarian"]
    db_session.add(household)
    db_session.commit()
    login(client, email="ai-classified-context@example.com")

    pantry_group = create_location_group(client, household.external_id, "Pantry")
    shelf = create_location(client, household.external_id, pantry_group["external_id"], "Shelf")
    sauce = create_product(
        client,
        household.external_id,
        name="Brown sauce",
        default_unit="bottle",
        aliases=["HP sauce"],
        barcodes=["5000111046244"],
        manual_ingredient_tags=["Tomatoes", "Vinegar"],
    )
    beans = create_product(
        client,
        household.external_id,
        name="Butter beans",
        default_unit="can",
        aliases=[],
        barcodes=[],
        manual_ingredient_tags=["Beans"],
    )

    add_stock_lot(
        client,
        household.external_id,
        product_external_id=sauce["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=beans["external_id"],
        location_external_id=shelf["external_id"],
        quantity="2.000",
    )

    sauce_product = db_session.scalar(select(Product).where(Product.external_id == sauce["external_id"]))
    assert sauce_product is not None
    db_session.add(
        ProductIntelligence(
            household_id=household.id,
            product_id=sauce_product.id,
            source_provider="ollama",
            source_model="llama3.2",
            classification_scope=PRODUCT_INTELLIGENCE_SCOPE,
            classification_version=PRODUCT_INTELLIGENCE_CLASSIFICATION_VERSION,
            schema_version=PRODUCT_INTELLIGENCE_SCHEMA_VERSION,
            source_data_hash=build_product_intelligence_source_data_hash(sauce_product),
            classified_at=sauce_product.updated_at,
            confidence=0.91,
            rationale_short="Useful condiment classification for recipe matching.",
            primary_ingredient_type="Tomato",
            ingredient_families=["Tomato", "Vinegar"],
            food_category="Condiment",
            dietary_tags=["Vegetarian"],
            allergen_tags=["Gluten"],
            recipe_role_tags=["Sauce", "Seasoning"],
            substitution_groups=["Brown sauce"],
            pantry_use_tags=["Pantry staple", "Shelf stable"],
            structured_metadata={
                "product_format": "Bottled sauce",
                "storage_profile": "Shelf stable",
                "cuisine_tags": ["British"],
                "flavour_tags": ["Tangy"],
                "preparation_tags": ["Ready to use"],
            },
        )
    )
    db_session.commit()

    access = resolve_household_access(
        db_session,
        household_external_id=household.external_id,
        user=user,
    )
    assert access is not None

    context_bundle = build_household_ai_context(
        db_session,
        access=access,
        request=AISuggestionRequest(kind="meal_suggestions", limit=2),
    )

    assert context_bundle.payload["household"]["dietary_preferences"] == ["Vegetarian"]
    assert context_bundle.payload["dietary_context"]["classified_product_count"] == 1
    assert context_bundle.payload["dietary_context"]["fallback_product_count"] == 1
    assert context_bundle.payload["pantry"]["classified_products"][0]["product_name"] == "Brown sauce"
    assert context_bundle.payload["pantry"]["classified_products"][0]["ingredient_families"] == ["Tomato", "Vinegar"]
    assert context_bundle.payload["pantry"]["fallback_products"][0]["product_name"] == "Butter beans"
    assert context_bundle.payload["pantry"]["fallback_products"][0]["manual_ingredient_tags"] == ["Beans"]


def test_household_ai_suggestions_use_provider_adapter_and_record_audit(
    client,
    db_session,
    monkeypatch,
):
    member, household = create_member_household(
        db_session,
        email="ai-member@example.com",
        household_name="AI Suggestion Household",
    )
    admin = create_platform_admin(
        db_session,
        email="ai-admin@example.com",
        password=PASSWORD,
        display_name="AI Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=admin,
        provider_type=AI_PROVIDER_OLLAMA,
        base_url="http://ollama.local:11434",
        default_model="llama3.2",
        api_key=None,
        is_enabled=True,
    )

    monkeypatch.setattr(
        "app.services.ai_config.build_ai_provider_adapter",
        lambda config: StubAIProviderAdapter(),
    )
    monkeypatch.setattr(
        "app.services.ai_suggestions.build_ai_provider_adapter",
        lambda config: StubAIProviderAdapter(),
    )

    login(client, email="ai-member@example.com")

    status_response = client.get(f"/api/households/{household.external_id}/ai/status")
    assert status_response.status_code == 200
    assert status_response.json()["available"] is True
    assert status_response.json()["provider_type"] == AI_PROVIDER_OLLAMA

    suggestion_response = client.post(
        f"/api/households/{household.external_id}/ai/suggestions",
        json={"kind": "meal_suggestions", "limit": 2},
    )
    assert suggestion_response.status_code == 200
    payload = suggestion_response.json()
    assert payload["feature"]["available"] is True
    assert payload["suggestions"][0]["title"] == "Use the pasta"
    assert payload["suggestions"][0]["substitution_ideas"] == ["Swap basil for parsley"]

    audit_actions = db_session.scalars(
        select(AuditEvent.action)
        .where(AuditEvent.household_id == household.id)
        .order_by(AuditEvent.occurred_at.asc())
    ).all()
    assert "ai.suggestion.requested" in audit_actions
    assert "ai.suggestion.completed" in audit_actions


def test_household_ai_suggestions_support_claude_provider_configs(
    client,
    db_session,
    monkeypatch,
):
    member, household = create_member_household(
        db_session,
        email="claude-member@example.com",
        household_name="Claude Suggestion Household",
    )
    admin = create_platform_admin(
        db_session,
        email="claude-admin@example.com",
        password=PASSWORD,
        display_name="Claude Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=admin,
        provider_type="claude",
        base_url="https://api.anthropic.com",
        default_model="claude-sonnet-4-20250514",
        api_key="claude-test-secret",
        is_enabled=True,
    )

    captured_provider_types: list[str] = []

    class StubClaudeSuggestionAdapter(StubAIProviderAdapter):
        def generate_structured_output(self, request) -> StructuredCompletionResult:
            assert request.model == "claude-sonnet-4-20250514"
            assert request.user_payload["request"]["kind"] == "meal_suggestions"
            return StructuredCompletionResult(
                output_text='{"suggestions":[{"title":"Use the pasta","summary":"Cook pasta soon.","rationale":"It is already in the pantry.","pantry_product_names":["Pasta"],"expiring_product_names":["Tomatoes"],"missing_product_names":[],"extra_ingredient_names":["Lemon"],"substitution_ideas":["Swap basil for parsley"],"caution":"Check expiry dates before cooking."}]}',
                parsed_output={
                    "suggestions": [
                        {
                            "title": "Use the pasta",
                            "summary": "Cook pasta soon.",
                            "rationale": "It is already in the pantry.",
                            "pantry_product_names": ["Pasta"],
                            "expiring_product_names": ["Tomatoes"],
                            "missing_product_names": [],
                            "extra_ingredient_names": ["Lemon"],
                            "substitution_ideas": ["Swap basil for parsley"],
                            "caution": "Check expiry dates before cooking.",
                        }
                    ]
                },
                provider_request_id="claude_req_123",
            )

    def build_stub_adapter(config):
        captured_provider_types.append(config.provider_type)
        return StubClaudeSuggestionAdapter()

    monkeypatch.setattr(
        "app.services.ai_config.build_ai_provider_adapter",
        build_stub_adapter,
    )
    monkeypatch.setattr(
        "app.services.ai_suggestions.build_ai_provider_adapter",
        build_stub_adapter,
    )

    login(client, email="claude-member@example.com")

    status_response = client.get(f"/api/households/{household.external_id}/ai/status")
    assert status_response.status_code == 200
    assert status_response.json()["provider_type"] == "claude"

    suggestion_response = client.post(
        f"/api/households/{household.external_id}/ai/suggestions",
        json={"kind": "meal_suggestions", "limit": 2},
    )
    assert suggestion_response.status_code == 200
    assert suggestion_response.json()["feature"]["provider_type"] == "claude"
    assert "claude" in captured_provider_types


def test_household_ai_generation_failures_degrade_cleanly_and_update_status(
    client,
    db_session,
    monkeypatch,
):
    _, household = create_member_household(
        db_session,
        email="ai-failure@example.com",
        household_name="AI Failure Household",
    )
    admin = create_platform_admin(
        db_session,
        email="ai-failure-admin@example.com",
        password=PASSWORD,
        display_name="AI Failure Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=admin,
        provider_type=AI_PROVIDER_OLLAMA,
        base_url="http://ollama.local:11434",
        default_model="llama3.2",
        api_key=None,
        is_enabled=True,
    )

    monkeypatch.setattr(
        "app.services.ai_config.build_ai_provider_adapter",
        lambda config: FailingSuggestionAdapter(),
    )
    monkeypatch.setattr(
        "app.services.ai_suggestions.build_ai_provider_adapter",
        lambda config: FailingSuggestionAdapter(),
    )

    login(client, email="ai-failure@example.com")

    suggestion_response = client.post(
        f"/api/households/{household.external_id}/ai/suggestions",
        json={"kind": "meal_suggestions", "limit": 2},
    )
    assert suggestion_response.status_code == 503
    assert "temporarily unavailable" in suggestion_response.json()["detail"].lower()

    status_response = client.get(f"/api/households/{household.external_id}/ai/status")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["available"] is False
    assert payload["health_status"] == "unhealthy"
    assert "temporarily unavailable" in payload["reason"].lower()


def test_ai_meal_suggestions_support_openai_provider_configs(client, db_session, monkeypatch):
    member, household = create_member_household(
        db_session,
        email="openai-meals@example.com",
        household_name="OpenAI Meals Household",
    )
    admin = create_platform_admin(
        db_session,
        email="openai-meals-admin@example.com",
        password=PASSWORD,
        display_name="OpenAI Meals Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=admin,
        provider_type=AI_PROVIDER_OPENAI,
        base_url="https://api.openai.com/v1",
        default_model="gpt-4.1-mini",
        api_key="openai-test-secret",
        is_enabled=True,
    )

    captured_provider_types: list[str] = []

    class StubOpenAIMealAdapter(StubAIProviderAdapter):
        def generate_structured_output(self, request) -> StructuredCompletionResult:
            assert request.model == "gpt-4.1-mini"
            return StructuredCompletionResult(
                output_text='{"suggestions":[{"title":"Simple toast","short_summary":"Fast pantry meal.","why_it_matches":"Uses what is already available.","dietary_fit_summary":"Fits the selected preferences.","source":{"kind":"ai_generated","label":"AI-generated"},"ingredients":[],"steps":["Toast the bread."]}]}',
                parsed_output={
                    "suggestions": [
                        {
                            "title": "Simple toast",
                            "short_summary": "Fast pantry meal.",
                            "why_it_matches": "Uses what is already available.",
                            "dietary_fit_summary": "Fits the selected preferences.",
                            "source": {
                                "kind": "ai_generated",
                                "label": "AI-generated",
                            },
                            "ingredients": [],
                            "steps": ["Toast the bread."],
                        }
                    ]
                },
                provider_request_id="openai_meal_req_123",
            )

    def build_stub_adapter(config):
        captured_provider_types.append(config.provider_type)
        return StubOpenAIMealAdapter()

    monkeypatch.setattr("app.services.ai_config.build_ai_provider_adapter", build_stub_adapter)
    monkeypatch.setattr("app.services.ai_meal_suggestions.build_ai_provider_adapter", build_stub_adapter)

    login(client, email="openai-meals@example.com")

    response = client.post(
        f"/api/households/{household.external_id}/ai/meal-suggestions",
        json={
            "people_count": 1,
            "selected_user_external_ids": [member.external_id],
            "meal_type": "dinner",
            "extra_portion_count": 0,
            "max_total_minutes": 20,
            "prioritize_near_expiry": False,
            "allow_extra_ingredients": True,
            "pantry_only": False,
            "temporary_include_preferences": [],
            "temporary_exclude_preferences": [],
            "removed_preference_pills": [],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["feature"]["provider_type"] == "openai"
    assert payload["suggestions"][0]["title"] == "Simple toast"
    assert "openai" in captured_provider_types


def test_ai_meal_suggestions_surface_friendly_openai_errors(client, db_session, monkeypatch):
    member, household = create_member_household(
        db_session,
        email="openai-meal-error@example.com",
        household_name="OpenAI Error Household",
    )
    admin = create_platform_admin(
        db_session,
        email="openai-meal-error-admin@example.com",
        password=PASSWORD,
        display_name="OpenAI Error Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=admin,
        provider_type=AI_PROVIDER_OPENAI,
        base_url="https://api.openai.com/v1",
        default_model="gpt-4.1-mini",
        api_key="openai-test-secret",
        is_enabled=True,
    )

    class FailingOpenAIAdapter(StubAIProviderAdapter):
        def generate_structured_output(self, request) -> StructuredCompletionResult:
            request_obj = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            response = httpx.Response(
                400,
                request=request_obj,
                text='{"error":{"message":"Invalid schema for response_format json_schema"}}',
            )
            raise httpx.HTTPStatusError("400 Client Error", request=request_obj, response=response)

    monkeypatch.setattr("app.services.ai_config.build_ai_provider_adapter", lambda config: FailingOpenAIAdapter())
    monkeypatch.setattr(
        "app.services.ai_meal_suggestions.build_ai_provider_adapter",
        lambda config: FailingOpenAIAdapter(),
    )

    login(client, email="openai-meal-error@example.com")

    response = client.post(
        f"/api/households/{household.external_id}/ai/meal-suggestions",
        json={
            "people_count": 1,
            "selected_user_external_ids": [member.external_id],
            "meal_type": "dinner",
            "extra_portion_count": 0,
            "max_total_minutes": 20,
            "prioritize_near_expiry": False,
            "allow_extra_ingredients": True,
            "pantry_only": False,
            "temporary_include_preferences": [],
            "temporary_exclude_preferences": [],
            "removed_preference_pills": [],
        },
    )
    assert response.status_code == 503
    assert "gpt-4.1-mini" in response.json()["detail"]
    assert "gpt-5.4-mini" in response.json()["detail"]
    assert "gpt-5.4" in response.json()["detail"]


def test_household_ai_feature_flag_can_disable_household_access(client, db_session):
    _, household = create_member_household(
        db_session,
        email="ai-flag@example.com",
        household_name="AI Flag Household",
    )
    upsert_feature_flag(
        db_session,
        flag_key=FLAG_AI_SUGGESTIONS,
        scope_type="household",
        scope_key=household.external_id,
        is_enabled=False,
        note="Disabled for this household.",
    )

    login(client, email="ai-flag@example.com")

    status_response = client.get(f"/api/households/{household.external_id}/ai/status")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["feature_enabled"] is False
    assert status_payload["available"] is False
    assert "disabled" in status_payload["reason"].lower()

    suggestion_response = client.post(
        f"/api/households/{household.external_id}/ai/suggestions",
        json={"kind": "meal_suggestions", "limit": 1},
    )
    assert suggestion_response.status_code == 403
    assert "disabled" in suggestion_response.json()["detail"].lower()


def test_ai_meal_planner_returns_household_members_and_existing_preferences(client, db_session):
    member, household = create_member_household(
        db_session,
        email="meal-planner@example.com",
        household_name="Meal Planner Household",
    )
    second_user = create_user(
        db_session,
        email="meal-planner-second@example.com",
        password=PASSWORD,
        display_name="Second Planner",
    )
    create_membership(
        db_session,
        user=second_user,
        household=household,
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    household.dietary_preferences = ["Vegetarian", "Gluten-free"]
    member.dietary_preferences = ["Nut allergy"]
    second_user.dietary_preferences = ["Dairy-free"]
    db_session.add_all([household, member, second_user])
    db_session.commit()

    login(client, email="meal-planner@example.com")

    response = client.get(f"/api/households/{household.external_id}/ai/meal-planner")
    assert response.status_code == 200
    payload = response.json()
    assert payload["household_dietary_preferences"] == ["Vegetarian", "Gluten-free"]
    member_map = {
        item["display_name"]: item["dietary_preferences"]
        for item in payload["members"]
    }
    assert member_map["Meal-Planner"] == ["Nut allergy"]
    assert member_map["Second Planner"] == ["Dairy-free"]


def test_ai_meal_suggestions_support_pantry_only_and_pantry_plus_extras_modes(
    client,
    db_session,
    monkeypatch,
):
    member, household = create_member_household(
        db_session,
        email="meal-suggestions@example.com",
        household_name="Meal Suggestions Household",
    )
    second_user = create_user(
        db_session,
        email="meal-suggestions-second@example.com",
        password=PASSWORD,
        display_name="Second Diner",
    )
    create_membership(
        db_session,
        user=second_user,
        household=household,
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )
    household.dietary_preferences = ["Vegetarian"]
    member.dietary_preferences = ["Nut allergy"]
    second_user.dietary_preferences = ["Gluten-free"]
    db_session.add_all([household, member, second_user])
    db_session.commit()
    login(client, email="meal-suggestions@example.com")

    pantry_group = create_location_group(client, household.external_id, "Pantry")
    shelf = create_location(client, household.external_id, pantry_group["external_id"], "Shelf")
    pasta = create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="count",
        aliases=[],
        barcodes=[],
    )
    tomatoes = create_product(
        client,
        household.external_id,
        name="Tomatoes",
        default_unit="can",
        aliases=[],
        barcodes=[],
    )

    add_stock_lot(
        client,
        household.external_id,
        product_external_id=pasta["external_id"],
        location_external_id=shelf["external_id"],
        quantity="2.000",
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=tomatoes["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
    )

    recipe_response = client.post(
        f"/api/households/{household.external_id}/recipes",
        json={
            "title": "Simple Pasta",
            "notes": "Pantry staple.",
            "ingredients": [
                {"name": "Pasta", "quantity": "1.000", "unit": "count"},
                {"name": "Tomatoes", "quantity": "1.000", "unit": "can"},
            ],
        },
    )
    assert recipe_response.status_code == 201
    recipe_external_id = recipe_response.json()["recipe"]["external_id"]

    admin = create_platform_admin(
        db_session,
        email="meal-suggestions-admin@example.com",
        password=PASSWORD,
        display_name="Meal Suggestions Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=admin,
        provider_type=AI_PROVIDER_OLLAMA,
        base_url="http://ollama.local:11434",
        default_model="llama3.2",
        api_key=None,
        is_enabled=True,
    )

    captured_payloads: list[dict] = []

    class StubMealSuggestionAdapter(StubAIProviderAdapter):
        def generate_structured_output(self, request) -> StructuredCompletionResult:
            captured_payloads.append(request.user_payload)
            pantry_only = bool(request.user_payload["request"]["pantry_only"])
            parsed_output = {
                "suggestions": [
                    {
                        "title": "Simple Pasta Bowl" if pantry_only else "Pasta with Lemon",
                        "short_summary": "Pantry-first dinner.",
                        "why_it_matches": "Uses the core pantry staples already on hand.",
                        "total_time_minutes": 25,
                        "dietary_fit_summary": "Matches the selected dietary preferences.",
                        "source": {
                            "kind": "household_recipe_reference" if pantry_only else "ai_generated",
                            "label": "Household recipe reference" if pantry_only else "AI-generated",
                            "recipe_external_id": recipe_external_id if pantry_only else None,
                            "recipe_title": "Simple Pasta" if pantry_only else None,
                            "recipe_url": None,
                            "provider_name": None,
                        },
                        "ingredients": [
                            {
                                "name": "Pasta",
                                "quantity": "1.000",
                                "unit": "count",
                                "pantry_product_external_id": pasta["external_id"],
                                "is_extra_ingredient": False,
                            },
                            {
                                "name": "Tomatoes",
                                "quantity": "1.000",
                                "unit": "can",
                                "pantry_product_external_id": tomatoes["external_id"],
                                "is_extra_ingredient": False,
                            },
                            *(
                                []
                                if pantry_only
                                else [
                                    {
                                        "name": "Lemon",
                                        "quantity": "1.000",
                                        "unit": "count",
                                        "pantry_product_external_id": pasta["external_id"],
                                        "is_extra_ingredient": True,
                                    }
                                ]
                            ),
                        ],
                        "steps": [
                            "Cook the pasta.",
                            "Warm the tomatoes and combine everything.",
                        ],
                    }
                ]
            }
            return StructuredCompletionResult(
                output_text=str(parsed_output),
                parsed_output=parsed_output,
                provider_request_id="meal_req_123",
            )

    monkeypatch.setattr(
        "app.services.ai_config.build_ai_provider_adapter",
        lambda config: StubMealSuggestionAdapter(),
    )
    monkeypatch.setattr(
        "app.services.ai_meal_suggestions.build_ai_provider_adapter",
        lambda config: StubMealSuggestionAdapter(),
    )

    login(client, email="meal-suggestions@example.com")

    pantry_only_response = client.post(
        f"/api/households/{household.external_id}/ai/meal-suggestions",
        json={
            "people_count": 2,
            "selected_user_external_ids": [member.external_id, second_user.external_id],
            "meal_type": "dinner",
            "extra_portion_count": 1,
            "max_total_minutes": 30,
            "prioritize_near_expiry": True,
            "allow_extra_ingredients": False,
            "pantry_only": True,
            "temporary_include_preferences": ["High-protein"],
            "temporary_exclude_preferences": ["Mushrooms"],
            "removed_preference_pills": ["Vegetarian"],
        },
    )
    assert pantry_only_response.status_code == 200
    pantry_only_payload = pantry_only_response.json()
    assert pantry_only_payload["context_snapshot"]["selected_user_count"] == 2
    assert pantry_only_payload["context_snapshot"]["pantry_only"] is True
    assert pantry_only_payload["suggestions"][0]["pantry_ingredients_available"] == ["Pasta", "Tomatoes"]
    assert pantry_only_payload["suggestions"][0]["extra_ingredients_needed"] == []
    assert pantry_only_payload["suggestions"][0]["source"]["recipe_external_id"] == recipe_external_id
    assert pantry_only_payload["suggestions"][0]["ingredients"][0]["availability_status"] == "available"

    extras_response = client.post(
        f"/api/households/{household.external_id}/ai/meal-suggestions",
        json={
            "people_count": 2,
            "selected_user_external_ids": [member.external_id],
            "meal_type": "dinner",
            "extra_portion_count": 0,
            "max_total_minutes": 30,
            "prioritize_near_expiry": False,
            "allow_extra_ingredients": True,
            "pantry_only": False,
            "temporary_include_preferences": [],
            "temporary_exclude_preferences": [],
            "removed_preference_pills": [],
        },
    )
    assert extras_response.status_code == 200
    extras_payload = extras_response.json()
    assert extras_payload["context_snapshot"]["pantry_only"] is False
    assert extras_payload["suggestions"][0]["extra_ingredients_needed"] == ["Lemon"]
    assert extras_payload["suggestions"][0]["ingredients"][2]["availability_status"] == "unmatched"
    assert "Vegetarian" in captured_payloads[0]["context"]["dietary_preferences"]["base_preferences"]
    assert "High-protein" in captured_payloads[0]["context"]["dietary_preferences"]["active_preferences"]
    assert "Mushrooms" in captured_payloads[0]["context"]["dietary_preferences"]["excluded_preferences"]
    assert captured_payloads[0]["context"]["recipe_candidates"][0]["recipe_external_id"] == recipe_external_id
    assert captured_payloads[1]["request"]["pantry_only"] is False


def test_ai_meal_suggestions_hide_raw_openai_400_details(client, db_session, monkeypatch):
    member, household = create_member_household(
        db_session,
        email="openai-meal-error@example.com",
        household_name="OpenAI Meal Error Household",
    )
    admin = create_platform_admin(
        db_session,
        email="openai-meal-error-admin@example.com",
        password=PASSWORD,
        display_name="OpenAI Meal Error Admin",
    )
    upsert_instance_provider_config(
        db_session,
        actor=admin,
        provider_type="openai",
        base_url="https://api.openai.com/v1",
        default_model="gpt-5.4-mini",
        api_key="openai-test-secret",
        is_enabled=True,
    )

    class FailingOpenAIAdapter:
        def generate_structured_output(self, request) -> StructuredCompletionResult:
            raise AIProviderError(
                (
                    "The selected OpenAI model (gpt-5.4-mini) is not compatible with Pantry's "
                    "structured AI requests on Chat Completions. Choose a recommended OpenAI "
                    "model such as gpt-4.1-mini, gpt-5.4-mini, gpt-5.4."
                ),
                diagnostic_message=(
                    "Client error '400 Bad Request' for url "
                    "'https://api.openai.com/v1/chat/completions'"
                ),
                category="unsupported_model",
            )

    monkeypatch.setattr(
        "app.services.ai_meal_suggestions.refresh_provider_health",
        lambda db, config: AIProviderHealth(
            is_healthy=True,
            status="healthy",
            message=None,
            models=["gpt-5.4-mini"],
            capabilities={"supports_structured_output": True},
        ),
    )
    monkeypatch.setattr(
        "app.services.ai_meal_suggestions.build_ai_provider_adapter",
        lambda config: FailingOpenAIAdapter(),
    )

    login(client, email="openai-meal-error@example.com")

    response = client.post(
        f"/api/households/{household.external_id}/ai/meal-suggestions",
        json={
            "people_count": 2,
            "selected_user_external_ids": [member.external_id],
            "meal_type": "dinner",
            "extra_portion_count": 0,
            "max_total_minutes": 30,
            "prioritize_near_expiry": False,
            "allow_extra_ingredients": True,
            "pantry_only": False,
            "temporary_include_preferences": [],
            "temporary_exclude_preferences": [],
            "removed_preference_pills": [],
        },
    )

    assert response.status_code == 503
    assert "OpenAI model" in response.json()["detail"]
    assert "400 Bad Request" not in response.json()["detail"]
    assert "https://api.openai.com/v1/chat/completions" not in response.json()["detail"]


def test_complete_ai_meal_suggestion_deducts_stock_across_multiple_lots(client, db_session):
    _, household = create_member_household(
        db_session,
        email="meal-complete@example.com",
        household_name="Meal Complete Household",
    )
    login(client, email="meal-complete@example.com")

    pantry_group = create_location_group(client, household.external_id, "Kitchen")
    shelf = create_location(client, household.external_id, pantry_group["external_id"], "Shelf")
    pasta = create_product(
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
        product_external_id=pasta["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
        expires_on=(date.today() + timedelta(days=2)).isoformat(),
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=pasta["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
        expires_on=(date.today() + timedelta(days=5)).isoformat(),
    )

    response = client.post(
        f"/api/households/{household.external_id}/ai/meal-suggestions/complete",
        json={
            "suggestion_id": "meal-suggestion-1",
            "suggestion_title": "Simple Pasta Bowl",
            "ingredients": [
                {
                    "ingredient_id": "meal-suggestion-1-ingredient-1",
                    "name": "Pasta",
                    "quantity": "1.500",
                    "unit": "count",
                    "pantry_product_external_id": pasta["external_id"],
                    "consume_quantity": "1.500",
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["completed"] is True
    assert payload["consumed_ingredients"][0]["status"] == "consumed"
    assert Decimal(payload["consumed_ingredients"][0]["consumed_quantity"]) == Decimal("1.500")

    lots = db_session.scalars(
        select(StockLot)
        .where(StockLot.household_id == household.id)
        .order_by(StockLot.created_at.asc())
    ).all()
    assert len(lots) == 2
    assert lots[0].quantity == Decimal("0.000")
    assert lots[0].depleted_at is not None
    assert lots[1].quantity == Decimal("0.500")
