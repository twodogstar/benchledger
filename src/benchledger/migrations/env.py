"""Alembic environment: how migrations connect to the database."""

from alembic import context

from benchledger.config import load_settings
from benchledger.db import models  # noqa: F401  (imports the models so autogenerate sees them)
from benchledger.db.base import Base
from benchledger.db.session import make_engine

config = context.config
target_metadata = Base.metadata

# Set by benchledger.db.migrate; when running the `alembic` command directly, fall back
# to the normal BenchLedger settings so both routes hit the same database.
database_url = config.get_main_option("sqlalchemy.url") or load_settings().database_url


def run_migrations_offline() -> None:
    """Write SQL to stdout instead of running it (alembic upgrade --sql)."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Foreign keys off while migrating; see make_engine() for why.
    engine = make_engine(database_url, foreign_keys=False)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite can't ALTER most things in place; batch mode rebuilds the table safely.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
