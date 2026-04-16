from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.ai import AI_HEALTH_HEALTHY
from app.models.ai_provider_config import AIProviderConfig
from app.models.household import Household
from app.models.instance_setting import InstanceSetting
from app.models.location import Location
from app.models.location_group import LocationGroup
from app.models.membership import Membership
from app.models.product import Product
from app.models.product_enrichment import ProductEnrichment
from app.models.setup_state import SetupState
from app.models.stock_lot import StockLot
from app.models.user import User
from app.services.ai_providers import AIProviderHealth
from app.services.auth import authenticate_user
from app.services.development_seed import (
    DEV_MODE_DEMO,
    DEV_MODE_FRESH,
    bootstrap_development_mode,
)
from app.services.secrets import decrypt_secret
from app.services.open_food_facts import OpenFoodFactsUnavailableError
from app.services.smtp import SMTPTestResult
from app.services.setup import is_setup_complete


EXPECTED_BARCODE_PRODUCTS = {
    "Baked Beans": ["5000157024671"],
    "Butter": ["5054775188239"],
    "Cheddar Cheese": ["29060115"],
    "Chickpeas": ["5051399182506"],
    "Chopped Tomatoes": ["5031021164032"],
    "Coconut Milk": ["8997212610412"],
    "Greek Yoghurt": ["5052320269839"],
    "Kidney Beans": ["5018374442215"],
    "Mayonnaise": ["5000157076397"],
    "Oats": ["5000108022152"],
    "Olive Oil": ["6191509900671"],
    "Pasta": ["8076800195057"],
    "Rice": ["20142360"],
    "Soy Sauce": ["8715035110106"],
    "Stock Cubes": ["5013665112273"],
    "Sweetcorn": ["5050179136500"],
    "Tomato Puree": ["5010061000098"],
    "Tuna": ["5000171061522"],
    "Wraps": ["4056489983507"],
}

EXPECTED_MANUAL_PRODUCTS = {
    "Bacon",
    "Black Pepper",
    "Brown Bread Rolls",
    "Carrots",
    "Chicken Thigh Fillets",
    "Cucumber",
    "Cumin",
    "Curry Powder",
    "Eggs",
    "Garlic",
    "Ham",
    "Honey",
    "Lemons",
    "Milk",
    "Mushrooms",
    "Oregano",
    "Onions",
    "Paprika",
    "Peppers",
    "Potatoes",
    "Salt",
    "Spinach",
    "White Bread",
}


class NoOpenFoodFactsClient:
    def lookup_by_barcode(self, _barcode: str):
        return None


class UnavailableOpenFoodFactsClient:
    def lookup_by_barcode(self, _barcode: str):
        raise OpenFoodFactsUnavailableError("OFF unavailable")


def test_fresh_development_mode_resets_to_uninitialized_state(db_session):
    bootstrap_development_mode(db_session, mode=DEV_MODE_DEMO, off_client=NoOpenFoodFactsClient())

    manifest = bootstrap_development_mode(db_session, mode=DEV_MODE_FRESH)

    assert manifest.mode == DEV_MODE_FRESH
    assert manifest.entry_path == "/setup"
    assert manifest.setup_complete is False
    assert manifest.bootstrap_warnings == []
    assert manifest.users == {}
    assert is_setup_complete(db_session) is False
    assert db_session.scalar(select(User)) is None
    assert db_session.scalar(select(Household)) is None
    assert db_session.scalar(select(SetupState)) is None


