"""Pytest fixtures for Opwise domain testing."""

import pytest

from opwise.domain.entities import (
    Factory,
    Machine,
    MachineDowntime,
    Operation,
    ProductionOrder,
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
