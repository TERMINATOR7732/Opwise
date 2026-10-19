"""Unit tests for execution-aware CP-SAT scheduling (Milestone 15B).

Governed by Milestone 15B specification:
- PLANNED: scheduled on [start, start + duration) with start >= max(t_0, release_time)
- IN_PROGRESS: actual_start <= t_0 preserved, future lock on [t_0, t_0 + remaining)
- COMPLETED: actual_start and actual_end preserved, not rescheduled
- Machine exclusivity and downtime non-collision
- Precedence across mixed lifecycle statuses
- All-completed deterministic state handling
"""

from opwise.domain.entities import (
    Factory,
    Machine,
    MachineDowntime,
    ObjectiveMode,
    Operation,
    OperationStatus,
    ProductionOrder,
    ScheduleStatus,
)
from opwise.solver.engine import CPSATScheduler


def _make_machine(m_id: str = "M1") -> Machine:
    return Machine(id=m_id, name=f"Workstation {m_id}")


def test_planned_operations_respect_plant_clock() -> None:
    """Planned operations must not be scheduled prior to factory plant clock t_0."""
    clock = 50
    m1 = _make_machine("M1")
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.PLANNED,
    )
    order1 = ProductionOrder(
        id="ord1",
        order_code="J1",
        release_time_minutes=10,  # release is before clock
        due_date_minutes=100,
        tardiness_weight=1,
        operations=[op1],
    )
    factory = Factory(
        workspace_id="ws-test",
        machines=[m1],
        downtimes=[],
        orders=[order1],
        current_time_minute=clock,
    )

    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True
    assert result.schedule.current_time_minute == clock
    sched_op = result.schedule.scheduled_operations[0]
    assert sched_op.start_minute >= clock
    assert sched_op.start_minute == clock  # Earliest feasible is t_0 = 50
    assert sched_op.end_minute == clock + 20
    assert sched_op.status == OperationStatus.PLANNED


def test_in_progress_operation_future_lock_and_successor_precedence() -> None:
    """In-progress op keeps actual start <= t_0, locks machine [t_0, t_0 + r), and gates successor."""
    clock = 40
    m1 = _make_machine("M1")
    m2 = _make_machine("M2")

    # Order 1: Op 1 is IN_PROGRESS on M1 (started at 20, remaining 30 -> finishes at 40 + 30 = 70)
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=40,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=20,
        remaining_duration_minutes=30,
    )
    # Op 2 is PLANNED on M2 (duration 25). Must start >= 70 (completion of op1)
    op2 = Operation(
        id="op2",
        order_id="ord1",
        sequence_number=2,
        machine_id="M2",
        processing_duration_minutes=25,
        status=OperationStatus.PLANNED,
    )
    order1 = ProductionOrder(
        id="ord1",
        order_code="J1",
        release_time_minutes=10,
        due_date_minutes=120,
        tardiness_weight=1,
        operations=[op1, op2],
    )

    # Order 2: Op 3 is PLANNED on M1 (duration 20). Competes with Op 1 on M1.
    # Must wait until Op 1 future lock ends at 70!
    op3 = Operation(
        id="op3",
        order_id="ord2",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.PLANNED,
    )
    order2 = ProductionOrder(
        id="ord2",
        order_code="J2",
        release_time_minutes=0,
        due_date_minutes=120,
        tardiness_weight=1,
        operations=[op3],
    )

    factory = Factory(
        workspace_id="ws-test",
        machines=[m1, m2],
        downtimes=[],
        orders=[order1, order2],
        current_time_minute=clock,
    )

    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True

    ops_by_id = {op.operation_id: op for op in result.schedule.scheduled_operations}

    # Op 1 checks
    s_op1 = ops_by_id["op1"]
    assert s_op1.status == OperationStatus.IN_PROGRESS
    assert s_op1.start_minute == 20
    assert s_op1.end_minute == clock + 30  # 70
    assert s_op1.processing_duration_minutes == 70 - 20  # 50

    # Op 2 checks (successor on M2, precedence from Op 1)
    s_op2 = ops_by_id["op2"]
    assert s_op2.status == OperationStatus.PLANNED
    assert s_op2.start_minute >= 70
    assert s_op2.end_minute == s_op2.start_minute + 25

    # Op 3 checks (competes on M1, must not overlap Op 1 future lock [40, 70))
    s_op3 = ops_by_id["op3"]
    assert s_op3.status == OperationStatus.PLANNED
    assert s_op3.start_minute >= 70
    assert s_op3.end_minute == s_op3.start_minute + 20


