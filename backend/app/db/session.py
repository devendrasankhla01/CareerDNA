"""Database engine and session management."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine_kwargs = {}
_database_url = get_settings().database_url
if _database_url.startswith("sqlite"):
    # Open a fresh connection per checkout so that `scripts.reset_demo`
    # (which replaces the DB file) works even against a running server.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = NullPool

engine = create_engine(_database_url, pool_pre_ping=True, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
