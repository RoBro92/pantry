from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

from app.core.db import SessionLocal
from app.domain.roles import HOUSEHOLD_ADMIN_ROLE
from app.models.import_job import ImportJob
from app.models.import_line import ImportLine
from app.models.stock_lot import StockLot
from app.services.auth import create_household, create_membership, create_user
from app.services.import_workflow import confirm_import_job, get_import_job_by_external_id, refresh_import_job_counts
from app.services.pantry_catalog import create_location, create_location_group, create_product
from app.services.pantry_normalization import normalize_lookup_name
from app.services.pantry_stock import (
    add_stock_lot,
    get_stock_lot_by_external_id,
    move_stock_lot,
    remove_stock_from_lot,
    update_stock_lot,
)


PASSWORD = "correct horse battery"


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