def test_demo_development_mode_seeds_expected_fixture_state(db_session):
    manifest = bootstrap_development_mode(db_session, mode=DEV_MODE_DEMO, off_client=NoOpenFoodFactsClient())

    assert manifest.mode == DEV_MODE_DEMO
    assert manifest.entry_path == "/login"
    assert manifest.setup_complete is True
    assert manifest.bootstrap_warnings == []
    assert sorted(manifest.users) == ["demoadmin", "demouser"]
    assert manifest.users["demoadmin"]["password"] == "demopass"
    assert manifest.users["demouser"]["password"] == "demopass"
    assert manifest.household_name == "demohouse"
    assert is_setup_complete(db_session) is True

    assert authenticate_user(db_session, "demoadmin", "demopass") is not None
    assert authenticate_user(db_session, "demouser", "demopass") is not None

    users = db_session.scalars(select(User).order_by(User.email)).all()
    assert [user.email for user in users] == ["demoadmin", "demouser"]

    household = db_session.scalar(select(Household))
    assert household is not None
    assert household.name == "demohouse"

    memberships = db_session.scalars(select(Membership)).all()
    assert len(memberships) == 2

    rooms = db_session.scalars(select(LocationGroup).order_by(LocationGroup.name)).all()
    assert [room.name for room in rooms] == ["Garage", "Kitchen"]

    locations = db_session.execute(
        select(LocationGroup.name, Location.name)
        .join(Location, Location.location_group_id == LocationGroup.id)
        .order_by(LocationGroup.name, Location.name)
    ).all()
    assert locations == [
        ("Garage", "Freezer"),
        ("Garage", "Fridge"),
        ("Garage", "Shelf"),
        ("Kitchen", "Cupboard"),
        ("Kitchen", "Freezer"),
        ("Kitchen", "Fridge"),
    ]

    products = db_session.scalars(
        select(Product).options(selectinload(Product.barcodes)).order_by(Product.name)
    ).all()
    assert len(products) == len(EXPECTED_BARCODE_PRODUCTS) + len(EXPECTED_MANUAL_PRODUCTS)

    barcode_backed_products = {
        product.name: [barcode.value for barcode in product.barcodes]
        for product in products
        if product.barcodes
    }
    manual_products = {product.name for product in products if not product.barcodes}
    assert barcode_backed_products == EXPECTED_BARCODE_PRODUCTS
    assert manual_products == EXPECTED_MANUAL_PRODUCTS

    stock_lots = db_session.scalars(
        select(StockLot)
        .options(selectinload(StockLot.product))
        .options(selectinload(StockLot.location).selectinload(Location.location_group))
    ).all()
    assert len(stock_lots) == len(products)

    today = date.today()
    products_by_name = {product.name for product in products}
    lots_by_product = {lot.product.name: lot for lot in stock_lots}
    near_expiry_products = {
        lot.product.name
        for lot in stock_lots
        if lot.expires_on is not None and lot.expires_on <= today + timedelta(days=7)
    }
    long_life_products = {
        lot.product.name
        for lot in stock_lots
        if lot.expires_on is not None and lot.expires_on >= today + timedelta(days=120)
    }
    location_counts = {}
    for lot in stock_lots:
        location_key = f"{lot.location.location_group.name}:{lot.location.name}"
        location_counts[location_key] = location_counts.get(location_key, 0) + 1

    assert {"Milk", "Chicken Thigh Fillets", "Greek Yoghurt", "Spinach", "Wraps", "White Bread"} <= near_expiry_products
    assert {"Pasta", "Rice", "Chopped Tomatoes", "Coconut Milk", "Chickpeas", "Olive Oil"} <= long_life_products
    assert location_counts["Kitchen:Fridge"] >= 10
    assert location_counts["Kitchen:Cupboard"] >= 10
    assert location_counts["Garage:Shelf"] >= 8
    assert location_counts["Garage:Fridge"] >= 3

    assert {"Oats", "Milk", "Greek Yoghurt", "Honey", "Eggs", "White Bread"} <= products_by_name
    assert {"Wraps", "Tuna", "Mayonnaise", "Cucumber", "Ham", "Cheddar Cheese"} <= products_by_name
    assert {
        "Pasta",
        "Rice",
        "Chopped Tomatoes",
        "Coconut Milk",
        "Chicken Thigh Fillets",
        "Chickpeas",
        "Kidney Beans",
        "Spinach",
        "Peppers",
        "Carrots",
        "Onions",
        "Garlic",
        "Curry Powder",
    } <= products_by_name

    assert lots_by_product["Milk"].quantity == 2
    assert lots_by_product["Eggs"].quantity == 12
    assert lots_by_product["Pasta"].quantity == 3
    assert lots_by_product["Chopped Tomatoes"].quantity == 4
    assert lots_by_product["Milk"].location.name == "Fridge"
    assert lots_by_product["Pasta"].location.name == "Shelf"

    setup_state = db_session.scalar(select(SetupState))
    assert setup_state is not None
    assert setup_state.status == "completed"

    enrichments = db_session.scalars(select(ProductEnrichment)).all()
    assert enrichments == []


