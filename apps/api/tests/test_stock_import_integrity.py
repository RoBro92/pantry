from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.db import SessionLocal
from app.domain.roles import HOUSEHOLD_ADMIN_ROLE
from app.models import Base
from app.models.import_job import ImportJob
from app.models.import_line import ImportLine
from app.models.shopping_list_item import ShoppingListItem
from app.models.stock_lot import StockLot
from app.services.auth import create_household, create_membership, create_user
from app.services.import_workflow import confirm_import_job, get_import_job_by_external_id, refresh_import_job_counts
from app.services.pantry_catalog import create_location, create_location_group, create_product
from app.services.pantry_normalization import normalize_lookup_name
from app.services.pantry_stock import (
    add_stock_lot,
    buy_more_from_stock_lot,
    get_stock_lot_by_external_id,
    move_stock_lot,
    remove_stock_from_lot,
    update_stock_lot,
)


PASSWORD = "correct horse battery"
POSTGRES_URL_ENV = "PANTRY_TEST_POSTGRES_URL"


class CapturingSession:
    def __init__(self) -> None:
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        return None


def _compile_postgresql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect())).upper()


def _create_stock_fixture(db_session, *, email: str = "integrity@example.com"):
    actor = create_user(db_session, email=email, password=PASSWORD, display_name="Integrity")
    household = create_household(db_session, name="Stock Integrity Household")
    create_membership(db_session, user=actor, household=household, role_code=HOUSEHOLD_ADMIN_ROLE)
    group = create_location_group(db_session, household=household, actor=actor, name="Pantry")
    shelf = create_location(
        db_session,
        household=household,
        actor=actor,
        location_group_external_id=group.external_id,
        name="Shelf",
    )
    drawer = create_location(
        db_session,
        household=household,
        actor=actor,
        location_group_external_id=group.external_id,
        name="Drawer",
    )
    freezer = create_location(
        db_session,
        household=household,
        actor=actor,
        location_group_external_id=group.external_id,
        name="Freezer",
    )
    product = create_product(
        db_session,
        household=household,
        actor=actor,
        name="Olive Oil",
        default_unit="bottle",
        aliases=[],
        barcodes=[],
    )
    lot = add_stock_lot(
        db_session,
        household=household,
        actor=actor,
        product_external_id=product.external_id,
        location_external_id=shelf.external_id,
        quantity=Decimal("5.000"),
        note=None,
        purchased_on=None,
        expires_on=None,
    )
    return actor, household, shelf, drawer, freezer, product, lot


def _load_household_actor(db, household_id, actor_id):
    from app.models.household import Household
    from app.models.user import User

    household = db.get(Household, household_id)
    actor = db.get(User, actor_id)
    assert household is not None
    assert actor is not None
    return household, actor


