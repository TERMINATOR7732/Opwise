"""Integration tests for Alembic migration 003 (operation lifecycle and plant clock).

Governed by Milestone 15A specification (AC-MIG-01 through AC-MIG-05).
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
async def test_migration_003_upgrade_downgrade_cycle() -> None:
    """AC-MIG-01..05: Test migration from 002 to 003, default backfills, constraints, and downgrade."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        temp_db = f.name

    try:
        cfg = _get_alembic_config(temp_db)

        # 1. Migrate to revision 002 (pre-lifecycle)
        command.upgrade(cfg, "002_add_import_jobs_index")

        # 2. Seed pre-migration data with full relational foreign keys
        settings = Settings(db_url=f"sqlite+aiosqlite:///{temp_db}")
        engine = create_database_engine(settings)

        now = datetime.now(UTC).isoformat()
        ws_id = str(uuid.uuid4())
        m_id = str(uuid.uuid4())
        ord_id = str(uuid.uuid4())
        op_id = str(uuid.uuid4())
        sched_id = str(uuid.uuid4())
        sched_op_id = str(uuid.uuid4())

        async with engine.connect() as conn:
            await conn.execute(
                text(
                    "INSERT INTO workspaces (id, name, description, created_at, updated_at) "
                    "VALUES (:id, :name, :desc, :created_at, :updated_at);"
                ),
                {"id": ws_id, "name": "Mig-Test-WS", "desc": "Desc", "created_at": now, "updated_at": now},
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
                    "INSERT INTO operations (id, order_id, sequence_index, machine_id, processing_minutes) "
                    "VALUES (:id, :ord_id, 1, :m_id, 30);"
                ),
                {"id": op_id, "ord_id": ord_id, "m_id": m_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO schedules (id, workspace_id, name, objective_type, solver_status, verification_status, "
                    "makespan_minutes, weighted_tardiness, late_order_count, on_time_rate, solver_wall_clock_seconds, "
                    "input_snapshot_json, created_at) "
                    "VALUES (:id, :ws_id, 'Legacy Sched', 'PURE_MAKESPAN', 'OPTIMAL', 'VERIFIED', 30, 0, 0, 1.0, 0.1, '{}', :created_at);"
                ),
                {"id": sched_id, "ws_id": ws_id, "created_at": now},
            )
            await conn.execute(
                text(
                    "INSERT INTO scheduled_operations (id, schedule_id, operation_id, order_id, machine_id, sequence_number, "
                    "start_minute, end_minute, processing_duration_minutes, slack_minutes) "
                    "VALUES (:id, :sched_id, :op_id, :ord_id, :m_id, 1, 0, 30, 30, 0);"
                ),
                {"id": sched_op_id, "sched_id": sched_id, "op_id": op_id, "ord_id": ord_id, "m_id": m_id},
            )
            await conn.commit()

        # Dispose async engine before running synchronous Alembic commands
        await engine.dispose()

        # 3. Upgrade to revision 003_add_lifecycle_clock
        command.upgrade(cfg, "003_add_lifecycle_clock")

        # 4. Verify defaults backfilled on existing records
        engine = create_database_engine(settings)
        async with engine.connect() as conn:
            # AC-MIG-01: Operation defaults
            res_op = await conn.execute(
                text("SELECT status, actual_start_minute, actual_end_minute, remaining_duration_minutes FROM operations WHERE id = :id;"),
                {"id": op_id},
            )
            row_op = res_op.fetchone()
            assert row_op is not None
            assert row_op[0] == "PLANNED"
            assert row_op[1] is None
            assert row_op[2] is None
            assert row_op[3] is None

            # AC-MIG-02: Schedule defaults
            res_sched = await conn.execute(
                text("SELECT current_time_minute FROM schedules WHERE id = :id;"),
                {"id": sched_id},
            )
            row_sched = res_sched.fetchone()
            assert row_sched is not None
            assert row_sched[0] == 0

            # AC-MIG-03: Scheduled operation defaults
            res_so = await conn.execute(
                text("SELECT status FROM scheduled_operations WHERE id = :id;"),
                {"id": sched_op_id},
            )
            row_so = res_so.fetchone()
            assert row_so is not None
            assert row_so[0] == "PLANNED"

            # AC-MIG-04: Inserting valid IN_PROGRESS and COMPLETED operations succeeds
            new_op_in_prog = str(uuid.uuid4())
            await conn.execute(
                text(
                    "INSERT INTO operations (id, order_id, sequence_index, machine_id, processing_minutes, status, actual_start_minute, remaining_duration_minutes) "
                    "VALUES (:id, :ord_id, 2, :m_id, 20, 'IN_PROGRESS', 5, 15);"
                ),
                {"id": new_op_in_prog, "ord_id": ord_id, "m_id": m_id},
            )
            new_op_completed = str(uuid.uuid4())
            await conn.execute(
                text(
                    "INSERT INTO operations (id, order_id, sequence_index, machine_id, processing_minutes, status, actual_start_minute, actual_end_minute) "
                    "VALUES (:id, :ord_id, 3, :m_id, 10, 'COMPLETED', 0, 10);"
                ),
                {"id": new_op_completed, "ord_id": ord_id, "m_id": m_id},
            )
            await conn.commit()

            # Inserting check constraint violation fails
            with pytest.raises(IntegrityError):
                await conn.execute(
                    text(
                        "INSERT INTO operations (id, order_id, sequence_index, machine_id, processing_minutes, status, actual_start_minute) "
                        "VALUES (:id, :ord_id, 4, :m_id, 10, 'PLANNED', 5);"
                    ),
                    {"id": str(uuid.uuid4()), "ord_id": ord_id, "m_id": m_id},
                )
            await conn.rollback()

        await engine.dispose()

        # 5. AC-MIG-05: Downgrade back to revision 002_add_import_jobs_index
        command.downgrade(cfg, "002_add_import_jobs_index")

        engine = create_database_engine(settings)
        async with engine.connect() as conn:
            # Inspect dropped columns in operations table
            res = await conn.execute(text("PRAGMA table_info(operations);"))
            op_columns = {row[1] for row in res.fetchall()}
            assert "status" not in op_columns
            assert "actual_start_minute" not in op_columns
            assert "actual_end_minute" not in op_columns
            assert "remaining_duration_minutes" not in op_columns

            # Inspect dropped column in schedules table
            res = await conn.execute(text("PRAGMA table_info(schedules);"))
            sched_columns = {row[1] for row in res.fetchall()}
            assert "current_time_minute" not in sched_columns

            # Inspect dropped column in scheduled_operations table
            res = await conn.execute(text("PRAGMA table_info(scheduled_operations);"))
            so_columns = {row[1] for row in res.fetchall()}
            assert "status" not in so_columns

        await engine.dispose()

        # 6. Re-upgrade to head ensures idempotency
        command.upgrade(cfg, "head")

    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)
