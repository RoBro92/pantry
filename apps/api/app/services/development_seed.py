from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.roles import HOUSEHOLD_ADMIN_ROLE, HOUSEHOLD_USER_ROLE
from app.services.ai_config import upsert_instance_provider_config
from app.models.household import Household
from app.models.product import Product
from app.models.user import User
from app.schemas.pantry import ConfirmedProductEnrichmentRequest
from app.services.auth import (
    create_household,
    create_membership,
    create_platform_admin,
    create_user,
)
from app.services.ai_config import upsert_instance_provider_config
from app.services.canonical_knowledge import bootstrap_default_canonical_items, relink_household_products_to_canonical_items
from app.services.e2e_seed import reset_application_data
from app.services.instance_integration_checks import (
    run_instance_ai_health_check,
    run_instance_smtp_health_check,
)
from app.services.instance_settings import get_or_create_instance_settings, upsert_smtp_settings
from app.services.local_ai_bootstrap import resolve_local_ai_bootstrap_config
from app.services.local_smtp_bootstrap import resolve_local_smtp_bootstrap_config
from app.services.open_food_facts import OPEN_FOOD_FACTS_SOURCE, OpenFoodFactsUnavailableError
from app.services.pantry_catalog import create_location, create_location_group, create_product
from app.services.pantry_stock import add_stock_lot
from app.services.product_enrichment import (
    ProductEnrichmentError,
    apply_confirmed_product_enrichment,
    get_default_open_food_facts_client,
)
from app.services.instance_settings import upsert_smtp_settings
from app.services.setup import mark_setup_completed

DEV_MODE_FRESH = "fresh"
DEV_MODE_DEMO = "demo"
DEV_MODE_CHOICES = (DEV_MODE_FRESH, DEV_MODE_DEMO)


@dataclass(frozen=True)
class DemoUserSeed:
    login: str
    password: str
    display_name: str
    is_platform_admin: bool
    household_role_code: str


@dataclass(frozen=True)
class DemoRoomSeed:
    name: str
    storage_locations: tuple[str, ...]


@dataclass(frozen=True)
class DemoProductSeed:
    name: str
    unit: str
    location_key: str
    quantity: str
    purchase_days_ago: int
    expiry_days_ahead: int
    barcode: str | None = None


@dataclass(frozen=True)
class DevelopmentSeedManifest:
    mode: str
    entry_path: str
    setup_complete: bool
    bootstrap_warnings: list[str]
    users: dict[str, dict[str, object]]
    household_external_id: str | None
    household_name: str | None
    room_external_ids: dict[str, str]
    location_external_ids: dict[str, str]
    product_external_ids: dict[str, str]
    enriched_product_names: list[str]

    def to_json(self) -> str:
        return json.dumps(
            {
                "mode": self.mode,
                "entry_path": self.entry_path,
                "setup_complete": self.setup_complete,
                "bootstrap_warnings": self.bootstrap_warnings,
                "users": self.users,
                "household_external_id": self.household_external_id,
                "household_name": self.household_name,
                "room_external_ids": self.room_external_ids,
                "location_external_ids": self.location_external_ids,
                "product_external_ids": self.product_external_ids,
                "enriched_product_names": self.enriched_product_names,
            },
            sort_keys=True,
        )


