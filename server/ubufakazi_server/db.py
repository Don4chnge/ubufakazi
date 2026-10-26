"""Database engine and session. SQLite for the local demo; any SQLAlchemy URL (e.g. Postgres) works."""
from __future__ import annotations

import threading
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_Session = None

# One in-process lock for every write transaction. SQLite allows one writer at a time anyway; taking this
# lock first means the hash-chained audit log is always appended in order and writers never deadlock.
# (Single server process assumed; see docs/UBUFAKAZI-2.md.)
write_lock = threading.RLock()


def engine():
    global _engine, _Session
    if _engine is None:
        url = get_settings().database_url
        kwargs = {}
        if url.startswith("postgresql"):
            kwargs.update(pool_pre_ping=True, pool_recycle=280, pool_size=5, max_overflow=5)   # serverless DBs drop idle connections
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        _engine = create_engine(url, future=True, **kwargs)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.close()
        _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def SessionLocal():
    engine()
    return _Session()


@contextmanager
def session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db():
    """FastAPI dependency."""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def init_db():
    from . import models  # noqa: F401  (register tables)
    Base.metadata.create_all(engine())


def reset_engine():
    """Used by tests."""
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Session = None
