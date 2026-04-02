from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete

db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["SESSION_SECRET_KEY"] = "test-session-secret"
os.environ["WEB_APP_URL"] = "http://testserver"
os.environ["API_BASE_URL"] = "http://testserver"

api_root = Path(__file__).resolve().parents[1]
alembic_config = Config(str(api_root / "alembic.ini"))
command.upgrade(alembic_config, "head")

from app.core.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Role  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == Role.__tablename__:
                continue
            session.execute(delete(table))
        session.commit()

    yield

    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == Role.__tablename__:
                continue
            session.execute(delete(table))
        session.commit()


@pytest.fixture
def db_session():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
