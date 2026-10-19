"""Integration tests for Alembic migration 004 (workspace plant clock).

Governed by Milestone 15A.1 specification.
"""

import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command
from alembic.config import Config
from opwise.config import Settings
from opwise.persistence.database import create_database_engine


def _get_alembic_config(db_path: str) -> Config:
    """Construct an Alembic Config pointing to a temporary test database."""
    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(ini_path.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    return cfg


@pytest.mark.asyncio
async def test_migration_004_upgrade_downgrade_cycle() -> None:
    """Verify migration 003 -> 004, default backfill to 0, check constraint, and downgrade/re-upgrade."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        temp_db = f.name

    try:
        cfg = _get_alembic_config(temp_db)

        # 1. Migrate to revision 003 (pre-workspace-clock)
        command.upgrade(cfg, "003_add_lifecycle_clock")

        # 2. Seed pre-migration data with full relational hierarchy
        settings = Settings(db_url=f"sqlite+aiosqlite:///{temp_db}")
        engine = create_database_engine(settings)

        now = datetime.now(UTC).isoformat()
        ws_id = str(uuid.uuid4())
        m_id = str(uuid.uuid4())
        ord_id = str(uuid.uuid4())
        op_id = str(uuid.uuid4())
        sched_id = str(uuid.uuid4())

        async with engine.connect() as conn:
            await conn.execute(
                text(
                    "INSERT INTO workspaces (id, name, description, created_at, updated_at) "
                    "VALUES (:id, :name, :desc, :created_at, :updated_at);"
                ),
                {"id": ws_id, "name": "Mig-004-WS", "desc": "Desc", "created_at": now, "updated_at": now},
            )
            await conn.execute(
                text(
                    "INSERT INTO machines (id, workspace_id, external_id, name, created_at) "
                    "VALUES (:id, :ws_id, :ext_id, :name, :created_at);"
                ),
                {"id": m_id, "ws_id": ws_id, "ext_id": "M1", "name": "Mill 1", "created_at": now},
            )
            await conn.execute(
                text(
                    "INSERT INTO production_orders (id, workspace_id, external_id, name, release_minute, due_minute, tardiness_weight, created_at) "
                    "VALUES (:id, :ws_id, :ext_id, :name, 0, 100, 1, :created_at);"
                ),
                {"id": ord_id, "ws_id": ws_id, "ext_id": "ORD-1", "name": "Order 1", "created_at": now},
            )
            await conn.execute(
                text(
                    "INSERT INTO operations (id, order_id, sequence_index, machine_id, processing_minutes, status) "
                    "VALUES (:id, :ord_id, 1, :m_id, 30, 'PLANNED');"
                ),
                {"id": op_id, "ord_id": ord_id, "m_id": m_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO schedules (id, workspace_id, name, objective_type, solver_status, verification_status, "
                    "makespan_minutes, weighted_tardiness, late_order_count, on_time_rate, solver_wall_clock_seconds, "
                    "input_snapshot_json, current_time_minute, created_at) "
                    "VALUES (:id, :ws_id, 'Sched 003', 'PURE_MAKESPAN', 'OPTIMAL', 'VERIFIED', 30, 0, 0, 1.0, 0.1, '{}', 45, :created_at);"
                ),
                {"id": sched_id, "ws_id": ws_id, "created_at": now},
            )
            await conn.commit()

        await engine.dispose()

        # 3. Upgrade to revision 004_add_workspace_clock
        command.upgrade(cfg, "004_add_workspace_clock")

        # 4. Verify defaults backfilled and existing data preserved
        engine = create_database_engine(settings)
        async with engine.connect() as conn:
            res_ws = await conn.execute(
                text("SELECT name, description, current_time_minute FROM workspaces WHERE id = :id;"),
                {"id": ws_id},
            )
            row_ws = res_ws.fetchone()
            assert row_ws is not None
            assert row_ws[0] == "Mig-004-WS"
            assert row_ws[1] == "Desc"
            assert row_ws[2] == 0, "Existing workspace must backfill current_time_minute = 0"

            # Verify schedule current_time_minute remains untouched at 45
            res_sched = await conn.execute(
                text("SELECT current_time_minute FROM schedules WHERE id = :id;"),
                {"id": sched_id},
            )
            row_sched = res_sched.fetchone()
            assert row_sched is not None
            assert row_sched[0] == 45, "Historical schedule current_time_minute must remain 45"

            # Verify inserting workspace with nonzero clock succeeds
            new_ws_id = str(uuid.uuid4())
            await conn.execute(
                text(
                    "INSERT INTO workspaces (id, name, description, current_time_minute, created_at, updated_at) "
                    "VALUES (:id, 'Nonzero Clock WS', 'Desc', 120, :created_at, :updated_at);"
                ),
                {"id": new_ws_id, "created_at": now, "updated_at": now},
            )
            await conn.commit()

            res_new = await conn.execute(
                text("SELECT current_time_minute FROM workspaces WHERE id = :id;"),
                {"id": new_ws_id},
            )
            assert res_new.scalar_one() == 120

            # Verify negative current_time_minute is rejected by check constraint
            with pytest.raises(IntegrityError):
                await conn.execute(
                    text(
                        "INSERT INTO workspaces (id, name, description, current_time_minute, created_at, updated_at) "
                        "VALUES (:id, 'Negative Clock WS', 'Desc', -5, :created_at, :updated_at);"
                    ),
                    {"id": str(uuid.uuid4()), "created_at": now, "updated_at": now},
                )
            await conn.rollback()

        await engine.dispose()

        # 5. Downgrade back to revision 003_add_lifecycle_clock
        command.downgrade(cfg, "003_add_lifecycle_clock")

        engine = create_database_engine(settings)
        async with engine.connect() as conn:
            res = await conn.execute(text("PRAGMA table_info(workspaces);"))
            ws_columns = {row[1] for row in res.fetchall()}
            assert "current_time_minute" not in ws_columns, "current_time_minute must be dropped on downgrade"

            # Verify existing workspace row still exists
            ws_count = (await conn.execute(text("SELECT COUNT(*) FROM workspaces;"))).scalar()
            assert ws_count == 2

        await engine.dispose()

        # 6. Re-upgrade to head ensures idempotency
        command.upgrade(cfg, "head")

    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)
