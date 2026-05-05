from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.base import utc_now
from app.models.household import Household
from app.models.import_job import ImportJob
from app.models.product_intelligence_run import ProductIntelligenceRun
from app.models.recipe_url_import import RecipeURLImport
from app.services.import_processing import _claim_next_import_job
from app.services.product_intelligence_runs import _claim_next_product_intelligence_run
from app.services.recipe_url_imports import _claim_next_recipe_url_import

POSTGRES_URL_ENV = "PANTRY_TEST_POSTGRES_URL"


class CapturingSession:
    def __init__(self) -> None:
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        return None


def _compile_postgresql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect())).upper()


@pytest.mark.parametrize(
    ("claim_func", "expected_statement_count"),
    [
        (_claim_next_import_job, 1),
        (_claim_next_recipe_url_import, 1),
        (_claim_next_product_intelligence_run, 2),
    ],
)
def test_queue_claims_compile_with_postgresql_skip_locked(claim_func, expected_statement_count):
    # Invariant: every DB-backed queue claim skips rows already locked by another worker.
    db = CapturingSession()

    claim_func(db)

    assert len(db.statements) == expected_statement_count
    for statement in db.statements:
        assert "FOR UPDATE SKIP LOCKED" in _compile_postgresql(statement)


@pytest.fixture
def postgres_session_factory():
    postgres_url = os.environ.get(POSTGRES_URL_ENV)
    if not postgres_url:
        pytest.skip(f"Set {POSTGRES_URL_ENV} to run live PostgreSQL queue contention tests.")

    parsed_url = make_url(postgres_url)
    if not parsed_url.drivername.startswith("postgresql"):
        pytest.skip(f"{POSTGRES_URL_ENV} must use a PostgreSQL SQLAlchemy URL.")

    schema = f"queue_concurrency_{uuid4().hex}"
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


def _create_household(db, *, name: str = "Queue Concurrency Household") -> Household:
    household = Household(name=f"{name} {uuid4().hex[:8]}")
    db.add(household)
    db.flush()
    return household


def _seed_import_jobs(session_factory, *, count: int) -> list:
    with session_factory() as db:
        household = _create_household(db)
        base_created_at = utc_now() - timedelta(minutes=10)
        jobs = []
        for index in range(count):
            job = ImportJob(
                household_id=household.id,
                source_type="structured_import",
                source_label=f"queue-{index}.json",
                status="queued",
                created_at=base_created_at + timedelta(seconds=index),
            )
            db.add(job)
            jobs.append(job)
        db.commit()
        return [job.id for job in jobs]


def _claim_import_job_after_barrier(session_factory, barrier: threading.Barrier):
    with session_factory() as db:
        barrier.wait(timeout=10)
        claimed = _claim_next_import_job(db)
        return claimed.id if claimed is not None else None


def test_postgresql_import_claims_are_unique_under_multi_worker_contention(postgres_session_factory):
    # Invariant: concurrent workers claim each queued import job at most once.
    job_ids = _seed_import_jobs(postgres_session_factory, count=4)
    barrier = threading.Barrier(4)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(_claim_import_job_after_barrier, postgres_session_factory, barrier) for _ in job_ids
        ]
        claimed_ids = [future.result(timeout=10) for future in futures]

    assert set(claimed_ids) == set(job_ids)
    assert len(claimed_ids) == len(set(claimed_ids))

    with postgres_session_factory() as db:
        rows = db.scalars(select(ImportJob).where(ImportJob.id.in_(job_ids))).all()
        assert {row.status for row in rows} == {"processing"}
        assert all(row.processing_started_at is not None for row in rows)


