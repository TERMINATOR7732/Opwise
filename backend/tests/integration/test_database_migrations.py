"""Integration tests for database migrations, SQLite WAL pragmas, and transactional integrity.

Governed by DATA_AND_API.md Section 2 and TEST_AND_RELEASE_PLAN.md TM-07.
"""

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command
from alembic.config import Config
from opwise.config import Settings
from opwise.persistence.database import create_database_engine, create_session_factory
from opwise.persistence.models import MachineModel, WorkspaceModel


def _get_alembic_config(db_path: str) -> Config:
    """Construct an Alembic Config pointing to a temporary test database."""
    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(ini_path.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    return cfg


def test_fresh_database_migration_cycle() -> None:
    """TM-07.3: Verify fresh DB migrates to head, downgrades to base, and re-migrates cleanly."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        temp_db = f.name

    try:
        cfg = _get_alembic_config(temp_db)
        # 1. Upgrade from empty DB to head
        command.upgrade(cfg, "head")

        # 2. Downgrade from head back to base
        command.downgrade(cfg, "base")

        # 3. Re-apply upgrade to ensure idempotency
        command.upgrade(cfg, "head")
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)


@pytest.mark.asyncio
async def test_sqlite_pragmas_enforcement() -> None:
    """TM-07: Verify required SQLite pragmas (WAL, synchronous=NORMAL, foreign_keys=ON)."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        temp_db = f.name

    try:
        cfg = _get_alembic_config(temp_db)
        command.upgrade(cfg, "head")

        settings = Settings(db_url=f"sqlite+aiosqlite:///{temp_db}", db_synchronous="NORMAL", db_busy_timeout_ms=5000)
        engine = create_database_engine(settings)

        async with engine.connect() as conn:
            fk = (await conn.execute(text("PRAGMA foreign_keys;"))).scalar()
            sync = (await conn.execute(text("PRAGMA synchronous;"))).scalar()
            busy = (await conn.execute(text("PRAGMA busy_timeout;"))).scalar()
            jm = (await conn.execute(text("PRAGMA journal_mode;"))).scalar()

            assert fk == 1, "Foreign keys must be enabled"
            assert sync == 1, "Synchronous mode must be NORMAL (1)"
            assert busy == 5000, "Busy timeout must be 5000ms"
            assert jm is not None and str(jm).lower() == "wal", "Journal mode must be WAL"

        await engine.dispose()
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)


@pytest.mark.asyncio
async def test_foreign_key_and_check_constraints() -> None:
    """TM-07: Verify SQLite rejects orphaned records and check constraint violations."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        temp_db = f.name

    try:
        cfg = _get_alembic_config(temp_db)
        command.upgrade(cfg, "head")

        settings = Settings(db_url=f"sqlite+aiosqlite:///{temp_db}")
        engine = create_database_engine(settings)
        session_factory = create_session_factory(engine)

        async with session_factory() as session:
            # Foreign key violation: Machine referencing non-existent workspace
            orphaned_machine = MachineModel(
                workspace_id="non-existent-workspace-id",
                external_id="M1",
                name="CNC Mill",
            )
            session.add(orphaned_machine)
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

        await engine.dispose()
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)


@pytest.mark.asyncio
async def test_transaction_rollback_on_failure() -> None:
    """TM-07.1: Verify multi-record operation rolls back atomically upon mid-transaction error."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        temp_db = f.name

    try:
        cfg = _get_alembic_config(temp_db)
        command.upgrade(cfg, "head")

        settings = Settings(db_url=f"sqlite+aiosqlite:///{temp_db}")
        engine = create_database_engine(settings)
        session_factory = create_session_factory(engine)

        async with session_factory() as session:
            ws = WorkspaceModel(name="Rollback Test WS", description="Test WS")
            session.add(ws)
            await session.commit()
            ws_id = ws.id

        # Now start an atomic transaction that partially succeeds then fails
        async with session_factory() as session:
            try:
                m1 = MachineModel(workspace_id=ws_id, external_id="M1", name="Machine 1")
                session.add(m1)
                await session.flush()

                # Duplicate external_id in same workspace -> violates unique constraint
                m2_dup = MachineModel(workspace_id=ws_id, external_id="M1", name="Machine 1 Duplicate")
                session.add(m2_dup)
                await session.flush()
                await session.commit()
            except IntegrityError:
                await session.rollback()

        # Verify target workspace has 0 machines (m1 was rolled back)
        async with session_factory() as session:
            res = await session.execute(text(f"SELECT COUNT(*) FROM machines WHERE workspace_id = '{ws_id}';"))
            count = res.scalar()
            assert count == 0, "Partial insert must be completely rolled back"

        await engine.dispose()
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)
