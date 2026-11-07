from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text

from benchledger.db.base import Base
from benchledger.db.migrate import current_revision
from benchledger.db.session import make_engine


def test_upgrade_creates_tables(migrated):
    engine = make_engine(migrated.database_url)
    tables = set(inspect(engine).get_table_names())
    assert {"users", "change_log", "alembic_version"} <= tables
    assert current_revision(engine) == "0002"
    engine.dispose()


def test_owner_user_is_seeded(migrated):
    engine = make_engine(migrated.database_url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, name, role FROM users")).all()
    assert rows == [(1, "Owner", "owner")]
    engine.dispose()


def test_sqlite_pragmas(migrated):
    engine = make_engine(migrated.database_url)
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
    engine.dispose()


def test_models_match_migrations(migrated):
    """Fails if someone changes a model without writing a migration (or the reverse)."""
    engine = make_engine(migrated.database_url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
    engine.dispose()
