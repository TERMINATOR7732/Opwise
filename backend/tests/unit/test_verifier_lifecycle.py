"""Unit tests for clean-room independent schedule verifier with lifecycle operations (Milestone 15B).

Governed by Milestone 15B verifier specifications:
- Invariant 1: Cardinality across all lifecycle operations
- Invariant 2: Duration, timestamps, and status matching
- Invariant 3: Release time and plant clock adherence
- Invariant 4: Sequential intra-order precedence
- Invariant 5: Machine exclusivity (including active locks)
- Invariant 6: Downtime collision detection
- Invariant 7: Dynamic horizon bounds
- Invariant 8: Metric concordance
"""

from opwise.domain.entities import (
    Factory,
    Machine,
    ObjectiveMode,
    Operation,
    OperationStatus,
    ProductionOrder,
    Schedule,
    ScheduledOperation,
    ScheduleKPIs,
    ScheduleStatus,
)
from opwise.verifier.independent_verifier import (
    InvariantRule,
    ScheduleVerifier,
    VerificationStatus,
)


def _make_sample_lifecycle_setup() -> tuple[Factory, Schedule]:
    """Helper creating a valid mixed-lifecycle factory and corresponding verified schedule."""
    clock = 40
    m1 = Machine(id="M1", name="Mill 1")
    m2 = Machine(id="M2", name="Lathe 1")

    # Order 1: Op 1 COMPLETED [0, 25), Op 2 IN_PROGRESS [25, clock=40) remaining 20 -> end 60
    op1_1 = Operation(
        id="op1_1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=25,
        status=OperationStatus.COMPLETED,
        actual_start_minute=0,
        actual_end_minute=25,
    )
    op1_2 = Operation(
        id="op1_2",
        order_id="ord1",
        sequence_number=2,
        machine_id="M2",
        processing_duration_minutes=35,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=25,
        remaining_duration_minutes=20,
    )
    order1 = ProductionOrder(
        id="ord1",
        order_code="J1",
        release_time_minutes=0,
        due_date_minutes=70,
        tardiness_weight=1,
        operations=[op1_1, op1_2],
    )

    # Order 2: Op 2_1 PLANNED on M1 [40, 70)
    op2_1 = Operation(
        id="op2_1",
        order_id="ord2",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.PLANNED,
    )
    order2 = ProductionOrder(
        id="ord2",
        order_code="J2",
        release_time_minutes=10,
        due_date_minutes=80,
        tardiness_weight=1,
        operations=[op2_1],
    )

    factory = Factory(
        workspace_id="ws-verif",
        machines=[m1, m2],
        downtimes=[],
        orders=[order1, order2],
        current_time_minute=clock,
    )

    s_op1 = ScheduledOperation(
        operation_id="op1_1",
        order_id="ord1",
        machine_id="M1",
        sequence_number=1,
        start_minute=0,
        end_minute=25,
        processing_duration_minutes=25,
        slack_minutes=0,
        status=OperationStatus.COMPLETED,
    )
    s_op2 = ScheduledOperation(
        operation_id="op1_2",
        order_id="ord1",
        machine_id="M2",
        sequence_number=2,
        start_minute=25,
        end_minute=60,
        processing_duration_minutes=35,
        slack_minutes=10,
        status=OperationStatus.IN_PROGRESS,
    )
    s_op3 = ScheduledOperation(
        operation_id="op2_1",
        order_id="ord2",
        machine_id="M1",
        sequence_number=1,
        start_minute=40,
        end_minute=70,
        processing_duration_minutes=30,
        slack_minutes=10,
        status=OperationStatus.PLANNED,
    )

    schedule = Schedule(
        id="SCHED-V1",
        workspace_id="ws-verif",
        status=ScheduleStatus.OPTIMAL,
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        kpis=ScheduleKPIs(
            makespan_minutes=70,
            total_weighted_tardiness=0,
            late_order_count=0,
            on_time_rate=100.0,
        ),
        scheduled_operations=[s_op1, s_op2, s_op3],
        verified=False,
        current_time_minute=clock,
    )
    return factory, schedule


def test_valid_lifecycle_schedule_passes_verification() -> None:
    """A valid schedule respecting plant clock and lifecycles passes all 8 invariants."""
    factory, schedule = _make_sample_lifecycle_setup()
    verifier = ScheduleVerifier()
    report = verifier.verify(factory, schedule)

    assert report.is_valid is True
    assert report.status == VerificationStatus.VERIFIED
    assert len(report.failed_rules) == 0


