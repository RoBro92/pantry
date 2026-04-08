from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.domain.roles import HOUSEHOLD_ADMIN_ROLE, HOUSEHOLD_USER_ROLE
from app.models.audit_event import AuditEvent
from app.models.product_enrichment import ProductEnrichment
from app.schemas.pantry import ProductEnrichmentAttribution, ProductEnrichmentCandidate, ProductNutritionSummaryItem
from app.models.stock_lot import StockLot
from app.services.auth import create_household, create_membership, create_user
from app.services.pantry_catalog import create_location as create_location_record
from app.services.pantry_catalog import create_location_group as create_location_group_record
from app.services.pantry_catalog import create_product as create_product_record
from app.services.pantry_stock import add_stock_lot as add_stock_lot_record


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
        purchased_on="2026-04-01",
        expires_on="2026-04-03",
        note="Family pack",
    )

    assert payload["status"] == "created"
    assert payload["product"]["name"] == "Beef mince"
    assert payload["product"]["default_unit"] == "kg"
    assert payload["lot"]["product_name"] == "Beef mince"
    assert payload["lot"]["location_name"] == "Shelf"
    assert payload["lot"]["note"] == "Family pack"


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
    assert reconciled_payload["pending_lists"][0]["purchased_item_count"] == 1
    assert reconciled_payload["pending_lists"][0]["items"][0]["status"] == "purchased"


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
    assert "[ ] Milk (1.000 bottle)" in first_export.text

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

    finalized = client.post(
        f"/api/households/{household.external_id}/shopping-list/pending/{pending_list['external_id']}/finalize",
        json={},
    )
    assert finalized.status_code == 200
    finalized_payload = finalized.json()
    assert len(finalized_payload["pending_lists"]) == 0
    assert finalized_payload["active_list"]["items"][0]["label"] == "Bread"
    assert finalized_payload["history_lists"][0]["lifecycle_state"] == "reconciled"


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
