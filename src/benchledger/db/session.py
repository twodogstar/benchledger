"""Engine and session setup for SQLite."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from benchledger.db import audit  # noqa: F401  (importing registers the change-log hook)
from benchledger.db.models import OWNER_ID


def make_engine(database_url: str, *, foreign_keys: bool = True) -> Engine:
    """Create an engine with the SQLite settings BenchLedger relies on.

    `foreign_keys=False` is only for migrations: SQLite rebuilds tables to alter them, and
    with foreign keys on, dropping the old table could cascade-delete rows that point at it.
    """
    fk_pragma = "PRAGMA foreign_keys=ON" if foreign_keys else "PRAGMA foreign_keys=OFF"
    engine = create_engine(
        database_url,
        # FastAPI runs ordinary (non-async) routes in a thread pool, so a connection
        # may be used by a different thread than the one that opened it.
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")  # readers don't block the writer
        cursor.execute(fk_pragma)  # SQLite leaves foreign keys off unless asked
        cursor.execute("PRAGMA busy_timeout=5000")  # wait up to 5 s for a lock
        cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # info["author_id"] is who the change log credits; always the owner until logins (C1).
    return sessionmaker(bind=engine, expire_on_commit=False, info={"author_id": OWNER_ID})
