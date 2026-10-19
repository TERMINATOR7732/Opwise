"""Unit tests for execution-aware operation lifecycle, plant clock, and validators.

Governed by Milestone 15A specification (AC-LIFE-01 through AC-LIFE-15).
"""

import pytest

from opwise.domain.entities import (
    Factory,
    Machine,
    MachineDowntime,
    Operation,
    OperationStatus,
    ProductionOrder,
)
from opwise.domain.exceptions import LifecycleStateError
from opwise.domain.validators import (
    validate_factory_for_optimization,
    validate_historical_and_active_downtimes,
    validate_historical_machine_exclusivity,
    validate_operation_lifecycle,
    validate_order_lifecycle_sequence,
    validate_plant_clock,
)


def _make_factory(
    current_time_minute: int = 0,
    machines: list[Machine] | None = None,
    downtimes: list[MachineDowntime] | None = None,
    orders: list[ProductionOrder] | None = None,
) -> Factory:
    """Helper to create a test Factory."""
    if machines is None:
        machines = [Machine(id="M1", name="Machine 1")]
    if downtimes is None:
        downtimes = []
    if orders is None:
        orders = []
    return Factory(
        workspace_id="ws-test",
        machines=machines,
        downtimes=downtimes,
        orders=orders,
        current_time_minute=current_time_minute,
    )


# --- AC-LIFE-01 to AC-LIFE-04: Operation Lifecycle Validation ---


def test_planned_operation_valid() -> None:
    """AC-LIFE-01: Valid PLANNED operation with all actual fields None."""
    op = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.PLANNED,
        actual_start_minute=None,
        actual_end_minute=None,
        remaining_duration_minutes=None,
    )
    validate_operation_lifecycle(op)


def test_planned_operation_with_actual_fields_fails() -> None:
    """AC-LIFE-02: PLANNED operation with actual_start_minute or remaining_duration fails."""
    op = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.PLANNED,
        actual_start_minute=10,
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_operation_lifecycle(op)
    assert exc_info.value.code == "INVALID_LIFECYCLE_STATE"


def test_in_progress_operation_valid() -> None:
    """AC-LIFE-03: Valid IN_PROGRESS operation with start and positive remaining duration."""
    op = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=10,
        actual_end_minute=None,
        remaining_duration_minutes=15,
    )
    validate_operation_lifecycle(op)


