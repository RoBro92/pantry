from __future__ import annotations

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
        ("Kitchen", "Freezer"),
        ("Kitchen", "Fridge"),
    ]

    products = db_session.scalars(
        select(Product).options(selectinload(Product.barcodes)).order_by(Product.name)
    ).all()
    assert [product.name for product in products] == [
        "Brown Sauce",
        "Golden Syrup",
        "Huel Chocolate",
        "Sweet Chilli Jam",
    ]
    assert {
        product.name: [barcode.value for barcode in product.barcodes]
        for product in products
    } == {
        "Brown Sauce": ["5060092696456"],
        "Golden Syrup": ["5010115900596"],
        "Huel Chocolate": ["5060495113291"],
        "Sweet Chilli Jam": ["6003770009178"],
    }

    stock_lots = db_session.scalars(select(StockLot)).all()
    assert len(stock_lots) == 4

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
