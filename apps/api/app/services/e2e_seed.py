from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.roles import HOUSEHOLD_ADMIN_ROLE
from app.models import Base, Role
from app.services.auth import create_household, create_membership, create_platform_admin, create_user
from app.services.pantry_catalog import create_location, create_location_group, create_product
from app.services.pantry_stock import add_stock_lot

E2E_PASSWORD = "correct horse battery"
E2E_ADMIN_EMAIL = "e2e-admin@example.com"
E2E_MEMBER_EMAIL = "e2e-member@example.com"
E2E_HOUSEHOLD_NAME = "E2E Household"


@dataclass(frozen=True)
class E2ESeedManifest:
    admin_email: str
    member_email: str
    password: str
    household_external_id: str
    household_name: str
    primary_location_external_id: str
    primary_location_name: str
    pantry_group_external_id: str
    pantry_group_name: str
    product_external_ids: dict[str, str]

    def to_json(self) -> str:
        return json.dumps(
            {
                "admin_email": self.admin_email,
                "member_email": self.member_email,
                "password": self.password,
                "household_external_id": self.household_external_id,
                "household_name": self.household_name,
                "primary_location_external_id": self.primary_location_external_id,
                "primary_location_name": self.primary_location_name,
                "pantry_group_external_id": self.pantry_group_external_id,
                "pantry_group_name": self.pantry_group_name,
                "product_external_ids": self.product_external_ids,
            },
            sort_keys=True,
        )


def reset_application_data(db: Session) -> None:
    for table in reversed(Base.metadata.sorted_tables):
        if table.name == Role.__tablename__:
            continue
        db.execute(delete(table))
    db.commit()

    storage_root = Path(get_settings().import_storage_root)
    shutil.rmtree(storage_root, ignore_errors=True)
    storage_root.mkdir(parents=True, exist_ok=True)


def seed_e2e_baseline(db: Session) -> E2ESeedManifest:
    reset_application_data(db)

    admin = create_platform_admin(
        db,
        email=E2E_ADMIN_EMAIL,
        password=E2E_PASSWORD,
        display_name="E2E Admin",
    )
    member = create_user(
        db,
        email=E2E_MEMBER_EMAIL,
        password=E2E_PASSWORD,
        display_name="E2E Member",
    )
    household = create_household(db, name=E2E_HOUSEHOLD_NAME)
    create_membership(
        db,
        user=member,
        household=household,
        role_code=HOUSEHOLD_ADMIN_ROLE,
    )

    pantry_group = create_location_group(
        db,
        household=household,
        actor=member,
        name="Kitchen",
    )
    shelf_a = create_location(
        db,
        household=household,
        actor=member,
        location_group_external_id=pantry_group.external_id,
        name="Shelf A",
    )

    pasta = create_product(
        db,
        household=household,
        actor=member,
        name="Pasta",
        default_unit="count",
        aliases=["Dry pasta"],
        barcodes=["00123"],
    )
    tomatoes = create_product(
        db,
        household=household,
        actor=member,
        name="Tomatoes",
        default_unit="can",
        aliases=[],
        barcodes=[],
    )
    spice_blend = create_product(
        db,
        household=household,
        actor=member,
        name="Spice Blend",
        default_unit="jar",
        aliases=[],
        barcodes=[],
    )

    add_stock_lot(
        db,
        household=household,
        actor=member,
        product_external_id=pasta.external_id,
        location_external_id=shelf_a.external_id,
        quantity=Decimal("1.000"),
        note="Seeded baseline stock",
        purchased_on=None,
        expires_on=None,
    )

    return E2ESeedManifest(
        admin_email=admin.email,
        member_email=member.email,
        password=E2E_PASSWORD,
        household_external_id=household.external_id,
        household_name=household.name,
        primary_location_external_id=shelf_a.external_id,
        primary_location_name=shelf_a.name,
        pantry_group_external_id=pantry_group.external_id,
        pantry_group_name=pantry_group.name,
        product_external_ids={
            "pasta": pasta.external_id,
            "tomatoes": tomatoes.external_id,
            "spice_blend": spice_blend.external_id,
        },
    )