def test_corrupted_completed_start_fails_inv_2() -> None:
    """Mutant: If a completed operation's scheduled start differs from actual start, fails INV_2."""
    factory, schedule = _make_sample_lifecycle_setup()
    # Mutate op1_1 start from 0 to 5
    corrupt_ops = list(schedule.scheduled_operations)
    corrupt_ops[0] = ScheduledOperation(
        operation_id="op1_1",
        order_id="ord1",
        machine_id="M1",
        sequence_number=1,
        start_minute=5,  # Expected 0
        end_minute=25,
        processing_duration_minutes=20,
        slack_minutes=0,
        status=OperationStatus.COMPLETED,
    )
    schedule.scheduled_operations = corrupt_ops

    verifier = ScheduleVerifier()
    report = verifier.verify(factory, schedule)

    assert report.is_valid is False
    assert InvariantRule.INV_2_DURATION_MACHINE in report.failed_rules


def test_corrupted_in_progress_end_fails_inv_2() -> None:
    """Mutant: If in-progress scheduled end differs from clock + remaining, fails INV_2."""
    factory, schedule = _make_sample_lifecycle_setup()
    # Mutate op1_2 end from 60 to 55
    corrupt_ops = list(schedule.scheduled_operations)
    corrupt_ops[1] = ScheduledOperation(
        operation_id="op1_2",
        order_id="ord1",
        machine_id="M2",
        sequence_number=2,
        start_minute=25,
        end_minute=55,  # Expected clock 40 + remaining 20 = 60
        processing_duration_minutes=30,
        slack_minutes=15,
        status=OperationStatus.IN_PROGRESS,
    )
    schedule.scheduled_operations = corrupt_ops

    verifier = ScheduleVerifier()
    report = verifier.verify(factory, schedule)

    assert report.is_valid is False
    assert InvariantRule.INV_2_DURATION_MACHINE in report.failed_rules


def test_planned_op_starting_before_plant_clock_fails_inv_3() -> None:
    """Mutant: If a planned operation starts before factory plant clock, fails INV_3."""
    factory, schedule = _make_sample_lifecycle_setup()
    # Clock is 40. Set op2_1 start to 35.
    corrupt_ops = list(schedule.scheduled_operations)
    corrupt_ops[2] = ScheduledOperation(
        operation_id="op2_1",
        order_id="ord2",
        machine_id="M1",
        sequence_number=1,
        start_minute=35,  # < clock 40
        end_minute=65,
        processing_duration_minutes=30,
        slack_minutes=15,
        status=OperationStatus.PLANNED,
    )
    schedule.scheduled_operations = corrupt_ops

    verifier = ScheduleVerifier()
    report = verifier.verify(factory, schedule)

    assert report.is_valid is False
    assert InvariantRule.INV_3_RELEASE_TIME in report.failed_rules


def test_planned_op_overlapping_in_progress_lock_fails_inv_5() -> None:
    """Mutant: If a planned operation overlaps with in-progress operation on same machine, fails INV_5."""
    factory, schedule = _make_sample_lifecycle_setup()
    # Op 1_2 is on M2 from [25, 60). Schedule op2_1 on M2 from [50, 80) -> overlap [50, 60)
    corrupt_ops = list(schedule.scheduled_operations)
    corrupt_ops[2] = ScheduledOperation(
        operation_id="op2_1",
        order_id="ord2",
        machine_id="M2",  # Moved to M2
        sequence_number=1,
        start_minute=50,  # Overlaps [25, 60)
        end_minute=80,
        processing_duration_minutes=30,
        slack_minutes=0,
        status=OperationStatus.PLANNED,
    )
    schedule.scheduled_operations = corrupt_ops

    verifier = ScheduleVerifier()
    report = verifier.verify(factory, schedule)

    assert report.is_valid is False
    assert InvariantRule.INV_5_MACHINE_OVERLAP in report.failed_rules


def test_operation_status_mismatch_fails_inv_2() -> None:
    """Mutant: If scheduled operation reports a different status than factory, fails INV_2."""
    factory, schedule = _make_sample_lifecycle_setup()
    corrupt_ops = list(schedule.scheduled_operations)
    corrupt_ops[0] = ScheduledOperation(
        operation_id="op1_1",
        order_id="ord1",
        machine_id="M1",
        sequence_number=1,
        start_minute=0,
        end_minute=25,
        processing_duration_minutes=25,
        slack_minutes=0,
        status=OperationStatus.PLANNED,  # Factory defined as COMPLETED
    )
    schedule.scheduled_operations = corrupt_ops

    verifier = ScheduleVerifier()
    report = verifier.verify(factory, schedule)

    assert report.is_valid is False
    assert InvariantRule.INV_2_DURATION_MACHINE in report.failed_rules