def test_demo_development_mode_bootstraps_local_ai_and_smtp_config_from_environment(
    db_session,
    monkeypatch,
):
    def stub_refresh_provider_health(db, config):
        config.health_status = AI_HEALTH_HEALTHY
        config.health_checked_at = datetime.now(timezone.utc)
        config.health_error = None
        db.add(config)
        db.commit()
        db.refresh(config)
        return AIProviderHealth(
            is_healthy=True,
            status=AI_HEALTH_HEALTHY,
            message=None,
            models=["gpt-5.4-mini"],
            capabilities={"supports_structured_output": True},
        )

    monkeypatch.setattr(
        "app.services.instance_integration_checks.refresh_provider_health",
        stub_refresh_provider_health,
    )
    monkeypatch.setattr(
        "app.services.instance_integration_checks.run_smtp_connectivity_test",
        lambda db: SMTPTestResult(status="passed", ok=True, message="250 OK"),
    )
    monkeypatch.setenv("PANTRY_LOCAL_AI_PROVIDER_TYPE", "openai")
    monkeypatch.setenv("PANTRY_LOCAL_AI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("PANTRY_LOCAL_AI_DEFAULT_MODEL", "gpt-5.4-mini")
    monkeypatch.setenv("PANTRY_LOCAL_AI_API_KEY", "local-openai-secret")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PORT", "587")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_USERNAME", "mailer")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PASSWORD", "local-smtp-secret")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_FROM_EMAIL", "pantry@example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_FROM_NAME", "Pantro Local")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_SECURITY", "starttls")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_ENABLED", "true")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_TEST_RECIPIENT_EMAIL", "test@example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PASSWORD_RESET_ENABLED", "true")

    manifest = bootstrap_development_mode(db_session, mode=DEV_MODE_DEMO, off_client=NoOpenFoodFactsClient())

    assert manifest.mode == DEV_MODE_DEMO

    ai_config = db_session.scalar(select(AIProviderConfig))
    assert ai_config is not None
    assert ai_config.provider_type == "openai"
    assert ai_config.base_url == "https://api.openai.com/v1"
    assert ai_config.default_model == "gpt-5.4-mini"
    assert ai_config.encrypted_api_key is not None
    assert ai_config.encrypted_api_key != "local-openai-secret"
    assert decrypt_secret(ai_config.encrypted_api_key) == "local-openai-secret"
    assert ai_config.health_status == "healthy"
    assert ai_config.health_checked_at is not None

    instance_settings = db_session.scalar(select(InstanceSetting))
    assert instance_settings is not None
    assert instance_settings.smtp_host == "smtp.example.com"
    assert instance_settings.smtp_port == 587
    assert instance_settings.smtp_username == "mailer"
    assert instance_settings.encrypted_smtp_password is not None
    assert instance_settings.encrypted_smtp_password != "local-smtp-secret"
    assert decrypt_secret(instance_settings.encrypted_smtp_password) == "local-smtp-secret"
    assert instance_settings.smtp_from_email == "pantry@example.com"
    assert instance_settings.smtp_from_name == "Pantro Local"
    assert instance_settings.smtp_test_recipient_email == "test@example.com"
    assert instance_settings.smtp_security == "starttls"
    assert instance_settings.smtp_enabled is True
    assert instance_settings.password_reset_enabled is True
    assert instance_settings.smtp_last_test_status == "passed"
    assert instance_settings.smtp_last_tested_at is not None
    assert instance_settings.smtp_last_test_error is None


def test_demo_development_mode_warns_when_local_ai_health_check_fails(db_session, monkeypatch):
    def stub_refresh_provider_health(db, config):
        config.health_status = "unhealthy"
        config.health_checked_at = datetime.now(timezone.utc)
        config.health_error = "OpenAI health failed."
        db.add(config)
        db.commit()
        db.refresh(config)
        return AIProviderHealth(
            is_healthy=False,
            status="unhealthy",
            message="OpenAI health failed.",
            models=[],
            capabilities={},
        )

    monkeypatch.setattr(
        "app.services.instance_integration_checks.refresh_provider_health",
        stub_refresh_provider_health,
    )
    monkeypatch.setenv("PANTRY_LOCAL_AI_PROVIDER_TYPE", "openai")
    monkeypatch.setenv("PANTRY_LOCAL_AI_API_KEY", "local-openai-secret")

    manifest = bootstrap_development_mode(db_session, mode=DEV_MODE_DEMO, off_client=NoOpenFoodFactsClient())

    assert manifest.mode == DEV_MODE_DEMO
    assert manifest.setup_complete is True
    assert manifest.bootstrap_warnings == []
    ai_config = db_session.scalar(select(AIProviderConfig))
    assert ai_config is not None
    assert ai_config.health_status == "unhealthy"
    assert ai_config.health_error == "OpenAI health failed."


