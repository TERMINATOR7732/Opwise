"""Database connection lifecycle, SQLite WAL pragmas, and session management.

Governed by DATA_AND_API.md Section 2.1, ADR-001, and PROJECT_RULES.md.
Enforces SQLite foreign keys, WAL mode, busy timeout, and clean session lifecycle.
"""

import contextlib
import sqlite3
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from opwise.config import Settings, get_settings


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy ORM models."""


def _configure_sqlite_pragmas(
    dbapi_connection: Any,
    connection_record: Any,
    busy_timeout_ms: int = 5000,
    synchronous: str = "NORMAL",
) -> None:
    """Set SQLite pragmas on every newly established raw DBAPI connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute(f"PRAGMA busy_timeout = {busy_timeout_ms};")
    cursor.execute(f"PRAGMA synchronous = {synchronous};")
    cursor.execute("PRAGMA cache_size = -64000;")
    # Set WAL mode on file-based databases
    with contextlib.suppress(sqlite3.OperationalError):
        cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.close()


def create_database_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create an AsyncEngine configured with required SQLite pragmas."""
    cfg = settings or get_settings()
    engine = create_async_engine(
        cfg.db_url,
        echo=cfg.db_echo,
        connect_args={"timeout": cfg.db_timeout_seconds},
    )

    busy_ms = cfg.db_busy_timeout_ms
    sync_mode = cfg.db_synchronous

    @event.listens_for(engine.sync_engine, "connect")
    def on_connect(dbapi_connection: Any, connection_record: Any) -> None:
        _configure_sqlite_pragmas(
            dbapi_connection,
            connection_record,
            busy_timeout_ms=busy_ms,
            synchronous=sync_mode,
        )

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a configured async sessionmaker."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for dependency injection with auto-rollback."""
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
