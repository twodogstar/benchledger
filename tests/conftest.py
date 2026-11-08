"""Shared test fixtures. Every test gets its own temporary data folder."""

import pytest
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

from benchledger.app import create_app
from benchledger.config import Settings
from benchledger.db.migrate import alembic_config, upgrade
from benchledger.db.session import make_engine, make_session_factory


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def migrated(settings) -> Settings:
    upgrade(settings)
    return settings


@pytest.fixture
def session(migrated):
    """A database session on a freshly migrated database, for testing services directly."""
    engine = make_engine(migrated.database_url)
    with make_session_factory(engine)() as db_session:
        yield db_session
    engine.dispose()


@pytest.fixture
def client(migrated):
    app = create_app(migrated)
    with TestClient(app) as test_client:
        yield test_client
    app.state.engine.dispose()


@pytest.fixture
def head_revision(settings) -> str:
    """The newest migration, so tests don't need updating each time one is added."""
    return ScriptDirectory.from_config(alembic_config(settings)).get_current_head()
