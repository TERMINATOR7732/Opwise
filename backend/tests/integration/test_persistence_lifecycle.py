"""Integration tests for operation lifecycle and plant clock persistence, constraints, and snapshot compatibility.

Governed by Milestone 15A specification (AC-CLOCK-01, AC-CLOCK-02, AC-COMPAT-01..03).
"""

import json
import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from alembic import command
from alembic.config import Config
from opwise.config import Settings
from opwise.domain.entities import (
    Factory,
    Machine,
    Operation,
    OperationStatus,
    ProductionOrder,
)
from opwise.persistence.database import create_database_engine, create_session_factory
from opwise.persistence.models import (
    MachineModel,
    OperationModel,
    ProductionOrderModel,
    ScheduledOperationModel,
    ScheduleModel,
    WorkspaceModel,
)
from opwise.persistence.repository import FactoryRepository, ScheduleRepository, WorkspaceRepository
from opwise.services.snapshot import reconstruct_factory_from_snapshot, serialize_factory_snapshot


@pytest.fixture
def test_db_path() -> Generator[str, None, None]:
    """Provide a temporary SQLite database initialized with all migrations to head."""
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
async def test_operation_model_lifecycle_constraints(test_db_path: str) -> None:
    """Verify OperationModel database check constraints for lifecycle integrity."""
    settings = Settings(db_url=f"sqlite+aiosqlite:///{test_db_path}")
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        ws = WorkspaceModel(name="WS-Lifecycle-Test")
        session.add(ws)
        await session.flush()

        machine = MachineModel(workspace_id=ws.id, external_id="M1", name="M1")
        session.add(machine)
        order = ProductionOrderModel(workspace_id=ws.id, external_id="ORD-1", name="Order 1", due_minute=100)
        session.add(order)
        await session.flush()

        # 1. Valid PLANNED operation
        op_planned = OperationModel(
            order_id=order.id,
            sequence_index=1,
            machine_id=machine.id,
            processing_minutes=20,
            status="PLANNED",
            actual_start_minute=None,
            actual_end_minute=None,
            remaining_duration_minutes=None,
        )
        session.add(op_planned)
        await session.flush()

        # 2. Valid IN_PROGRESS operation
        op_in_prog = OperationModel(
            order_id=order.id,
            sequence_index=2,
            machine_id=machine.id,
            processing_minutes=30,
            status="IN_PROGRESS",
            actual_start_minute=10,
            actual_end_minute=None,
            remaining_duration_minutes=20,
        )
        session.add(op_in_prog)
        await session.flush()

        # 3. Valid COMPLETED operation
        op_completed = OperationModel(
            order_id=order.id,
            sequence_index=3,
            machine_id=machine.id,
            processing_minutes=15,
            status="COMPLETED",
            actual_start_minute=0,
            actual_end_minute=15,
            remaining_duration_minutes=None,
        )
        session.add(op_completed)
        await session.flush()
        await session.commit()

    # Verify check constraint violations
    async with session_factory() as session:
        # Invalid status
        bad_status_op = OperationModel(
            order_id=order.id,
            sequence_index=4,
            machine_id=machine.id,
            processing_minutes=10,
            status="UNKNOWN_STATUS",
        )
        session.add(bad_status_op)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async with session_factory() as session:
        # PLANNED with actual_start_minute -> violates chk_op_lifecycle_consistency
        bad_planned = OperationModel(
            order_id=order.id,
            sequence_index=4,
            machine_id=machine.id,
            processing_minutes=10,
            status="PLANNED",
            actual_start_minute=5,
        )
        session.add(bad_planned)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async with session_factory() as session:
        # IN_PROGRESS missing remaining_duration_minutes -> violates chk_op_lifecycle_consistency
        bad_in_prog = OperationModel(
            order_id=order.id,
            sequence_index=4,
            machine_id=machine.id,
            processing_minutes=10,
            status="IN_PROGRESS",
            actual_start_minute=5,
            remaining_duration_minutes=None,
        )
        session.add(bad_in_prog)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async with session_factory() as session:
        # COMPLETED with end <= start -> violates chk_op_actual_end_gt_start
        bad_comp = OperationModel(
            order_id=order.id,
            sequence_index=4,
            machine_id=machine.id,
            processing_minutes=10,
            status="COMPLETED",
            actual_start_minute=20,
            actual_end_minute=15,
        )
        session.add(bad_comp)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    await engine.dispose()