def test_demo_development_mode_warns_when_local_smtp_connectivity_test_fails(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.instance_integration_checks.run_smtp_connectivity_test",
        lambda db: SMTPTestResult(status="failed", ok=False, message="SMTP auth failed."),
    )
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PORT", "587")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_USERNAME", "mailer")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PASSWORD", "local-smtp-secret")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_FROM_EMAIL", "pantry@example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_SECURITY", "starttls")

    manifest = bootstrap_development_mode(db_session, mode=DEV_MODE_DEMO, off_client=NoOpenFoodFactsClient())

    assert manifest.mode == DEV_MODE_DEMO
    assert manifest.setup_complete is True
    assert manifest.bootstrap_warnings == []
    instance_settings = db_session.scalar(select(InstanceSetting))
    assert instance_settings is not None
    assert instance_settings.smtp_last_test_status == "failed"
    assert instance_settings.smtp_last_test_error == "SMTP auth failed."


def test_demo_development_mode_warns_when_local_smtp_config_is_incomplete(db_session, monkeypatch):
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_USERNAME", "mailer")

    manifest = bootstrap_development_mode(db_session, mode=DEV_MODE_DEMO, off_client=NoOpenFoodFactsClient())

    assert manifest.mode == DEV_MODE_DEMO
    assert manifest.setup_complete is True
    assert manifest.bootstrap_warnings == []
    instance_settings = db_session.scalar(select(InstanceSetting))
    assert instance_settings is None or instance_settings.smtp_host is None


def test_demo_development_mode_ignores_open_food_facts_failures(db_session):
    manifest = bootstrap_development_mode(
        db_session,
        mode=DEV_MODE_DEMO,
        off_client=UnavailableOpenFoodFactsClient(),
    )

    assert manifest.enriched_product_names == []
    assert is_setup_complete(db_session) is True
    assert db_session.scalars(select(ProductEnrichment)).all() == []


def test_demo_development_mode_bootstraps_instance_ai_from_local_env(db_session, monkeypatch):
    monkeypatch.setenv("PANTRY_LOCAL_AI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("PANTRY_LOCAL_AI_DEFAULT_MODEL", "gpt-5.4-mini")
    monkeypatch.setenv("PANTRY_LOCAL_AI_API_KEY", "openai-local-test-key")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PORT", "587")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_USERNAME", "mailer")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_FROM_EMAIL", "pantry@example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_FROM_NAME", "Pantro")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_SECURITY", "starttls")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_ENABLED", "true")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_TEST_RECIPIENT_EMAIL", "test@example.com")
    monkeypatch.setenv("PANTRY_LOCAL_SMTP_PASSWORD_RESET_ENABLED", "true")
    def stub_refresh_provider_health(db, config):
        del db
        config.health_status = AI_HEALTH_HEALTHY
        config.health_error = None
        config.available_model_count = 1
        config.capabilities = {"supports_structured_output": True}
        return AIProviderHealth(
            is_healthy=True,
            status=AI_HEALTH_HEALTHY,
            message=None,
            models=["gpt-5.4-mini"],
            capabilities={"supports_structured_output": True},
        )

    monkeypatch.setattr(
        "app.services.instance_integration_checks.refresh_provider_health",
        stub_refresh_provider_health,
    )
    monkeypatch.setattr(
        "app.services.instance_integration_checks.run_smtp_connectivity_test",
        lambda db: SMTPTestResult(status="passed", ok=True, message="250 OK"),
    )

    bootstrap_development_mode(db_session, mode=DEV_MODE_DEMO, off_client=NoOpenFoodFactsClient())

    ai_config = db_session.scalar(select(AIProviderConfig))
    assert ai_config is not None
    assert ai_config.provider_type == "openai"
    assert ai_config.base_url == "https://api.openai.com/v1"
    assert ai_config.default_model == "gpt-5.4-mini"
    assert ai_config.encrypted_api_key is not None
    assert ai_config.is_enabled is True
    assert ai_config.health_status == AI_HEALTH_HEALTHY

    smtp_settings = db_session.scalar(select(InstanceSetting))
    assert smtp_settings is not None
    assert smtp_settings.smtp_host == "smtp.example.com"
    assert smtp_settings.smtp_port == 587
    assert smtp_settings.smtp_username == "mailer"
    assert smtp_settings.smtp_from_email == "pantry@example.com"
    assert smtp_settings.smtp_test_recipient_email == "test@example.com"
    assert smtp_settings.password_reset_enabled is True
    assert smtp_settings.smtp_last_test_status == "passed"