def test_postgresql_import_claim_skips_locked_candidate_and_claims_next_job(postgres_session_factory):
    # Invariant: a worker holding the oldest row lock cannot make another worker double-claim or block.
    first_job_id, second_job_id = _seed_import_jobs(postgres_session_factory, count=2)
    locker = postgres_session_factory()
    contender = postgres_session_factory()
    try:
        locked_job = locker.scalar(select(ImportJob).where(ImportJob.id == first_job_id).with_for_update())
        assert locked_job is not None

        contender.execute(text("SET lock_timeout TO '500ms'"))
        claimed = _claim_next_import_job(contender)

        assert claimed is not None
        assert claimed.id == second_job_id
        assert locked_job.status == "queued"
    finally:
        locker.rollback()
        locker.close()
        contender.close()

    with postgres_session_factory() as db:
        claimed_after_release = _claim_next_import_job(db)

    assert claimed_after_release is not None
    assert claimed_after_release.id == first_job_id


def test_postgresql_stale_import_processing_job_is_reclaimed_once(postgres_session_factory):
    # Invariant: stale processing import jobs are reclaimable, but fresh processing jobs are not.
    with postgres_session_factory() as db:
        household = _create_household(db)
        stale_started_at = utc_now() - timedelta(hours=1)
        fresh_started_at = utc_now()
        stale_job = ImportJob(
            household_id=household.id,
            source_type="structured_import",
            source_label="stale.json",
            status="processing",
            processing_started_at=stale_started_at,
            failure_message="Worker disappeared.",
            created_at=utc_now() - timedelta(minutes=20),
        )
        fresh_job = ImportJob(
            household_id=household.id,
            source_type="structured_import",
            source_label="fresh.json",
            status="processing",
            processing_started_at=fresh_started_at,
            created_at=utc_now() - timedelta(minutes=10),
        )
        db.add_all([stale_job, fresh_job])
        db.commit()
        stale_job_id = stale_job.id
        fresh_job_id = fresh_job.id

    with postgres_session_factory() as db:
        claimed = _claim_next_import_job(db)
        second_claim = _claim_next_import_job(db)

    assert claimed is not None
    assert claimed.id == stale_job_id
    assert claimed.failure_message is None
    assert claimed.processing_started_at is not None
    assert claimed.processing_started_at > stale_started_at
    assert second_claim is None

    with postgres_session_factory() as db:
        fresh_job = db.get(ImportJob, fresh_job_id)
        assert fresh_job is not None
        assert fresh_job.status == "processing"
        assert fresh_job.processing_started_at == fresh_started_at


def _seed_product_intelligence_runs(session_factory, *, count: int) -> list:
    with session_factory() as db:
        base_created_at = utc_now() - timedelta(minutes=10)
        runs = []
        for index in range(count):
            household = _create_household(db, name="Product Intelligence Queue Household")
            run = ProductIntelligenceRun(
                household_id=household.id,
                provider_type="openai",
                source_model="test-model",
                mode="all",
                status="queued",
                target_product_external_ids=[],
                target_product_count=0,
                items_payload=[],
                events_payload=[],
                diagnostics_payload={},
                created_at=base_created_at + timedelta(seconds=index),
            )
            db.add(run)
            runs.append(run)
        db.commit()
        return [run.id for run in runs]


def _claim_product_intelligence_run_after_barrier(session_factory, barrier: threading.Barrier):
    with session_factory() as db:
        barrier.wait(timeout=10)
        claimed = _claim_next_product_intelligence_run(db)
        return claimed.id if claimed is not None else None


def test_postgresql_product_intelligence_claims_are_unique_under_multi_worker_contention(postgres_session_factory):
    # Invariant: concurrent product-intelligence workers claim each queued run at most once.
    run_ids = _seed_product_intelligence_runs(postgres_session_factory, count=3)
    barrier = threading.Barrier(3)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(_claim_product_intelligence_run_after_barrier, postgres_session_factory, barrier)
            for _ in run_ids
        ]
        claimed_ids = [future.result(timeout=10) for future in futures]

    assert set(claimed_ids) == set(run_ids)
    assert len(claimed_ids) == len(set(claimed_ids))

    with postgres_session_factory() as db:
        rows = db.scalars(select(ProductIntelligenceRun).where(ProductIntelligenceRun.id.in_(run_ids))).all()
        assert {row.status for row in rows} == {"running"}
        assert all(row.last_progress_at is not None for row in rows)


