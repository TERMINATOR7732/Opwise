"""Pytest fixtures for Opwise domain testing."""

import pytest

from opwise.domain.entities import (
    Factory,
    Machine,
    MachineDowntime,
    ObjectiveMode,
    Operation,
    ProductionOrder,
    Schedule,
    ScheduledOperation,
    ScheduleKPIs,
    ScheduleStatus,
)


@pytest.fixture
def sample_machines() -> list[Machine]:
    """Provide three sample production machines."""
    return [
        Machine(id="M1", name="CNC Milling Station"),
        Machine(id="M2", name="Lathe Turning Center"),
        Machine(id="M3", name="Surface Grinder"),
    ]


@pytest.fixture
def sample_orders() -> list[ProductionOrder]:
    """Provide two sample production orders with contiguous operations."""
    return [
        ProductionOrder(
            id="ORD-01",
            order_code="J1",
            release_time_minutes=0,
            due_date_minutes=120,
            tardiness_weight=2,
            operations=[
                Operation(
                    id="OP-01-1",
                    order_id="ORD-01",
                    sequence_number=1,
                    machine_id="M1",
                    processing_duration_minutes=30,
                ),
                Operation(
                    id="OP-01-2",
                    order_id="ORD-01",
                    sequence_number=2,
                    machine_id="M2",
                    processing_duration_minutes=45,
                ),
            ],
        ),
        ProductionOrder(
            id="ORD-02",
            order_code="J2",
            release_time_minutes=10,
            due_date_minutes=150,
            tardiness_weight=1,
            operations=[
                Operation(
                    id="OP-02-1",
                    order_id="ORD-02",
                    sequence_number=1,
                    machine_id="M2",
                    processing_duration_minutes=40,
                ),
                Operation(
                    id="OP-02-2",
                    order_id="ORD-02",
                    sequence_number=2,
                    machine_id="M3",
                    processing_duration_minutes=50,
                ),
            ],
        ),
    ]


@pytest.fixture
def sample_factory(
    sample_machines: list[Machine],
    sample_orders: list[ProductionOrder],
) -> Factory:
    """Provide a valid non-empty shop floor factory."""
    return Factory(
        workspace_id="WS-001",
        machines=sample_machines,
        downtimes=[
            MachineDowntime(
                id="DT-01",
                machine_id="M1",
                start_minute=60,
                end_minute=90,
                reason="Spindle Maintenance",
            )
        ],
        orders=sample_orders,
    )


@pytest.fixture
def valid_schedule() -> Schedule:
    """Provide a verified feasible schedule for sample_factory passing all 8 invariants."""
    kpis = ScheduleKPIs(
        makespan_minutes=165,
        total_weighted_tardiness=15,
        late_order_count=1,
        on_time_rate=50.0,
    )
    scheduled_ops = [
        ScheduledOperation(
            operation_id="OP-01-1",
            order_id="ORD-01",
            machine_id="M1",
            sequence_number=1,
            start_minute=0,
            end_minute=30,
            processing_duration_minutes=30,
            slack_minutes=0,
        ),
        ScheduledOperation(
            operation_id="OP-01-2",
            order_id="ORD-01",
            machine_id="M2",
            sequence_number=2,
            start_minute=30,
            end_minute=75,
            processing_duration_minutes=45,
            slack_minutes=45,
        ),
        ScheduledOperation(
            operation_id="OP-02-1",
            order_id="ORD-02",
            machine_id="M2",
            sequence_number=1,
            start_minute=75,
            end_minute=115,
            processing_duration_minutes=40,
            slack_minutes=0,
        ),
        ScheduledOperation(
            operation_id="OP-02-2",
            order_id="ORD-02",
            machine_id="M3",
            sequence_number=2,
            start_minute=115,
            end_minute=165,
            processing_duration_minutes=50,
            slack_minutes=0,
        ),
    ]
    return Schedule(
        id="SCHED-VALID-01",
        workspace_id="WS-001",
        status=ScheduleStatus.OPTIMAL,
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        kpis=kpis,
        scheduled_operations=scheduled_ops,
        verified=False,
    )