def test_in_progress_operation_missing_start_or_remaining_fails() -> None:
    """AC-LIFE-04: IN_PROGRESS operation missing start or remaining duration fails."""
    op_no_start = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=None,
        remaining_duration_minutes=15,
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_operation_lifecycle(op_no_start)
    assert exc_info.value.code == "INVALID_LIFECYCLE_STATE"

    op_no_rem = Operation(
        id="op2",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=10,
        remaining_duration_minutes=None,
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_operation_lifecycle(op_no_rem)
    assert exc_info.value.code == "INVALID_LIFECYCLE_STATE"

    op_zero_rem = Operation(
        id="op3",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=10,
        remaining_duration_minutes=0,
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_operation_lifecycle(op_zero_rem)
    assert exc_info.value.code == "INVALID_LIFECYCLE_STATE"

    op_with_end = Operation(
        id="op4",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=10,
        actual_end_minute=25,
        remaining_duration_minutes=5,
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_operation_lifecycle(op_with_end)
    assert exc_info.value.code == "INVALID_LIFECYCLE_STATE"


def test_completed_operation_valid() -> None:
    """AC-LIFE-05: Valid COMPLETED operation with start and end, no remaining duration."""
    op = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.COMPLETED,
        actual_start_minute=10,
        actual_end_minute=45,
        remaining_duration_minutes=None,
    )
    validate_operation_lifecycle(op)


def test_completed_operation_invalid_timestamps_or_remaining_fails() -> None:
    """AC-LIFE-06: COMPLETED operation with missing timestamps or end <= start fails."""
    op_missing_end = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.COMPLETED,
        actual_start_minute=10,
        actual_end_minute=None,
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_operation_lifecycle(op_missing_end)
    assert exc_info.value.code == "INVALID_LIFECYCLE_STATE"

    op_end_le_start = Operation(
        id="op2",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.COMPLETED,
        actual_start_minute=20,
        actual_end_minute=20,
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_operation_lifecycle(op_end_le_start)
    assert exc_info.value.code == "INVALID_LIFECYCLE_STATE"

    op_with_rem = Operation(
        id="op3",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.COMPLETED,
        actual_start_minute=10,
        actual_end_minute=40,
        remaining_duration_minutes=5,
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_operation_lifecycle(op_with_rem)
    assert exc_info.value.code == "INVALID_LIFECYCLE_STATE"


# --- AC-LIFE-07 to AC-LIFE-09: Order Lifecycle Sequence Validation ---


def test_order_lifecycle_sequence_valid() -> None:
    """AC-LIFE-07: Valid linear order lifecycle: COMPLETED -> IN_PROGRESS -> PLANNED."""
    ops = [
        Operation(
            id="op1",
            order_id="ord1",
            sequence_number=1,
            machine_id="M1",
            processing_duration_minutes=20,
            status=OperationStatus.COMPLETED,
            actual_start_minute=0,
            actual_end_minute=20,
        ),
        Operation(
            id="op2",
            order_id="ord1",
            sequence_number=2,
            machine_id="M2",
            processing_duration_minutes=30,
            status=OperationStatus.IN_PROGRESS,
            actual_start_minute=25,
            remaining_duration_minutes=15,
        ),
        Operation(
            id="op3",
            order_id="ord1",
            sequence_number=3,
            machine_id="M1",
            processing_duration_minutes=15,
            status=OperationStatus.PLANNED,
        ),
    ]
    order = ProductionOrder(id="ord1", order_code="ORD-1", release_time_minutes=0, due_date_minutes=100, operations=ops)
    validate_order_lifecycle_sequence(order)


def test_order_multiple_in_progress_fails() -> None:
    """AC-LIFE-08: Order with multiple IN_PROGRESS operations is rejected."""
    ops = [
        Operation(
            id="op1",
            order_id="ord1",
            sequence_number=1,
            machine_id="M1",
            processing_duration_minutes=20,
            status=OperationStatus.IN_PROGRESS,
            actual_start_minute=10,
            remaining_duration_minutes=10,
        ),
        Operation(
            id="op2",
            order_id="ord1",
            sequence_number=2,
            machine_id="M2",
            processing_duration_minutes=30,
            status=OperationStatus.IN_PROGRESS,
            actual_start_minute=20,
            remaining_duration_minutes=15,
        ),
    ]
    order = ProductionOrder(id="ord1", order_code="ORD-1", release_time_minutes=0, due_date_minutes=100, operations=ops)
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_order_lifecycle_sequence(order)
    assert exc_info.value.code == "INVALID_SEQUENCE"


def test_order_planned_before_completed_or_in_progress_fails() -> None:
    """AC-LIFE-09: PLANNED predecessor before COMPLETED or IN_PROGRESS is rejected."""
    ops = [
        Operation(
            id="op1",
            order_id="ord1",
            sequence_number=1,
            machine_id="M1",
            processing_duration_minutes=20,
            status=OperationStatus.PLANNED,
        ),
        Operation(
            id="op2",
            order_id="ord1",
            sequence_number=2,
            machine_id="M2",
            processing_duration_minutes=30,
            status=OperationStatus.COMPLETED,
            actual_start_minute=25,
            actual_end_minute=55,
        ),
    ]
    order = ProductionOrder(id="ord1", order_code="ORD-1", release_time_minutes=0, due_date_minutes=100, operations=ops)
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_order_lifecycle_sequence(order)
    assert exc_info.value.code == "INVALID_SEQUENCE"


def test_order_predecessor_overlap_fails() -> None:
    """AC-LIFE-10: In an order, operation start before predecessor end is rejected."""
    ops = [
        Operation(
            id="op1",
            order_id="ord1",
            sequence_number=1,
            machine_id="M1",
            processing_duration_minutes=20,
            status=OperationStatus.COMPLETED,
            actual_start_minute=10,
            actual_end_minute=30,
        ),
        Operation(
            id="op2",
            order_id="ord1",
            sequence_number=2,
            machine_id="M2",
            processing_duration_minutes=30,
            status=OperationStatus.COMPLETED,
            actual_start_minute=25,  # Started before op1 ended at 30!
            actual_end_minute=55,
        ),
    ]
    order = ProductionOrder(id="ord1", order_code="ORD-1", release_time_minutes=0, due_date_minutes=100, operations=ops)
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_order_lifecycle_sequence(order)
    assert exc_info.value.code == "INVALID_SEQUENCE"


def test_order_release_time_violation_fails() -> None:
    """AC-LIFE-11: First operation starting before order release time is rejected."""
    ops = [
        Operation(
            id="op1",
            order_id="ord1",
            sequence_number=1,
            machine_id="M1",
            processing_duration_minutes=20,
            status=OperationStatus.COMPLETED,
            actual_start_minute=5,  # Started before release_time_minutes=10!
            actual_end_minute=25,
        ),
    ]
    order = ProductionOrder(id="ord1", order_code="ORD-1", release_time_minutes=10, due_date_minutes=100, operations=ops)
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_order_lifecycle_sequence(order)
    assert exc_info.value.code == "INVALID_SEQUENCE"


# --- AC-LIFE-12 to AC-LIFE-13: Plant Clock Validation ---


def test_plant_clock_negative_fails() -> None:
    """AC-LIFE-12: Negative plant clock is rejected."""
    factory = _make_factory(current_time_minute=-5)
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_plant_clock(factory)
    assert exc_info.value.code == "INVALID_CLOCK"


def test_plant_clock_boundary_validation() -> None:
    """AC-LIFE-13: Operations must respect plant clock boundaries."""
    # Completed op ending at 50 with current_time=50 is valid (exact boundary)
    op_completed = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.COMPLETED,
        actual_start_minute=30,
        actual_end_minute=50,
    )
    # IN_PROGRESS starting at 50 with current_time=50 is valid (exact boundary)
    op_in_prog = Operation(
        id="op2",
        order_id="ord2",
        sequence_number=1,
        machine_id="M2",
        processing_duration_minutes=20,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=50,
        remaining_duration_minutes=10,
    )
    order1 = ProductionOrder(id="ord1", order_code="O1", operations=[op_completed])
    order2 = ProductionOrder(id="ord2", order_code="O2", operations=[op_in_prog])
    factory = _make_factory(
        current_time_minute=50,
        machines=[Machine(id="M1", name="M1"), Machine(id="M2", name="M2")],
        orders=[order1, order2],
    )
    validate_plant_clock(factory)

    # Completed op ending after current_time fails
    op_completed_late = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.COMPLETED,
        actual_start_minute=30,
        actual_end_minute=51,
    )
    factory_bad_comp = _make_factory(
        current_time_minute=50,
        orders=[ProductionOrder(id="ord1", order_code="O1", operations=[op_completed_late])],
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_plant_clock(factory_bad_comp)
    assert exc_info.value.code == "INVALID_CLOCK"

    # IN_PROGRESS starting after current_time fails
    op_in_prog_future = Operation(
        id="op2",
        order_id="ord2",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=51,
        remaining_duration_minutes=10,
    )
    factory_bad_prog = _make_factory(
        current_time_minute=50,
        orders=[ProductionOrder(id="ord2", order_code="O2", operations=[op_in_prog_future])],
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_plant_clock(factory_bad_prog)
    assert exc_info.value.code == "INVALID_CLOCK"


# --- AC-LIFE-14: Machine Exclusivity Validation ---


def test_machine_historical_overlap_fails() -> None:
    """AC-LIFE-14: Overlapping intervals on same machine are rejected."""
    # Completed op [10, 30) and Completed op [25, 40) on M1 overlap
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.COMPLETED,
        actual_start_minute=10,
        actual_end_minute=30,
    )
    op2 = Operation(
        id="op2",
        order_id="ord2",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=15,
        status=OperationStatus.COMPLETED,
        actual_start_minute=25,
        actual_end_minute=40,
    )
    factory = _make_factory(
        current_time_minute=50,
        orders=[
            ProductionOrder(id="ord1", order_code="O1", operations=[op1]),
            ProductionOrder(id="ord2", order_code="O2", operations=[op2]),
        ],
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_historical_machine_exclusivity(factory)
    assert exc_info.value.code == "HISTORICAL_MACHINE_CONFLICT"


def test_machine_exact_boundary_non_overlapping() -> None:
    """AC-LIFE-14b: Exact half-open boundary [10, 30) and [30, 50) on same machine is valid."""
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.COMPLETED,
        actual_start_minute=10,
        actual_end_minute=30,
    )
    op2 = Operation(
        id="op2",
        order_id="ord2",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=30,
        remaining_duration_minutes=15,
    )
    factory = _make_factory(
        current_time_minute=40,
        orders=[
            ProductionOrder(id="ord1", order_code="O1", operations=[op1]),
            ProductionOrder(id="ord2", order_code="O2", operations=[op2]),
        ],
    )
    validate_historical_machine_exclusivity(factory)


# --- AC-LIFE-15: Downtime Conflict Validation ---


def test_historical_downtime_conflict_fails() -> None:
    """AC-LIFE-15: Completed or in-progress operations overlapping machine downtime are rejected."""
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.COMPLETED,
        actual_start_minute=10,
        actual_end_minute=30,
    )
    dt = MachineDowntime(id="dt1", machine_id="M1", start_minute=25, end_minute=35, reason="Maintenance")
    factory = _make_factory(
        current_time_minute=50,
        downtimes=[dt],
        orders=[ProductionOrder(id="ord1", order_code="O1", operations=[op1])],
    )
    with pytest.raises(LifecycleStateError) as exc_info:
        validate_historical_and_active_downtimes(factory)
    assert exc_info.value.code == "HISTORICAL_DOWNTIME_CONFLICT"


def test_full_factory_validation_integration() -> None:
    """Integrated factory validation calls all lifecycle validators."""
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.COMPLETED,
        actual_start_minute=0,
        actual_end_minute=20,
    )
    op2 = Operation(
        id="op2",
        order_id="ord1",
        sequence_number=2,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=20,
        remaining_duration_minutes=10,
    )
    factory = _make_factory(
        current_time_minute=25,
        orders=[ProductionOrder(id="ord1", order_code="O1", operations=[op1, op2])],
    )
    res = validate_factory_for_optimization(factory)
    assert res.classification.value == "VALID_NON_EMPTY_FACTORY"
    assert res.is_optimizable is True