def test_postgresql_stale_product_intelligence_run_is_reclaimed_once(postgres_session_factory):
    # Invariant: stalled running product-intelligence runs are reclaimable without stealing fresh runs.
    with postgres_session_factory() as db:
        household = _create_household(db, name="Stale Product Intelligence Household")
        stale_progress_at = utc_now() - timedelta(hours=1)
        fresh_progress_at = utc_now()
        stale_run = ProductIntelligenceRun(
            household_id=household.id,
            provider_type="openai",
            source_model="test-model",
            mode="all",
            status="running",
            target_product_external_ids=[],
            target_product_count=0,
            items_payload=[],
            events_payload=[],
            diagnostics_payload={},
            processing_started_at=stale_progress_at,
            last_progress_at=stale_progress_at,
            created_at=utc_now() - timedelta(minutes=20),
        )
        fresh_run = ProductIntelligenceRun(
            household_id=household.id,
            provider_type="openai",
            source_model="test-model",
            mode="all",
            status="running",
            target_product_external_ids=[],
            target_product_count=0,
            items_payload=[],
            events_payload=[],
            diagnostics_payload={},
            processing_started_at=fresh_progress_at,
            last_progress_at=fresh_progress_at,
            created_at=utc_now() - timedelta(minutes=10),
        )
        db.add_all([stale_run, fresh_run])
        db.commit()
        stale_run_id = stale_run.id
        fresh_run_id = fresh_run.id

    with postgres_session_factory() as db:
        claimed = _claim_next_product_intelligence_run(db)
        second_claim = _claim_next_product_intelligence_run(db)

    assert claimed is not None
    assert claimed.id == stale_run_id
    assert claimed.status == "running"
    assert claimed.last_progress_at is not None
    assert claimed.last_progress_at > stale_progress_at
    assert second_claim is None

    with postgres_session_factory() as db:
        fresh_run = db.get(ProductIntelligenceRun, fresh_run_id)
        assert fresh_run is not None
        assert fresh_run.status == "running"
        assert fresh_run.last_progress_at == fresh_progress_at


def test_postgresql_stale_recipe_url_import_is_reclaimed_once(postgres_session_factory):
    # Invariant: stale recipe URL imports are reclaimable, while fresh processing imports stay owned.
    with postgres_session_factory() as db:
        household = _create_household(db, name="Stale Recipe URL Household")
        stale_updated_at = utc_now() - timedelta(hours=1)
        fresh_updated_at = utc_now()
        stale_record = RecipeURLImport(
            household_id=household.id,
            source_url="https://recipes.example/stale",
            normalized_url="https://recipes.example/stale",
            status="processing",
            note="Previous worker disappeared.",
            created_at=utc_now() - timedelta(minutes=20),
            updated_at=stale_updated_at,
        )
        fresh_record = RecipeURLImport(
            household_id=household.id,
            source_url="https://recipes.example/fresh",
            normalized_url="https://recipes.example/fresh",
            status="processing",
            note="Fresh worker still owns this.",
            created_at=utc_now() - timedelta(minutes=10),
            updated_at=fresh_updated_at,
        )
        db.add_all([stale_record, fresh_record])
        db.commit()
        stale_record_id = stale_record.id
        fresh_record_id = fresh_record.id

    with postgres_session_factory() as db:
        claimed = _claim_next_recipe_url_import(db)
        second_claim = _claim_next_recipe_url_import(db)

    assert claimed is not None
    assert claimed.id == stale_record_id
    assert claimed.status == "processing"
    assert claimed.note == "Fetching recipe metadata."
    assert claimed.updated_at is not None
    assert claimed.updated_at > stale_updated_at
    assert second_claim is None

    with postgres_session_factory() as db:
        fresh_record = db.get(RecipeURLImport, fresh_record_id)
        assert fresh_record is not None
        assert fresh_record.status == "processing"
        assert fresh_record.updated_at == fresh_updated_at