DEMO_USERS: tuple[DemoUserSeed, ...] = (
    DemoUserSeed(
        login="demoadmin",
        password="demopass",
        display_name="Demo Admin",
        is_platform_admin=True,
        household_role_code=HOUSEHOLD_ADMIN_ROLE,
    ),
    DemoUserSeed(
        login="demouser",
        password="demopass",
        display_name="Demo User",
        is_platform_admin=False,
        household_role_code=HOUSEHOLD_USER_ROLE,
    ),
)
DEMO_ROOMS: tuple[DemoRoomSeed, ...] = (
    DemoRoomSeed(name="Kitchen", storage_locations=("Fridge", "Freezer", "Cupboard")),
    DemoRoomSeed(name="Garage", storage_locations=("Fridge", "Freezer", "Shelf")),
)
DEMO_PRODUCTS: tuple[DemoProductSeed, ...] = (
    DemoProductSeed(
        name="Cheddar Cheese",
        unit="block",
        location_key="kitchen:fridge",
        quantity="1.000",
        purchase_days_ago=7,
        expiry_days_ahead=12,
        barcode="29060115",
    ),
    DemoProductSeed(
        name="Wraps",
        unit="pack",
        location_key="kitchen:fridge",
        quantity="1.000",
        purchase_days_ago=3,
        expiry_days_ahead=5,
        barcode="4056489983507",
    ),
    DemoProductSeed(
        name="Greek Yoghurt",
        unit="tub",
        location_key="kitchen:fridge",
        quantity="1.000",
        purchase_days_ago=4,
        expiry_days_ahead=3,
        barcode="5052320269839",
    ),
    DemoProductSeed(
        name="Chopped Tomatoes",
        unit="can",
        location_key="garage:shelf",
        quantity="4.000",
        purchase_days_ago=21,
        expiry_days_ahead=240,
        barcode="5031021164032",
    ),
    DemoProductSeed(
        name="Coconut Milk",
        unit="can",
        location_key="garage:shelf",
        quantity="2.000",
        purchase_days_ago=18,
        expiry_days_ahead=300,
        barcode="8997212610412",
    ),
    DemoProductSeed(
        name="Tuna",
        unit="can",
        location_key="garage:shelf",
        quantity="4.000",
        purchase_days_ago=35,
        expiry_days_ahead=210,
        barcode="5000171061522",
    ),
    DemoProductSeed(
        name="Baked Beans",
        unit="can",
        location_key="garage:shelf",
        quantity="3.000",
        purchase_days_ago=28,
        expiry_days_ahead=190,
        barcode="5000157024671",
    ),
    DemoProductSeed(
        name="Stock Cubes",
        unit="box",
        location_key="kitchen:cupboard",
        quantity="2.000",
        purchase_days_ago=40,
        expiry_days_ahead=365,
        barcode="5013665112273",
    ),
    DemoProductSeed(
        name="Mayonnaise",
        unit="jar",
        location_key="kitchen:fridge",
        quantity="1.000",
        purchase_days_ago=10,
        expiry_days_ahead=45,
        barcode="5000157076397",
    ),
    DemoProductSeed(
        name="Butter",
        unit="pack",
        location_key="garage:fridge",
        quantity="2.000",
        purchase_days_ago=12,
        expiry_days_ahead=25,
        barcode="5054775188239",
    ),
    DemoProductSeed(
        name="Pasta",
        unit="pack",
        location_key="garage:shelf",
        quantity="3.000",
        purchase_days_ago=16,
        expiry_days_ahead=280,
        barcode="8076800195057",
    ),
    DemoProductSeed(
        name="Rice",
        unit="bag",
        location_key="garage:shelf",
        quantity="2.000",
        purchase_days_ago=14,
        expiry_days_ahead=320,
        barcode="20142360",
    ),
    DemoProductSeed(
        name="Oats",
        unit="bag",
        location_key="garage:shelf",
        quantity="1.000",
        purchase_days_ago=9,
        expiry_days_ahead=180,
        barcode="5000108022152",
    ),
    DemoProductSeed(
        name="Tomato Puree",
        unit="tube",
        location_key="kitchen:cupboard",
        quantity="2.000",
        purchase_days_ago=22,
        expiry_days_ahead=120,
        barcode="5010061000098",
    ),
    DemoProductSeed(
        name="Sweetcorn",
        unit="can",
        location_key="garage:shelf",
        quantity="2.000",
        purchase_days_ago=24,
        expiry_days_ahead=200,
        barcode="5050179136500",
    ),
    DemoProductSeed(
        name="Kidney Beans",
        unit="can",
        location_key="garage:shelf",
        quantity="2.000",
        purchase_days_ago=23,
        expiry_days_ahead=220,
        barcode="5018374442215",
    ),
    DemoProductSeed(
        name="Chickpeas",
        unit="can",
        location_key="garage:shelf",
        quantity="3.000",
        purchase_days_ago=20,
        expiry_days_ahead=210,
        barcode="5051399182506",
    ),
    DemoProductSeed(
        name="Olive Oil",
        unit="bottle",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=30,
        expiry_days_ahead=360,
        barcode="6191509900671",
    ),
    DemoProductSeed(
        name="Soy Sauce",
        unit="bottle",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=26,
        expiry_days_ahead=300,
        barcode="8715035110106",
    ),
    DemoProductSeed(
        name="Milk",
        unit="bottle",
        location_key="kitchen:fridge",
        quantity="2.000",
        purchase_days_ago=2,
        expiry_days_ahead=2,
    ),
    DemoProductSeed(
        name="Cucumber",
        unit="count",
        location_key="kitchen:fridge",
        quantity="1.000",
        purchase_days_ago=3,
        expiry_days_ahead=4,
    ),
    DemoProductSeed(
        name="Chicken Thigh Fillets",
        unit="pack",
        location_key="kitchen:fridge",
        quantity="2.000",
        purchase_days_ago=1,
        expiry_days_ahead=2,
    ),
    DemoProductSeed(
        name="Onions",
        unit="count",
        location_key="kitchen:cupboard",
        quantity="6.000",
        purchase_days_ago=8,
        expiry_days_ahead=20,
    ),
    DemoProductSeed(
        name="Peppers",
        unit="count",
        location_key="kitchen:fridge",
        quantity="3.000",
        purchase_days_ago=4,
        expiry_days_ahead=6,
    ),
    DemoProductSeed(
        name="Carrots",
        unit="bag",
        location_key="kitchen:fridge",
        quantity="1.000",
        purchase_days_ago=6,
        expiry_days_ahead=10,
    ),
    DemoProductSeed(
        name="Mushrooms",
        unit="pack",
        location_key="kitchen:fridge",
        quantity="1.000",
        purchase_days_ago=2,
        expiry_days_ahead=2,
    ),
    DemoProductSeed(
        name="Spinach",
        unit="bag",
        location_key="kitchen:fridge",
        quantity="1.000",
        purchase_days_ago=2,
        expiry_days_ahead=1,
    ),
    DemoProductSeed(
        name="Potatoes",
        unit="bag",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=7,
        expiry_days_ahead=18,
    ),
    DemoProductSeed(
        name="Garlic",
        unit="bulb",
        location_key="kitchen:cupboard",
        quantity="2.000",
        purchase_days_ago=10,
        expiry_days_ahead=30,
    ),
    DemoProductSeed(
        name="Lemons",
        unit="count",
        location_key="kitchen:fridge",
        quantity="2.000",
        purchase_days_ago=5,
        expiry_days_ahead=8,
    ),
    DemoProductSeed(
        name="Eggs",
        unit="count",
        location_key="kitchen:fridge",
        quantity="12.000",
        purchase_days_ago=5,
        expiry_days_ahead=9,
    ),
    DemoProductSeed(
        name="White Bread",
        unit="loaf",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=2,
        expiry_days_ahead=2,
    ),
    DemoProductSeed(
        name="Brown Bread Rolls",
        unit="pack",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=1,
        expiry_days_ahead=2,
    ),
    DemoProductSeed(
        name="Bacon",
        unit="pack",
        location_key="garage:fridge",
        quantity="1.000",
        purchase_days_ago=4,
        expiry_days_ahead=5,
    ),
    DemoProductSeed(
        name="Ham",
        unit="pack",
        location_key="garage:fridge",
        quantity="1.000",
        purchase_days_ago=3,
        expiry_days_ahead=4,
    ),
    DemoProductSeed(
        name="Salt",
        unit="box",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=60,
        expiry_days_ahead=720,
    ),
    DemoProductSeed(
        name="Black Pepper",
        unit="jar",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=45,
        expiry_days_ahead=540,
    ),
    DemoProductSeed(
        name="Paprika",
        unit="jar",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=50,
        expiry_days_ahead=400,
    ),
    DemoProductSeed(
        name="Oregano",
        unit="jar",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=55,
        expiry_days_ahead=420,
    ),
    DemoProductSeed(
        name="Cumin",
        unit="jar",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=48,
        expiry_days_ahead=410,
    ),
    DemoProductSeed(
        name="Curry Powder",
        unit="jar",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=42,
        expiry_days_ahead=390,
    ),
    DemoProductSeed(
        name="Honey",
        unit="bottle",
        location_key="kitchen:cupboard",
        quantity="1.000",
        purchase_days_ago=35,
        expiry_days_ahead=540,
    ),
)