@pytest.mark.asyncio
async def test_schedule_clock_and_scheduled_operation_status(test_db_path: str) -> None:
    """Verify ScheduleModel current_time_minute and ScheduledOperationModel status check constraints."""
    settings = Settings(db_url=f"sqlite+aiosqlite:///{test_db_path}")
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        ws = WorkspaceModel(name="WS-Sched-Clock")
        session.add(ws)
        await session.flush()

        # Valid schedule with plant clock
        sched = ScheduleModel(
            workspace_id=ws.id,
            name="Clock Run",
            objective_type="PURE_MAKESPAN",
            solver_status="OPTIMAL",
            verification_status="VERIFIED",
            makespan_minutes=100,
            weighted_tardiness=0,
            late_order_count=0,
            on_time_rate=1.0,
            solver_wall_clock_seconds=0.5,
            input_snapshot_json="{}",
            current_time_minute=45,
        )
        session.add(sched)
        await session.flush()

        sched_op = ScheduledOperationModel(
            schedule_id=sched.id,
            operation_id="op-1",
            order_id="ord-1",
            machine_id="m-1",
            sequence_number=1,
            start_minute=10,
            end_minute=30,
            processing_duration_minutes=20,
            status="IN_PROGRESS",
        )
        session.add(sched_op)
        await session.flush()
        await session.commit()
        sched_id = sched.id

    # Verify retrieval
    async with session_factory() as session:
        repo = ScheduleRepository(session)
        loaded = await repo.get_by_id(ws.id, sched_id)
        assert loaded is not None
        assert loaded.current_time_minute == 45
        assert len(loaded.scheduled_operations) == 1
        assert loaded.scheduled_operations[0].status == "IN_PROGRESS"

        domain_sched = repo.to_domain_schedule(loaded)
        assert domain_sched.current_time_minute == 45
        assert domain_sched.scheduled_operations[0].status == OperationStatus.IN_PROGRESS

    # Verify negative plant clock is rejected by check constraint
    async with session_factory() as session:
        bad_sched = ScheduleModel(
            workspace_id=ws.id,
            name="Negative Clock Run",
            objective_type="PURE_MAKESPAN",
            solver_status="OPTIMAL",
            verification_status="VERIFIED",
            makespan_minutes=100,
            weighted_tardiness=0,
            late_order_count=0,
            on_time_rate=1.0,
            solver_wall_clock_seconds=0.5,
            input_snapshot_json="{}",
            current_time_minute=-1,
        )
        session.add(bad_sched)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    await engine.dispose()


@pytest.mark.asyncio
async def test_factory_repository_lifecycle_persistence_and_reload(test_db_path: str) -> None:
    """Verify FactoryRepository.replace_factory and get_factory persist and load lifecycle fields."""
    settings = Settings(db_url=f"sqlite+aiosqlite:///{test_db_path}")
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        ws_repo = WorkspaceRepository(session)
        ws = await ws_repo.create("WS-Repo-Lifecycle")
        ws_id = ws.id
        await session.commit()

    async with session_factory() as session:
        factory_repo = FactoryRepository(session)
        machine = MachineModel(external_id="M1", name="Mill 1")
        op1 = OperationModel(
            sequence_index=1,
            machine=machine,
            processing_minutes=25,
            status="COMPLETED",
            actual_start_minute=0,
            actual_end_minute=25,
            remaining_duration_minutes=None,
        )
        op2 = OperationModel(
            sequence_index=2,
            machine=machine,
            processing_minutes=35,
            status="IN_PROGRESS",
            actual_start_minute=25,
            actual_end_minute=None,
            remaining_duration_minutes=15,
        )
        order = ProductionOrderModel(
            external_id="ORD-101",
            name="Job 101",
            release_minute=0,
            due_minute=100,
            operations=[op1, op2],
        )
        await factory_repo.replace_factory(ws_id, [machine], [order])
        await session.commit()

    async with session_factory() as session:
        factory_repo = FactoryRepository(session)
        domain_factory = await factory_repo.get_factory(ws_id)
        assert domain_factory is not None
        assert len(domain_factory.orders) == 1
        ord_obj = domain_factory.orders[0]
        assert len(ord_obj.operations) == 2

        d_op1, d_op2 = ord_obj.operations[0], ord_obj.operations[1]
        assert d_op1.status == OperationStatus.COMPLETED
        assert d_op1.actual_start_minute == 0
        assert d_op1.actual_end_minute == 25
        assert d_op1.remaining_duration_minutes is None

        assert d_op2.status == OperationStatus.IN_PROGRESS
        assert d_op2.actual_start_minute == 25
        assert d_op2.actual_end_minute is None
        assert d_op2.remaining_duration_minutes == 15

    await engine.dispose()


