from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.domain.roles import HOUSEHOLD_ADMIN_ROLE, HOUSEHOLD_USER_ROLE
from app.models.audit_event import AuditEvent
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
    assert second.json()["detail"] == "A product with the same name or alias already exists."


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

    stored_lot = db_session.scalar(select(StockLot).where(StockLot.external_id == lot["external_id"]))
    assert stored_lot is not None
    assert stored_lot.depleted_at is not None


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