@pytest.fixture
def postgres_session_factory():
    postgres_url = os.environ.get(POSTGRES_URL_ENV)
    if not postgres_url:
        pytest.skip(f"Set {POSTGRES_URL_ENV} to run live PostgreSQL stock contention tests.")

    parsed_url = make_url(postgres_url)
    if not parsed_url.drivername.startswith("postgresql"):
        pytest.skip(f"{POSTGRES_URL_ENV} must use a PostgreSQL SQLAlchemy URL.")

    schema = f"stock_integrity_{uuid4().hex}"
    admin_engine = create_engine(postgres_url, future=True, pool_pre_ping=True)
    schema_engine = None
    schema_created = False
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_created = True

        schema_engine = create_engine(
            postgres_url,
            future=True,
            pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        Base.metadata.create_all(bind=schema_engine)
        yield sessionmaker(bind=schema_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    finally:
        if schema_engine is not None:
            schema_engine.dispose()
        if schema_created:
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.mark.parametrize(
    "operation",
    [
        lambda db, household, actor: remove_stock_from_lot(
            db,
            household=household,
            actor=actor,
            lot_external_id="lot_missing",
            quantity=Decimal("1.000"),
        ),
        lambda db, household, actor: move_stock_lot(
            db,
            household=household,
            actor=actor,
            lot_external_id="lot_missing",
            quantity=Decimal("1.000"),
            destination_location_external_id="loc_missing",
        ),
        lambda db, household, actor: update_stock_lot(
            db,
            household=household,
            actor=actor,
            lot_external_id="lot_missing",
            quantity=Decimal("1.000"),
            location_external_id="loc_missing",
            note=None,
            purchased_on=None,
            expires_on=None,
        ),
    ],
)
def test_stock_mutations_lock_the_stock_lot_row_for_postgresql(operation):
    db = CapturingSession()

    with pytest.raises(ValueError, match="Stock lot not found"):
        operation(db, household=type("HouseholdStub", (), {"id": "household-id"})(), actor=None)

    assert db.statements
    assert "FOR UPDATE" in _compile_postgresql(db.statements[0])


def test_import_confirmation_locks_the_import_job_row_for_postgresql():
    db = CapturingSession()

    with pytest.raises(ValueError, match="Import job not found"):
        confirm_import_job(
            db,
            household=type("HouseholdStub", (), {"id": "household-id"})(),
            actor=None,
            import_external_id="imp_missing",
            location_external_id="loc_missing",
            purchased_on=None,
        )

    assert db.statements
    assert "FOR UPDATE" in _compile_postgresql(db.statements[0])


def test_repeated_stock_decrement_uses_current_quantity_before_applying(db_session):
    actor, household, _, _, _, _, lot = _create_stock_fixture(db_session)

    stale_session = SessionLocal()
    fresh_session = SessionLocal()
    try:
        stale_household, stale_actor = _load_household_actor(stale_session, household.id, actor.id)
        assert get_stock_lot_by_external_id(
            stale_session,
            household=stale_household,
            external_id=lot.external_id,
        ).quantity == Decimal("5.000")
        stale_session.commit()

        fresh_household, fresh_actor = _load_household_actor(fresh_session, household.id, actor.id)
        remove_stock_from_lot(
            fresh_session,
            household=fresh_household,
            actor=fresh_actor,
            lot_external_id=lot.external_id,
            quantity=Decimal("4.000"),
        )

        with pytest.raises(ValueError, match="Cannot remove more stock"):
            remove_stock_from_lot(
                stale_session,
                household=stale_household,
                actor=stale_actor,
                lot_external_id=lot.external_id,
                quantity=Decimal("4.000"),
            )

        db_session.expire_all()
        stored_quantity = db_session.scalar(select(StockLot.quantity).where(StockLot.id == lot.id))
        assert stored_quantity == Decimal("1.000")
    finally:
        stale_session.close()
        fresh_session.close()


def test_repeated_stock_move_uses_current_source_quantity_before_splitting(db_session):
    actor, household, _, drawer, freezer, _, lot = _create_stock_fixture(
        db_session,
        email="integrity-move@example.com",
    )

    stale_session = SessionLocal()
    fresh_session = SessionLocal()
    try:
        stale_household, stale_actor = _load_household_actor(stale_session, household.id, actor.id)
        assert get_stock_lot_by_external_id(
            stale_session,
            household=stale_household,
            external_id=lot.external_id,
        ).quantity == Decimal("5.000")
        stale_session.commit()

        fresh_household, fresh_actor = _load_household_actor(fresh_session, household.id, actor.id)
        move_stock_lot(
            fresh_session,
            household=fresh_household,
            actor=fresh_actor,
            lot_external_id=lot.external_id,
            quantity=Decimal("4.000"),
            destination_location_external_id=drawer.external_id,
        )

        with pytest.raises(ValueError, match="Cannot move more stock"):
            move_stock_lot(
                stale_session,
                household=stale_household,
                actor=stale_actor,
                lot_external_id=lot.external_id,
                quantity=Decimal("4.000"),
                destination_location_external_id=freezer.external_id,
            )

        db_session.expire_all()
        total_quantity = db_session.scalar(
            select(func.coalesce(func.sum(StockLot.quantity), Decimal("0.000"))).where(
                StockLot.household_id == household.id
            )
        )
        assert total_quantity == Decimal("5.000")
    finally:
        stale_session.close()
        fresh_session.close()


def test_repeated_stock_update_cannot_resurrect_a_depleted_stale_lot(db_session):
    actor, household, _, drawer, _, _, lot = _create_stock_fixture(
        db_session,
        email="integrity-update@example.com",
    )

    stale_session = SessionLocal()
    fresh_session = SessionLocal()
    try:
        stale_household, stale_actor = _load_household_actor(stale_session, household.id, actor.id)
        assert get_stock_lot_by_external_id(
            stale_session,
            household=stale_household,
            external_id=lot.external_id,
        ).depleted_at is None
        stale_session.commit()

        fresh_household, fresh_actor = _load_household_actor(fresh_session, household.id, actor.id)
        remove_stock_from_lot(
            fresh_session,
            household=fresh_household,
            actor=fresh_actor,
            lot_external_id=lot.external_id,
            quantity=Decimal("5.000"),
        )

        with pytest.raises(ValueError, match="Stock lot not found"):
            update_stock_lot(
                stale_session,
                household=stale_household,
                actor=stale_actor,
                lot_external_id=lot.external_id,
                quantity=Decimal("3.000"),
                location_external_id=drawer.external_id,
                note=None,
                purchased_on=None,
                expires_on=None,
            )

        db_session.expire_all()
        stored_lot = db_session.get(StockLot, lot.id)
        assert stored_lot is not None
        assert stored_lot.quantity == Decimal("0.000")
        assert stored_lot.depleted_at is not None
    finally:
        stale_session.close()
        fresh_session.close()


def test_repeated_import_confirmation_returns_existing_confirmation_without_adding_stock(db_session):
    actor, household, shelf, _, _, product, _ = _create_stock_fixture(
        db_session,
        email="integrity-import@example.com",
    )
    db_session.execute(select(StockLot))
    for lot in db_session.scalars(select(StockLot).where(StockLot.household_id == household.id)).all():
        db_session.delete(lot)
    db_session.commit()

    import_job = ImportJob(
        household_id=household.id,
        requested_by_user_id=actor.id,
        source_type="structured_import",
        status="needs_review",
        source_label="repeat-import.json",
    )
    db_session.add(import_job)
    db_session.flush()
    line = ImportLine(
        household_id=household.id,
        import_job_id=import_job.id,
        product_id=product.id,
        suggested_product_id=product.id,
        position=1,
        raw_label=product.name,
        normalized_label=normalize_lookup_name(product.name),
        quantity=Decimal("2.000"),
        unit=product.default_unit,
        status="matched",
        match_basis="manual",
    )
    db_session.add(line)
    db_session.flush()
    import_job.lines = [line]
    refresh_import_job_counts(import_job)
    db_session.commit()

    stale_session = SessionLocal()
    fresh_session = SessionLocal()
    try:
        stale_household, stale_actor = _load_household_actor(stale_session, household.id, actor.id)
        assert (
            get_import_job_by_external_id(
                stale_session,
                household=stale_household,
                import_external_id=import_job.external_id,
            ).status
            == "needs_review"
        )
        stale_session.commit()

        fresh_household, fresh_actor = _load_household_actor(fresh_session, household.id, actor.id)
        confirm_import_job(
            fresh_session,
            household=fresh_household,
            actor=fresh_actor,
            import_external_id=import_job.external_id,
            location_external_id=shelf.external_id,
            purchased_on=None,
        )

        repeated = confirm_import_job(
            stale_session,
            household=stale_household,
            actor=stale_actor,
            import_external_id=import_job.external_id,
            location_external_id=shelf.external_id,
            purchased_on=None,
        )
        assert repeated.status == "confirmed"

        db_session.expire_all()
        stored_lots = db_session.scalars(select(StockLot).where(StockLot.household_id == household.id)).all()
        assert len(stored_lots) == 1
        assert stored_lots[0].quantity == Decimal("2.000")

        confirmed_line = db_session.get(ImportLine, line.id)
        assert confirmed_line is not None
        assert confirmed_line.confirmed_stock_lot_id == stored_lots[0].id
    finally:
        stale_session.close()
        fresh_session.close()


def test_postgresql_concurrent_add_stock_merges_into_one_active_lot(postgres_session_factory):
    # Invariant: concurrent inserts with the same merge key cannot create duplicate active lots.
    with postgres_session_factory() as db:
        actor, household, shelf, _, _, product, _ = _create_stock_fixture(
            db,
            email=f"pg-add-{uuid4().hex[:8]}@example.com",
        )
        for lot in db.scalars(select(StockLot).where(StockLot.household_id == household.id)).all():
            db.delete(lot)
        db.commit()
        household_id = household.id
        actor_id = actor.id
        product_external_id = product.external_id
        shelf_external_id = shelf.external_id

    def add_once(quantity: str) -> None:
        with postgres_session_factory() as db:
            household, actor = _load_household_actor(db, household_id, actor_id)
            add_stock_lot(
                db,
                household=household,
                actor=actor,
                product_external_id=product_external_id,
                location_external_id=shelf_external_id,
                quantity=Decimal(quantity),
                note=None,
                purchased_on=None,
                expires_on=None,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(add_once, quantity) for quantity in ("2.000", "3.000")]
        for future in futures:
            future.result(timeout=10)

    with postgres_session_factory() as db:
        lots = db.scalars(
            select(StockLot)
            .where(StockLot.household_id == household_id)
            .where(StockLot.depleted_at.is_(None))
        ).all()
        assert len(lots) == 1
        assert lots[0].quantity == Decimal("5.000")


def test_postgresql_buy_more_and_depletion_commit_atomically(postgres_session_factory):
    # Invariant: a buy-more shopping item is not committed unless the paired depletion commits too.
    with postgres_session_factory() as db:
        actor, household, _, _, _, _, lot = _create_stock_fixture(
            db,
            email=f"pg-buy-more-{uuid4().hex[:8]}@example.com",
        )
        household_id = household.id
        actor_id = actor.id
        lot_external_id = lot.external_id

    def buy_more() -> str:
        with postgres_session_factory() as db:
            household, actor = _load_household_actor(db, household_id, actor_id)
            try:
                buy_more_from_stock_lot(
                    db,
                    household=household,
                    actor=actor,
                    lot_external_id=lot_external_id,
                )
                return "buy_more"
            except ValueError as exc:
                db.rollback()
                return str(exc)

    def deplete() -> str:
        with postgres_session_factory() as db:
            household, actor = _load_household_actor(db, household_id, actor_id)
            try:
                remove_stock_from_lot(
                    db,
                    household=household,
                    actor=actor,
                    lot_external_id=lot_external_id,
                    quantity=Decimal("5.000"),
                )
                return "deplete"
            except ValueError as exc:
                db.rollback()
                return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [future.result(timeout=10) for future in (executor.submit(buy_more), executor.submit(deplete))]

    assert outcomes.count("buy_more") + outcomes.count("deplete") == 1
    assert any("Stock lot not found" in outcome for outcome in outcomes)

    with postgres_session_factory() as db:
        lot = db.scalar(select(StockLot).where(StockLot.external_id == lot_external_id))
        assert lot is not None
        assert lot.quantity == Decimal("0.000")
        assert lot.depleted_at is not None
        shopping_items = db.scalars(
            select(ShoppingListItem).where(ShoppingListItem.household_id == household_id)
        ).all()
        assert len(shopping_items) == (1 if "buy_more" in outcomes else 0)