def test_snapshot_backward_compatibility() -> None:
    """AC-COMPAT-01: Verify pre-Milestone-15 legacy snapshot format reconstructs cleanly."""
    legacy_snapshot = json.dumps(
        {
            "machines": [{"id": "M1", "name": "Machine 1"}],
            "downtimes": [{"id": "dt1", "machine_id": "M1", "start": 50, "end": 60}],
            "orders": [
                {
                    "id": "ord1",
                    "code": "ORD-1",
                    "release": 0,
                    "due": 100,
                    "weight": 1,
                    "operations": [
                        {"id": "op1", "seq": 1, "m": "M1", "dur": 30}
                    ],
                }
            ],
        }
    )
    factory = reconstruct_factory_from_snapshot("ws-test", legacy_snapshot)
    assert factory is not None
    assert factory.current_time_minute == 0
    assert len(factory.orders) == 1
    op = factory.orders[0].operations[0]
    assert op.status == OperationStatus.PLANNED
    assert op.actual_start_minute is None
    assert op.actual_end_minute is None
    assert op.remaining_duration_minutes is None


def test_snapshot_corruption_rejection() -> None:
    """AC-COMPAT-02 & AC-COMPAT-03: Verify corrupt snapshot status or negative clock returns None."""
    # Invalid status string
    corrupt_status_snapshot = json.dumps(
        {
            "current_time_minute": 10,
            "machines": [{"id": "M1", "name": "M1"}],
            "downtimes": [],
            "orders": [
                {
                    "id": "ord1",
                    "code": "ORD-1",
                    "release": 0,
                    "due": 100,
                    "weight": 1,
                    "operations": [
                        {
                            "id": "op1",
                            "seq": 1,
                            "m": "M1",
                            "dur": 30,
                            "status": "NON_EXISTENT_STATUS",
                        }
                    ],
                }
            ],
        }
    )
    assert reconstruct_factory_from_snapshot("ws-test", corrupt_status_snapshot) is None

    # Negative current_time_minute
    corrupt_clock_snapshot = json.dumps(
        {
            "current_time_minute": -5,
            "machines": [{"id": "M1", "name": "M1"}],
            "downtimes": [],
            "orders": [],
        }
    )
    assert reconstruct_factory_from_snapshot("ws-test", corrupt_clock_snapshot) is None


def test_snapshot_roundtrip_with_lifecycle() -> None:
    """Verify snapshot serialization and reconstruction roundtrip preserves clock and lifecycles."""
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.COMPLETED,
        actual_start_minute=5,
        actual_end_minute=25,
    )
    op2 = Operation(
        id="op2",
        order_id="ord1",
        sequence_number=2,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=25,
        remaining_duration_minutes=15,
    )
    order = ProductionOrder(id="ord1", order_code="ORD-1", release_time_minutes=5, due_date_minutes=100, operations=[op1, op2])
    factory = Factory(
        workspace_id="ws-test",
        machines=[Machine(id="M1", name="Machine 1")],
        orders=[order],
        current_time_minute=30,
    )

    serialized = serialize_factory_snapshot(factory)
    reconstructed = reconstruct_factory_from_snapshot("ws-test", serialized)
    assert reconstructed is not None
    assert reconstructed.current_time_minute == 30
    assert len(reconstructed.orders) == 1

    r_op1 = reconstructed.orders[0].operations[0]
    assert r_op1.status == OperationStatus.COMPLETED
    assert r_op1.actual_start_minute == 5
    assert r_op1.actual_end_minute == 25
    assert r_op1.remaining_duration_minutes is None

    r_op2 = reconstructed.orders[0].operations[1]
    assert r_op2.status == OperationStatus.IN_PROGRESS
    assert r_op2.actual_start_minute == 25
    assert r_op2.actual_end_minute is None
    assert r_op2.remaining_duration_minutes == 15
