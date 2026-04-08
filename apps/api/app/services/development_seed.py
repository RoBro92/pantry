from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.roles import HOUSEHOLD_ADMIN_ROLE, HOUSEHOLD_USER_ROLE
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
from app.services.e2e_seed import reset_application_data
from app.services.open_food_facts import OPEN_FOOD_FACTS_SOURCE, OpenFoodFactsUnavailableError
from app.services.pantry_catalog import create_location, create_location_group, create_product
from app.services.pantry_stock import add_stock_lot
from app.services.product_enrichment import (
    ProductEnrichmentError,
    apply_confirmed_product_enrichment,
    get_default_open_food_facts_client,
)
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
    barcode: str
    unit: str
    location_key: str
    purchase_days_ago: int
    expiry_days_ahead: int


@dataclass(frozen=True)
class DevelopmentSeedManifest:
    mode: str
    entry_path: str
    setup_complete: bool
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
        login="robin",
        password="weymouth",
        display_name="Robin",
        is_platform_admin=True,
        household_role_code=HOUSEHOLD_ADMIN_ROLE,
    ),
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
    DemoRoomSeed(name="Kitchen", storage_locations=("Fridge", "Freezer")),
    DemoRoomSeed(name="Garage", storage_locations=("Fridge", "Freezer")),
)
DEMO_PRODUCTS: tuple[DemoProductSeed, ...] = (
    DemoProductSeed(
        name="Golden Syrup",
        barcode="5010115900596",
        unit="bottle",
        location_key="kitchen:fridge",
        purchase_days_ago=6,
        expiry_days_ahead=120,
    ),
    DemoProductSeed(
        name="Huel Chocolate",
        barcode="5060495113291",
        unit="bottle",
        location_key="kitchen:freezer",
        purchase_days_ago=3,
        expiry_days_ahead=45,
    ),
    DemoProductSeed(
        name="Brown Sauce",
        barcode="5060092696456",
        unit="bottle",
        location_key="garage:fridge",
        purchase_days_ago=12,
        expiry_days_ahead=180,
    ),
    DemoProductSeed(
        name="Sweet Chilli Jam",
        barcode="6003770009178",
        unit="bottle",
        location_key="garage:freezer",
        purchase_days_ago=8,
        expiry_days_ahead=90,
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

    household = create_household(db, name="demohouse")
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
            barcodes=[product_seed.barcode],
            commit=False,
        )
        add_stock_lot(
            db,
            household=household,
            actor=actor,
            product_external_id=product.external_id,
            location_external_id=location_external_ids[product_seed.location_key],
            quantity=Decimal("1.000"),
            note="Seeded demo stock",
            purchased_on=today - timedelta(days=product_seed.purchase_days_ago),
            expires_on=today + timedelta(days=product_seed.expiry_days_ahead),
            unit_override=product_seed.unit,
            commit=False,
        )
        if _try_attach_open_food_facts_enrichment(
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

    mark_setup_completed(db)

    return DevelopmentSeedManifest(
        mode=DEV_MODE_DEMO,
        entry_path="/login",
        setup_complete=True,
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
