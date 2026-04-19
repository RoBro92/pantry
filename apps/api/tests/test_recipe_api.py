from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.domain.roles import HOUSEHOLD_ADMIN_ROLE
from app.models.audit_event import AuditEvent
from app.models.recipe import Recipe
from app.models.recipe_url_import import RecipeURLImport
from app.services.auth import create_household, create_membership, create_user
from app.services.canonical_knowledge import ensure_canonical_item
from app.services.platform_features import FLAG_RECIPE_URL_IMPORTS, upsert_feature_flag
from app.services.recipe_url_imports import process_next_recipe_url_import


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


def test_recipe_create_detail_list_and_shopping_gap_use_deterministic_matching(client, db_session):
    _, household = create_member_household(
        db_session,
        email="recipes@example.com",
        household_name="Recipe Household",
    )
    login(client, email="recipes@example.com")

    pantry_group = create_location_group(client, household.external_id, "Pantry")
    shelf = create_location(client, household.external_id, pantry_group["external_id"], "Shelf")
    spaghetti = create_product(
        client,
        household.external_id,
        name="Spaghetti",
        default_unit="count",
        aliases=["Pasta"],
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
    basil = create_product(
        client,
        household.external_id,
        name="Basil",
        default_unit="bunch",
        aliases=["Fresh basil"],
        barcodes=[],
    )

    add_stock_lot(
        client,
        household.external_id,
        product_external_id=spaghetti["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.500",
    )
    add_stock_lot(
        client,
        household.external_id,
        product_external_id=tomatoes["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
    )

    create_response = client.post(
        f"/api/households/{household.external_id}/recipes",
        json={
            "title": "Weeknight Pasta",
            "notes": "Manual first pass.",
            "ingredients": [
                {"name": "Pasta", "quantity": "1.000", "unit": "count"},
                {
                    "name": "Spaghetti",
                    "quantity": "1.000",
                    "unit": "count",
                    "product_external_id": spaghetti["external_id"],
                },
                {
                    "name": "Tomatoes",
                    "quantity": "1.000",
                    "unit": "can",
                    "product_external_id": tomatoes["external_id"],
                },
                {
                    "name": "Fresh basil",
                    "quantity": "1.000",
                    "unit": "bunch",
                    "product_external_id": basil["external_id"],
                },
            ],
        },
    )
    assert create_response.status_code == 201
    recipe_payload = create_response.json()["recipe"]

    assert recipe_payload["pantry_coverage"]["status"] == "partially_covered"
    assert recipe_payload["pantry_coverage"]["fully_covered_count"] == 2
    assert recipe_payload["pantry_coverage"]["partially_covered_count"] == 1
    assert recipe_payload["pantry_coverage"]["missing_count"] == 1
    assert recipe_payload["ingredient_count"] == 4
    assert recipe_payload["ingredients"][0]["match_source"] == "automatic"
    assert recipe_payload["ingredients"][0]["coverage"]["status"] == "fully_covered"
    assert recipe_payload["ingredients"][1]["match_source"] == "manual"
    assert recipe_payload["ingredients"][1]["coverage"]["status"] == "partially_covered"
    assert Decimal(recipe_payload["ingredients"][1]["coverage"]["missing_quantity"]) == Decimal("0.500")
    assert recipe_payload["ingredients"][3]["coverage"]["status"] == "missing"

    gap_map = {item["label"]: Decimal(item["quantity"]) for item in recipe_payload["shopping_gap_items"]}
    assert gap_map == {
        "Spaghetti": Decimal("0.500"),
        "Basil": Decimal("1.000"),
    }

    recipe_external_id = recipe_payload["external_id"]

    list_response = client.get(f"/api/households/{household.external_id}/recipes")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload["recipes"]) == 1
    assert list_payload["recipes"][0]["external_id"] == recipe_external_id
    assert list_payload["recipes"][0]["pantry_coverage"]["status"] == "partially_covered"

    detail_response = client.get(f"/api/households/{household.external_id}/recipes/{recipe_external_id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["recipe"]
    assert detail_payload["title"] == "Weeknight Pasta"
    assert detail_payload["shopping_gap_items"] == recipe_payload["shopping_gap_items"]


def test_recipe_matching_falls_back_to_canonical_links_when_direct_lookup_misses(client, db_session):
    admin, household = create_member_household(
        db_session,
        email="recipe-canonical@example.com",
        household_name="Recipe Canonical Household",
    )
    login(client, email="recipe-canonical@example.com")

    ensure_canonical_item(
        db_session,
        household=household,
        actor=admin,
        name="Pasta",
        aliases=["Spaghetti"],
        barcodes=[],
        review_status="verified",
        source_name="test_seed",
        provenance_payload={"test": True},
    )
    db_session.commit()

    pantry_group = create_location_group(client, household.external_id, "Pantry")
    shelf = create_location(client, household.external_id, pantry_group["external_id"], "Shelf")
    pasta = create_product(
        client,
        household.external_id,
        name="Pasta",
        default_unit="pack",
        aliases=[],
        barcodes=[],
    )

    add_stock_lot(
        client,
        household.external_id,
        product_external_id=pasta["external_id"],
        location_external_id=shelf["external_id"],
        quantity="1.000",
    )

    create_response = client.post(
        f"/api/households/{household.external_id}/recipes",
        json={
            "title": "Simple Spaghetti",
            "notes": "Canonical fallback should link this ingredient.",
            "ingredients": [
                {"name": "Spaghetti", "quantity": "1.000", "unit": "pack"},
            ],
        },
    )
    assert create_response.status_code == 201
    recipe = create_response.json()["recipe"]

    assert recipe["ingredients"][0]["match_source"] == "automatic_canonical"
    assert recipe["ingredients"][0]["product"]["external_id"] == pasta["external_id"]
    assert recipe["ingredients"][0]["coverage"]["status"] == "fully_covered"


def test_recipe_update_replaces_ingredients_and_records_audit_events(client, db_session):
    _, household = create_member_household(
        db_session,
        email="recipe-update@example.com",
        household_name="Recipe Update Household",
    )
    login(client, email="recipe-update@example.com")

    pantry_group = create_location_group(client, household.external_id, "Pantry")
    shelf = create_location(client, household.external_id, pantry_group["external_id"], "Shelf")
    rice = create_product(
        client,
        household.external_id,
        name="Rice",
        default_unit="bag",
        aliases=[],
        barcodes=[],
    )
    beans = create_product(
        client,
        household.external_id,
        name="Beans",
        default_unit="can",
        aliases=[],
        barcodes=[],
    )

    add_stock_lot(
        client,
        household.external_id,
        product_external_id=rice["external_id"],
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

    created = client.post(
        f"/api/households/{household.external_id}/recipes",
        json={
            "title": "Beans and rice",
            "notes": None,
            "ingredients": [
                {"name": "Rice", "quantity": "2.000", "unit": "bag"},
                {"name": "Beans", "quantity": "1.000", "unit": "can"},
            ],
        },
    )
    assert created.status_code == 201
    recipe_external_id = created.json()["recipe"]["external_id"]

    updated = client.put(
        f"/api/households/{household.external_id}/recipes/{recipe_external_id}",
        json={
            "title": "Beans and rice bowls",
            "notes": "Use what is already in the pantry.",
            "ingredients": [
                {"name": "Rice", "quantity": "1.000", "unit": "bag"},
                {"name": "Beans", "quantity": "1.000", "unit": "can"},
            ],
        },
    )
    assert updated.status_code == 200
    updated_payload = updated.json()["recipe"]
    assert updated_payload["title"] == "Beans and rice bowls"
    assert updated_payload["ingredient_count"] == 2
    assert updated_payload["pantry_coverage"]["status"] == "fully_covered"
    assert {ingredient["name"] for ingredient in updated_payload["ingredients"]} == {"Rice", "Beans"}

    events = db_session.scalars(
        select(AuditEvent)
        .where(AuditEvent.target_external_id == recipe_external_id)
        .order_by(AuditEvent.occurred_at.asc())
    ).all()
    assert [event.action for event in events] == ["recipe.created", "recipe.updated"]


def test_recipe_url_import_queues_background_processing(client, db_session, monkeypatch):
    _, household = create_member_household(
        db_session,
        email="recipe-import@example.com",
        household_name="Recipe Import Household",
    )
    login(client, email="recipe-import@example.com")

    response = client.post(
        f"/api/households/{household.external_id}/recipe-imports/url",
        json={"url": "https://Example.com/recipes/pasta?ref=weekly#hero"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["normalized_url"] == "https://example.com/recipes/pasta?ref=weekly"
    assert payload["note"] == "Queued for background recipe import."

    stored = db_session.scalar(select(RecipeURLImport).where(RecipeURLImport.external_id == payload["external_id"]))
    assert stored is not None
    assert stored.normalized_url == "https://example.com/recipes/pasta?ref=weekly"

    monkeypatch.setattr(
        "app.services.recipe_url_imports._fetch_recipe_html",
        lambda url: """
        <html>
          <head><title>Example Pasta</title></head>
          <body>
            <script type=\"application/ld+json\">
              {
                "@context": "https://schema.org",
                "@type": "Recipe",
                "name": "Example Pasta",
                "recipeIngredient": [
                  "1 count Pasta",
                  "2 can Tomatoes"
                ]
              }
            </script>
          </body>
        </html>
        """,
    )

    assert process_next_recipe_url_import() is True

    db_session.expire_all()
    refreshed = db_session.scalar(select(RecipeURLImport).where(RecipeURLImport.external_id == payload["external_id"]))
    assert refreshed is not None
    assert refreshed.status == "imported"
    assert refreshed.recipe_id is not None

    recipe = db_session.scalar(select(Recipe).where(Recipe.id == refreshed.recipe_id))
    assert recipe is not None
    assert recipe.title == "Example Pasta"
    assert recipe.source_kind == "url_import"
    assert recipe.source_url == "https://example.com/recipes/pasta?ref=weekly"

    audit_event = db_session.scalar(
        select(AuditEvent).where(AuditEvent.target_external_id == payload["external_id"])
    )
    assert audit_event is not None
    assert audit_event.action == "recipe.url_import.requested"

    completed_event = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.target_external_id == payload["external_id"])
        .where(AuditEvent.action == "recipe.url_import.completed")
    )
    assert completed_event is not None


def test_recipe_endpoints_enforce_household_scoping(client, db_session):
    _, allowed_household = create_member_household(
        db_session,
        email="recipe-scope@example.com",
        household_name="Allowed Recipes",
    )
    denied_household = create_household(db_session, name="Denied Recipes")
    login(client, email="recipe-scope@example.com")

    allowed = client.get(f"/api/households/{allowed_household.external_id}/recipes")
    denied = client.get(f"/api/households/{denied_household.external_id}/recipes")

    assert allowed.status_code == 200
    assert denied.status_code == 404


def test_recipe_url_import_can_be_disabled_by_feature_flag(client, db_session):
    _, household = create_member_household(
        db_session,
        email="recipe-flag@example.com",
        household_name="Recipe Flag Household",
    )
    upsert_feature_flag(
        db_session,
        flag_key=FLAG_RECIPE_URL_IMPORTS,
        scope_type="household",
        scope_key=household.external_id,
        is_enabled=False,
        note="Temporarily disabled.",
    )
    login(client, email="recipe-flag@example.com")

    response = client.post(
        f"/api/households/{household.external_id}/recipe-imports/url",
        json={"url": "https://example.com/recipes/pasta"},
    )
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"].lower()