def test_completed_operation_preserved_without_future_machine_blocking() -> None:
    """Completed op has historical start/end preserved, and does not block machine after clock."""
    clock = 60
    m1 = _make_machine("M1")

    # Op 1 completed on M1 from [10, 50)
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=35,
        status=OperationStatus.COMPLETED,
        actual_start_minute=10,
        actual_end_minute=50,
    )
    # Op 2 in same order is PLANNED on M1 (duration 20).
    # Since Op 1 completed at 50 <= clock (60), Op 2 can start right at clock 60!
    op2 = Operation(
        id="op2",
        order_id="ord1",
        sequence_number=2,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.PLANNED,
    )
    order1 = ProductionOrder(
        id="ord1",
        order_code="J1",
        release_time_minutes=0,
        due_date_minutes=100,
        tardiness_weight=1,
        operations=[op1, op2],
    )

    factory = Factory(
        workspace_id="ws-test",
        machines=[m1],
        downtimes=[],
        orders=[order1],
        current_time_minute=clock,
    )

    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True

    ops_by_id = {op.operation_id: op for op in result.schedule.scheduled_operations}
    s_op1 = ops_by_id["op1"]
    assert s_op1.status == OperationStatus.COMPLETED
    assert s_op1.start_minute == 10
    assert s_op1.end_minute == 50

    s_op2 = ops_by_id["op2"]
    assert s_op2.status == OperationStatus.PLANNED
    assert s_op2.start_minute == clock  # 60
    assert s_op2.end_minute == 80


def test_in_progress_conflicting_with_future_downtime_is_infeasible() -> None:
    """If an in-progress operation's future lock [t_0, t_0 + r) collides with future downtime, INFEASIBLE."""
    clock = 30
    m1 = _make_machine("M1")

    # In-progress on M1: started at 10, remaining 40 -> future lock [30, 70)
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=50,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=10,
        remaining_duration_minutes=40,
    )
    order1 = ProductionOrder(
        id="ord1",
        order_code="J1",
        release_time_minutes=0,
        due_date_minutes=100,
        tardiness_weight=1,
        operations=[op1],
    )

    # Future downtime on M1: [40, 60), which directly collides with future lock [30, 70)
    dt1 = MachineDowntime(id="dt1", machine_id="M1", start_minute=40, end_minute=60, reason="Repair")

    factory = Factory(
        workspace_id="ws-test",
        machines=[m1],
        downtimes=[dt1],
        orders=[order1],
        current_time_minute=clock,
    )

    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.INFEASIBLE
    assert result.schedule is None


def test_all_completed_factory_returns_optimal_deterministic_schedule() -> None:
    """When all operations across all orders are COMPLETED, returns OPTIMAL schedule instantly."""
    clock = 100
    m1 = _make_machine("M1")
    m2 = _make_machine("M2")

    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.COMPLETED,
        actual_start_minute=10,
        actual_end_minute=40,
    )
    op2 = Operation(
        id="op2",
        order_id="ord1",
        sequence_number=2,
        machine_id="M2",
        processing_duration_minutes=30,
        status=OperationStatus.COMPLETED,
        actual_start_minute=45,
        actual_end_minute=75,
    )
    order1 = ProductionOrder(
        id="ord1",
        order_code="J1",
        release_time_minutes=0,
        due_date_minutes=80,
        tardiness_weight=2,
        operations=[op1, op2],
    )

    factory = Factory(
        workspace_id="ws-test",
        machines=[m1, m2],
        downtimes=[],
        orders=[order1],
        current_time_minute=clock,
    )

    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True
    assert result.schedule.kpis.makespan_minutes == 75
    assert result.schedule.kpis.total_weighted_tardiness == 0  # 75 <= due 80
    assert result.schedule.kpis.on_time_rate == 100.0
    assert result.schedule.current_time_minute == clock


