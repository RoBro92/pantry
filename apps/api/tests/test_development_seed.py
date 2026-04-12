from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.household import Household
from app.models.location import Location
from app.models.location_group import LocationGroup
from app.models.membership import Membership
from app.models.product import Product
from app.models.product_enrichment import ProductEnrichment
from app.models.setup_state import SetupState
from app.models.stock_lot import StockLot
from app.models.user import User
from app.services.auth import authenticate_user
from app.services.development_seed import (
    DEV_MODE_DEMO,
    DEV_MODE_FRESH,
    bootstrap_development_mode,
)
from app.services.open_food_facts import OpenFoodFactsUnavailableError
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


def test_demo_development_mode_ignores_open_food_facts_failures(db_session):
    manifest = bootstrap_development_mode(
        db_session,
        mode=DEV_MODE_DEMO,
        off_client=UnavailableOpenFoodFactsClient(),
    )

    assert manifest.enriched_product_names == []
    assert is_setup_complete(db_session) is True
    assert db_session.scalars(select(ProductEnrichment)).all() == []
