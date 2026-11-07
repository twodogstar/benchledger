"""Shared test fixtures. Every test gets its own temporary data folder."""

import pytest
from fastapi.testclient import TestClient

from benchledger.app import create_app
from benchledger.config import Settings
from benchledger.db.migrate import upgrade


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture
def migrated(settings) -> Settings:
    upgrade(settings)
    return settings


@pytest.fixture
def client(migrated):
    app = create_app(migrated)
    with TestClient(app) as test_client:
        yield test_client
    app.state.engine.dispose()
