from __future__ import annotations

import os
import shutil
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
import_storage_root = tempfile.mkdtemp(prefix="pantry-imports-")
os.environ["IMPORT_STORAGE_ROOT"] = import_storage_root
backup_storage_root = tempfile.mkdtemp(prefix="pantry-backups-")
os.environ["BACKUP_STORAGE_ROOT"] = backup_storage_root

api_root = Path(__file__).resolve().parents[1]
alembic_config = Config(str(api_root / "alembic.ini"))
command.upgrade(alembic_config, "head")

from app.core.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Role  # noqa: E402
from app.services.rate_limits import clear_local_rate_limits  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    clear_local_rate_limits()
    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == Role.__tablename__:
                continue
            session.execute(delete(table))
        session.commit()
    shutil.rmtree(import_storage_root, ignore_errors=True)
    Path(import_storage_root).mkdir(parents=True, exist_ok=True)
    shutil.rmtree(backup_storage_root, ignore_errors=True)
    Path(backup_storage_root).mkdir(parents=True, exist_ok=True)

    yield

    clear_local_rate_limits()
    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == Role.__tablename__:
                continue
            session.execute(delete(table))
        session.commit()
    shutil.rmtree(import_storage_root, ignore_errors=True)
    Path(import_storage_root).mkdir(parents=True, exist_ok=True)
    shutil.rmtree(backup_storage_root, ignore_errors=True)
    Path(backup_storage_root).mkdir(parents=True, exist_ok=True)


@pytest.fixture
def db_session():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app, headers={"origin": "http://testserver"}) as test_client:
        yield test_client