def bootstrap_development_mode(
    db: Session,
    *,
    mode: str,
    off_client=None,
) -> DevelopmentSeedManifest:
    if mode not in DEV_MODE_CHOICES:
        raise ValueError(f"Unsupported development mode {mode!r}. Choose one of: {', '.join(DEV_MODE_CHOICES)}.")

    if mode == DEV_MODE_FRESH:
        return reset_development_state(db)

    return seed_demo_development_state(db, off_client=off_client)


def reset_development_state(db: Session) -> DevelopmentSeedManifest:
    reset_application_data(db)
    return DevelopmentSeedManifest(
        mode=DEV_MODE_FRESH,
        entry_path="/setup",
        setup_complete=False,
        bootstrap_warnings=[],
        users={},
        household_external_id=None,
        household_name=None,
        room_external_ids={},
        location_external_ids={},
        product_external_ids={},
        enriched_product_names=[],
    )


def seed_demo_development_state(db: Session, *, off_client=None) -> DevelopmentSeedManifest:
    reset_application_data(db)

    actor = None
    created_users: dict[str, User] = {}
    for user_seed in DEMO_USERS:
        if user_seed.is_platform_admin:
            user = create_platform_admin(
                db,
                email=user_seed.login,
                password=user_seed.password,
                display_name=user_seed.display_name,
            )
        else:
            user = create_user(
                db,
                email=user_seed.login,
                password=user_seed.password,
                display_name=user_seed.display_name,
            )
        created_users[user_seed.login] = user
        if actor is None and user_seed.is_platform_admin:
            actor = user

    if actor is None:
        raise ValueError("Demo development seed requires at least one platform admin.")

    ai_bootstrap = resolve_local_ai_bootstrap_config()
    if ai_bootstrap is not None:
        config = upsert_instance_provider_config(
            db,
            actor=actor,
            provider_type=ai_bootstrap.provider_type,
            base_url=ai_bootstrap.base_url,
            default_model=ai_bootstrap.default_model,
            api_key=ai_bootstrap.api_key,
            is_enabled=True,
        )
        run_instance_ai_health_check(db, config=config)

    smtp_bootstrap = resolve_local_smtp_bootstrap_config()
    if smtp_bootstrap is not None:
        upsert_smtp_settings(
            db,
            actor=actor,
            host=smtp_bootstrap.host,
            port=smtp_bootstrap.port,
            username=smtp_bootstrap.username,
            password=smtp_bootstrap.password,
            from_email=smtp_bootstrap.from_email,
            from_name=smtp_bootstrap.from_name,
            test_recipient_email=smtp_bootstrap.test_recipient_email,
            security=smtp_bootstrap.security,
            is_enabled=smtp_bootstrap.is_enabled,
        )
        settings = get_or_create_instance_settings(db)
        settings.password_reset_enabled = smtp_bootstrap.password_reset_enabled
        db.add(settings)
        db.commit()
        run_instance_smtp_health_check(db, actor=actor)

    household = create_household(db, name="demohouse")
    bootstrap_default_canonical_items(db, household=household, actor=actor)
    for user_seed in DEMO_USERS:
        create_membership(
            db,
            user=created_users[user_seed.login],
            household=household,
            role_code=user_seed.household_role_code,
        )

    room_external_ids: dict[str, str] = {}
    location_external_ids: dict[str, str] = {}
    for room_seed in DEMO_ROOMS:
        group = create_location_group(db, household=household, actor=actor, name=room_seed.name)
        room_key = room_seed.name.casefold()
        room_external_ids[room_key] = group.external_id
        for location_name in room_seed.storage_locations:
            location = create_location(
                db,
                household=household,
                actor=actor,
                location_group_external_id=group.external_id,
                name=location_name,
            )
            location_external_ids[f"{room_key}:{location_name.casefold()}"] = location.external_id

    off_lookup_client = off_client or get_default_open_food_facts_client()
    product_external_ids: dict[str, str] = {}
    enriched_product_names: list[str] = []
    today = date.today()
    for product_seed in DEMO_PRODUCTS:
        product = create_product(
            db,
            household=household,
            actor=actor,
            name=product_seed.name,
            default_unit=product_seed.unit,
            aliases=[],
            barcodes=[product_seed.barcode] if product_seed.barcode else [],
            commit=False,
        )
        add_stock_lot(
            db,
            household=household,
            actor=actor,
            product_external_id=product.external_id,
            location_external_id=location_external_ids[product_seed.location_key],
            quantity=Decimal(product_seed.quantity),
            note="Seeded demo stock",
            purchased_on=today - timedelta(days=product_seed.purchase_days_ago),
            expires_on=today + timedelta(days=product_seed.expiry_days_ahead),
            unit_override=product_seed.unit,
            commit=False,
        )
        if product_seed.barcode and _try_attach_open_food_facts_enrichment(
            db,
            household=household,
            actor=actor,
            product=product,
            barcode=product_seed.barcode,
            off_client=off_lookup_client,
        ):
            enriched_product_names.append(product_seed.name)
        db.commit()
        db.refresh(product)
        product_external_ids[product_seed.name] = product.external_id

    relink_household_products_to_canonical_items(
        db,
        household=household,
        actor=actor,
    )
    db.commit()

    bootstrap_warnings: list[str] = []
    mark_setup_completed(db)

    return DevelopmentSeedManifest(
        mode=DEV_MODE_DEMO,
        entry_path="/login",
        setup_complete=True,
        bootstrap_warnings=bootstrap_warnings,
        users={
            user_seed.login: {
                "password": user_seed.password,
                "display_name": user_seed.display_name,
                "platform_admin": user_seed.is_platform_admin,
                "household_role": user_seed.household_role_code,
            }
            for user_seed in DEMO_USERS
        },
        household_external_id=household.external_id,
        household_name=household.name,
        room_external_ids=room_external_ids,
        location_external_ids=location_external_ids,
        product_external_ids=product_external_ids,
        enriched_product_names=enriched_product_names,
    )


def _try_attach_open_food_facts_enrichment(
    db: Session,
    *,
    household: Household,
    actor: User,
    product: Product,
    barcode: str,
    off_client,
) -> bool:
    try:
        candidate = off_client.lookup_by_barcode(barcode)
    except OpenFoodFactsUnavailableError:
        return False

    if candidate is None:
        return False

    try:
        apply_confirmed_product_enrichment(
            db,
            household=household,
            actor=actor,
            product=product,
            confirmed_enrichment=ConfirmedProductEnrichmentRequest(
                source_name=OPEN_FOOD_FACTS_SOURCE,
                source_product_id=candidate.source_product_id,
                match_status="barcode_exact",
            ),
            client=off_client,
        )
    except ProductEnrichmentError:
        return False

    return True