def test_lexicographic_solve_with_mixed_lifecycle() -> None:
    """Two-stage lexicographic optimization succeeds and respects bounds with mixed lifecycles."""
    clock = 30
    m1 = _make_machine("M1")

    # Order 1: Op 1 COMPLETED [0, 20), Op 2 PLANNED (duration 20, due 60)
    op1_1 = Operation(
        id="op1_1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.COMPLETED,
        actual_start_minute=0,
        actual_end_minute=20,
    )
    op1_2 = Operation(
        id="op1_2",
        order_id="ord1",
        sequence_number=2,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.PLANNED,
    )
    order1 = ProductionOrder(
        id="ord1",
        order_code="J1",
        release_time_minutes=0,
        due_date_minutes=60,
        tardiness_weight=5,
        operations=[op1_1, op1_2],
    )

    # Order 2: Op 2_1 IN_PROGRESS [20, clock=30), remaining 15 (finishes at 45, due 45)
    op2_1 = Operation(
        id="op2_1",
        order_id="ord2",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=25,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=20,
        remaining_duration_minutes=15,
    )
    order2 = ProductionOrder(
        id="ord2",
        order_code="J2",
        release_time_minutes=15,
        due_date_minutes=45,
        tardiness_weight=1,
        operations=[op2_1],
    )

    factory = Factory(
        workspace_id="ws-test",
        machines=[m1],
        downtimes=[],
        orders=[order1, order2],
        current_time_minute=clock,
    )

    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True
    assert result.stage1_status == ScheduleStatus.OPTIMAL
    assert result.stage2_status == ScheduleStatus.OPTIMAL
    assert result.schedule.kpis.total_weighted_tardiness == 25
    assert result.schedule.kpis.makespan_minutes == 65


def test_chain_completed_to_in_progress() -> None:
    """Precedence Chain 5: Completed predecessor followed by In-Progress successor."""
    clock = 40
    m1 = _make_machine("M1")
    m2 = _make_machine("M2")

    # Order 1: Op 1 COMPLETED [0, 25) on M1, Op 2 IN_PROGRESS [25, clock=40) remaining 20 on M2
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=25,
        status=OperationStatus.COMPLETED,
        actual_start_minute=0,
        actual_end_minute=25,
    )
    op2 = Operation(
        id="op2",
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
        due_date_minutes=80,
        tardiness_weight=1,
        operations=[op1, op2],
    )

    factory = Factory(
        workspace_id="ws-test",
        machines=[m1, m2],
        downtimes=[],
        orders=[order1],
        current_time_minute=clock,
    )

    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True

    ops_by_id = {op.operation_id: op for op in result.schedule.scheduled_operations}
    assert ops_by_id["op1"].end_minute == 25
    assert ops_by_id["op2"].start_minute == 25
    assert ops_by_id["op2"].end_minute == clock + 20  # 60
    assert ops_by_id["op2"].start_minute >= ops_by_id["op1"].end_minute


def test_chain_multiple_completed_to_planned() -> None:
    """Precedence Chain 6: Multiple completed operations preceding a planned successor."""
    clock = 50
    m1 = _make_machine("M1")
    m2 = _make_machine("M2")

    # Order 1: Op 1 COMPLETED [0, 15) on M1, Op 2 COMPLETED [15, 30) on M2, Op 3 PLANNED (duration 25) on M1
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=15,
        status=OperationStatus.COMPLETED,
        actual_start_minute=0,
        actual_end_minute=15,
    )
    op2 = Operation(
        id="op2",
        order_id="ord1",
        sequence_number=2,
        machine_id="M2",
        processing_duration_minutes=15,
        status=OperationStatus.COMPLETED,
        actual_start_minute=15,
        actual_end_minute=30,
    )
    op3 = Operation(
        id="op3",
        order_id="ord1",
        sequence_number=3,
        machine_id="M1",
        processing_duration_minutes=25,
        status=OperationStatus.PLANNED,
    )
    order1 = ProductionOrder(
        id="ord1",
        order_code="J1",
        release_time_minutes=0,
        due_date_minutes=100,
        tardiness_weight=1,
        operations=[op1, op2, op3],
    )

    factory = Factory(
        workspace_id="ws-test",
        machines=[m1, m2],
        downtimes=[],
        orders=[order1],
        current_time_minute=clock,
    )

    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True

    ops_by_id = {op.operation_id: op for op in result.schedule.scheduled_operations}
    assert ops_by_id["op1"].end_minute == 15
    assert ops_by_id["op2"].end_minute == 30
    # Op 3 must start >= max(clock=50, op2.end=30) = 50
    assert ops_by_id["op3"].start_minute == clock  # 50
    assert ops_by_id["op3"].end_minute == 75


