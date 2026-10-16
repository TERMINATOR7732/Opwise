"""Integration tests for repository pattern, domain mapping, and workspace isolation.

Governed by DATA_AND_API.md Section 1 and ARCHITECTURE.md Section 3.
"""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from alembic import command
from alembic.config import Config
from opwise.config import Settings
from opwise.domain.entities import (
    ObjectiveMode,
    Schedule,
    ScheduledOperation,
    ScheduleKPIs,
    ScheduleStatus,
)
from opwise.persistence.database import create_database_engine, create_session_factory
from opwise.persistence.models import (
    MachineDowntimeModel,
    MachineModel,
    OperationModel,
    ProductionOrderModel,
)
from opwise.persistence.repository import (
    FactoryRepository,
    ScheduleRepository,
    WorkspaceRepository,
)


@pytest.fixture
def test_db_path() -> Generator[str, None, None]:
    """Provide a temporary SQLite database initialized with Alembic migrations."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        db_path = f.name
    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(ini_path.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(cfg, "head")
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_workspace_repository_crud(test_db_path: str) -> None:
    """Verify WorkspaceRepository create, get, list, and delete."""
    settings = Settings(db_url=f"sqlite+aiosqlite:///{test_db_path}")
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        repo = WorkspaceRepository(session)
        ws1 = await repo.create("Workspace Alpha", "Alpha description")
        ws2 = await repo.create("Workspace Beta")
        await session.commit()
        ws1_id = ws1.id

    async with session_factory() as session:
        repo = WorkspaceRepository(session)
        fetched = await repo.get_by_id(ws1_id)
        assert fetched is not None
        assert fetched.name == "Workspace Alpha"

        by_name = await repo.get_by_name("Workspace Beta")
        assert by_name is not None
        assert by_name.id == ws2.id

        all_ws = await repo.list_all()
        assert len(all_ws) == 2

        deleted = await repo.delete(ws1_id)
        assert deleted is True
        await session.commit()

    async with session_factory() as session:
        repo = WorkspaceRepository(session)
        assert await repo.get_by_id(ws1_id) is None
        assert len(await repo.list_all()) == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_factory_repository_and_domain_mapping(test_db_path: str) -> None:
    """Verify FactoryRepository replaces factory and maps to pure domain entities."""
    settings = Settings(db_url=f"sqlite+aiosqlite:///{test_db_path}")
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        ws_repo = WorkspaceRepository(session)
        ws = await ws_repo.create("Factory Test WS")
        await session.commit()
        ws_id = ws.id

    async with session_factory() as session:
        f_repo = FactoryRepository(session)
        m1 = MachineModel(id="M1-ID", workspace_id=ws_id, external_id="M1", name="CNC Mill")
        dt1 = MachineDowntimeModel(id="DT1-ID", machine_id="M1-ID", start_minute=30, end_minute=60, reason="Lube")
        m1.downtimes.append(dt1)

        o1 = ProductionOrderModel(id="ORD1-ID", workspace_id=ws_id, external_id="J1", name="Job 1", release_minute=0, due_minute=100, tardiness_weight=2)
        op1 = OperationModel(id="OP1-ID", order_id="ORD1-ID", sequence_index=1, machine_id="M1-ID", processing_minutes=25)
        o1.operations.append(op1)

        await f_repo.replace_factory(ws_id, [m1], [o1])
        await session.commit()

    async with session_factory() as session:
        f_repo = FactoryRepository(session)
        factory = await f_repo.get_factory(ws_id)
        assert factory is not None
        assert len(factory.machines) == 1
        assert factory.machines[0].id == "M1-ID"
        assert len(factory.downtimes) == 1
        assert factory.downtimes[0].start_minute == 30
        assert len(factory.orders) == 1
        assert factory.orders[0].id == "ORD1-ID"
        assert len(factory.orders[0].operations) == 1
        assert factory.orders[0].operations[0].processing_duration_minutes == 25

    await engine.dispose()


@pytest.mark.asyncio
async def test_schedule_repository_and_workspace_isolation(test_db_path: str) -> None:
    """Verify ScheduleRepository persistence, conversion, and workspace isolation."""
    settings = Settings(db_url=f"sqlite+aiosqlite:///{test_db_path}")
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        ws_repo = WorkspaceRepository(session)
        ws_a = await ws_repo.create("WS-A")
        ws_b = await ws_repo.create("WS-B")
        await session.commit()
        ws_a_id = ws_a.id
        ws_b_id = ws_b.id

    sched = Schedule(
        id="SCHED-1",
        workspace_id=ws_a_id,
        status=ScheduleStatus.OPTIMAL,
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        kpis=ScheduleKPIs(makespan_minutes=120, total_weighted_tardiness=0, late_order_count=0, on_time_rate=100.0),
        scheduled_operations=[
            ScheduledOperation("OP-1", "ORD-1", "M1", 1, 0, 30, 30, slack_minutes=10)
        ],
        verified=True,
    )

    async with session_factory() as session:
        sched_repo = ScheduleRepository(session)
        await sched_repo.save_schedule(ws_a_id, sched, "Baseline Schedule", wall_clock_seconds=1.2)
        await session.commit()

    async with session_factory() as session:
        sched_repo = ScheduleRepository(session)
        # 1. Fetch under WS-A succeeds
        s_model = await sched_repo.get_by_id(ws_a_id, "SCHED-1")
        assert s_model is not None
        assert s_model.name == "Baseline Schedule"
        assert len(s_model.scheduled_operations) == 1

        # 2. Conversion to domain entity preserves fields
        domain_sched = sched_repo.to_domain_schedule(s_model)
        assert domain_sched.status == ScheduleStatus.OPTIMAL
        assert domain_sched.kpis.makespan_minutes == 120
        assert domain_sched.scheduled_operations[0].processing_duration_minutes == 30

        # 3. Workspace isolation: querying from WS-B returns None
        isolated_check = await sched_repo.get_by_id(ws_b_id, "SCHED-1")
        assert isolated_check is None, "Workspace B must not access Workspace A schedule"

    await engine.dispose()
