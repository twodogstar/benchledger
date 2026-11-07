"""Run Alembic migrations from code, so `benchledger` needs no alembic.ini to work."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine

from benchledger.config import Settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def alembic_config(settings: Settings) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    # Alembic's config uses %-interpolation, so a literal % in a path must be doubled.
    cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    return cfg


def upgrade(settings: Settings, revision: str = "head") -> None:
    """Create the data folder if needed and bring the database schema up to date."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(settings), revision)


def current_revision(engine: Engine) -> str | None:
    """Return the schema revision the database is at, or None if it was never migrated."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()