def test_chain_completed_to_in_progress_to_planned() -> None:
    """Precedence Chain 7: Completed -> In-Progress -> Planned chain."""
    clock = 35
    m1 = _make_machine("M1")
    m2 = _make_machine("M2")

    # Order 1: Op 1 COMPLETED [0, 20) on M1, Op 2 IN_PROGRESS [20, 35) remaining 15 on M2 -> ends 50, Op 3 PLANNED (dur 20) on M1
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
        machine_id="M2",
        processing_duration_minutes=30,
        status=OperationStatus.IN_PROGRESS,
        actual_start_minute=20,
        remaining_duration_minutes=15,
    )
    op3 = Operation(
        id="op3",
        order_id="ord1",
        sequence_number=3,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.PLANNED,
    )
    order1 = ProductionOrder(
        id="ord1",
        order_code="J1",
        release_time_minutes=0,
        due_date_minutes=100,
        tardiness_weight=1,
        operations=[op1, op2, op3],
    )

    factory = Factory(
        workspace_id="ws-test",
        machines=[m1, m2],
        downtimes=[],
        orders=[order1],
        current_time_minute=clock,
    )

    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True

    ops_by_id = {op.operation_id: op for op in result.schedule.scheduled_operations}
    assert ops_by_id["op1"].end_minute == 20
    assert ops_by_id["op2"].start_minute == 20
    assert ops_by_id["op2"].end_minute == clock + 15  # 50
    # Op 3 cannot start until Op 2 expected completion at 50
    assert ops_by_id["op3"].start_minute >= 50
    assert ops_by_id["op3"].start_minute == 50
    assert ops_by_id["op3"].end_minute == 70


def test_chain_successor_with_later_clock_or_release() -> None:
    """Precedence Chain 9: Successor whose earliest start is constrained by plant clock beyond predecessor end."""
    clock = 60
    m1 = _make_machine("M1")
    m2 = _make_machine("M2")

    # Op 1 completed early at [0, 20) on M1. Clock is 60.
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
        machine_id="M2",
        processing_duration_minutes=20,
        status=OperationStatus.PLANNED,
    )
    order1 = ProductionOrder(
        id="ord1",
        order_code="J1",
        release_time_minutes=0,
        due_date_minutes=100,
        tardiness_weight=1,
        operations=[op1, op2],
    )

    factory = Factory(
        workspace_id="ws-test",
        machines=[m1, m2],
        downtimes=[],
        orders=[order1],
        current_time_minute=clock,
    )

    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    ops_by_id = {op.operation_id: op for op in result.schedule.scheduled_operations}
    # Predecessor completed at 20, but Op 2 cannot start before clock 60
    assert ops_by_id["op2"].start_minute == clock  # 60
    assert ops_by_id["op2"].end_minute == 80


def test_chain_exact_boundary_contact() -> None:
    """Precedence Chain 10: Predecessor completion exactly at successor start boundary."""
    clock = 40
    m1 = _make_machine("M1")

    # Op 1 completed [10, 40) on M1. Clock is 40.
    op1 = Operation(
        id="op1",
        order_id="ord1",
        sequence_number=1,
        machine_id="M1",
        processing_duration_minutes=30,
        status=OperationStatus.COMPLETED,
        actual_start_minute=10,
        actual_end_minute=40,
    )
    # Op 2 is PLANNED (duration 20) on M1. Meets Op 1 at exact boundary 40!
    op2 = Operation(
        id="op2",
        order_id="ord1",
        sequence_number=2,
        machine_id="M1",
        processing_duration_minutes=20,
        status=OperationStatus.PLANNED,
    )
    order1 = ProductionOrder(
        id="ord1",
        order_code="J1",
        release_time_minutes=0,
        due_date_minutes=100,
        tardiness_weight=1,
        operations=[op1, op2],
    )

    factory = Factory(
        workspace_id="ws-test",
        machines=[m1],
        downtimes=[],
        orders=[order1],
        current_time_minute=clock,
    )

    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True

    ops_by_id = {op.operation_id: op for op in result.schedule.scheduled_operations}
    assert ops_by_id["op1"].end_minute == 40
    assert ops_by_id["op2"].start_minute == 40
    assert ops_by_id["op2"].end_minute == 60

