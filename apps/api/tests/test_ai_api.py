from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.domain.ai import AI_PROVIDER_OLLAMA
from app.domain.roles import HOUSEHOLD_ADMIN_ROLE
from app.models.audit_event import AuditEvent
from app.models.product import Product
from app.schemas.pantry import ConfirmedProductEnrichmentRequest
from app.schemas.ai import AISuggestionRequest
from app.services.ai_config import upsert_instance_provider_config
from app.services.ai_context import build_household_ai_context
from app.services.product_enrichment import apply_confirmed_product_enrichment
from app.services.ai_providers import AIProviderHealth, StructuredCompletionResult
from app.services.platform_features import FLAG_AI_SUGGESTIONS, upsert_feature_flag
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
    assert context_bundle.payload["pantry"]["products"][0]["product_name"] == "Pasta"
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

    enrichment = context_bundle.payload["pantry"]["products"][0]["enrichment"]
    assert enrichment["ingredients_text"] == "Tomatoes, vinegar, barley malt"
    assert enrichment["allergen_tags"] == ["Gluten"]
    assert enrichment["labels"] == ["Vegetarian"]
    assert context_bundle.payload["dietary_context"]["enriched_products"][0]["enrichment"]["traces_text"] == "Mustard"


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
    assert "AI suggestion generation failed" in suggestion_response.json()["detail"]

    status_response = client.get(f"/api/households/{household.external_id}/ai/status")
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["available"] is False
    assert payload["health_status"] == "unhealthy"
    assert "Provider request timed out." in payload["reason"]


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
