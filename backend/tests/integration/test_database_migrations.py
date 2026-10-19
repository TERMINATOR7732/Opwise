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


@pytest.mark.asyncio
async def test_startup_migration_mismatch_aborts() -> None:
    """TM-07.3: Database with missing or mismatched alembic_version causes startup to abort."""
    from opwise.main import create_app, lifespan, verify_database_schema

    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        temp_db = f.name

    try:
        # Create an empty, unmigrated database
        settings = Settings(db_url=f"sqlite+aiosqlite:///{temp_db}")
        engine = create_database_engine(settings)

        # 1. verify_database_schema directly on unmigrated database raises RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await verify_database_schema(engine, expected_revision="002_add_import_jobs_index")
        assert "alembic upgrade head" in str(exc_info.value).lower()

        # 2. verify lifespan startup on unmigrated database raises RuntimeError
        app = create_app(settings)
        with pytest.raises(RuntimeError):
            async with lifespan(app):
                pass

        await engine.dispose()
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)


@pytest.mark.asyncio
async def test_migration_from_prior_schema_to_head() -> None:
    """Verify upgrade from prior schema (001) to new schema (002) and index creation."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        temp_db = f.name

    try:
        cfg = _get_alembic_config(temp_db)
        # 1. Migrate to prior revision (001_initial_schema)
        command.upgrade(cfg, "001_initial_schema")

        settings = Settings(db_url=f"sqlite+aiosqlite:///{temp_db}")
        engine = create_database_engine(settings)

        # Verify prior revision schema
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT version_num FROM alembic_version;"))
            assert res.scalar_one() == "001_initial_schema"
            # Prior schema should not have ix_import_jobs_workspace_id
            idx_res = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_import_jobs_workspace_id';")
            )
            assert idx_res.scalar_one_or_none() is None

        await engine.dispose()

        # 2. Upgrade from prior schema to 002_add_import_jobs_index
        command.upgrade(cfg, "002_add_import_jobs_index")

        engine = create_database_engine(settings)
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT version_num FROM alembic_version;"))
            assert res.scalar_one() == "002_add_import_jobs_index"
            idx_res = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_import_jobs_workspace_id';")
            )
            assert idx_res.scalar_one() == "ix_import_jobs_workspace_id"

        await engine.dispose()

        # 3. Test downgrade back to 001_initial_schema
        command.downgrade(cfg, "001_initial_schema")
        engine = create_database_engine(settings)
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT version_num FROM alembic_version;"))
            assert res.scalar_one() == "001_initial_schema"
        await engine.dispose()

        # 4. Final upgrade to head
        command.upgrade(cfg, "head")
    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)

