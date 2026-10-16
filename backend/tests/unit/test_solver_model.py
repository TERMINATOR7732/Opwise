"""Unit and constraint tests for Opwise CP-SAT scheduling model formulation.

Governed by SOLVER_MODEL.md Section 4 and TEST_AND_RELEASE_PLAN.md Milestone 04.
Exercises genuine CP-SAT interval models without mocking.
"""

from opwise.domain.entities import (
    Factory,
    Machine,
    MachineDowntime,
    ObjectiveMode,
    Operation,
    ProductionOrder,
    ScheduleStatus,
)
from opwise.solver.engine import CPSATScheduler


def test_single_operation_schedule_optimal() -> None:
    """Case 1: A single-operation order solves to proven optimal at minute 0."""
    factory = Factory(
        workspace_id="WS-TEST-1",
        machines=[Machine(id="M1", name="CNC Mill")],
        downtimes=[],
        orders=[
            ProductionOrder(
                id="ORD-1",
                order_code="J1",
                release_time_minutes=0,
                due_date_minutes=50,
                tardiness_weight=1,
                operations=[
                    Operation(
                        id="OP-1",
                        order_id="ORD-1",
                        sequence_number=1,
                        machine_id="M1",
                        processing_duration_minutes=20,
                    )
                ],
            )
        ],
    )
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True
    assert result.verification_report is not None
    assert result.verification_report.is_valid is True
    assert len(result.schedule.scheduled_operations) == 1

    op = result.schedule.scheduled_operations[0]
    assert op.start_minute == 0
    assert op.end_minute == 20
    assert op.slack_minutes == 30  # Due date 50 - end 20
    assert result.schedule.kpis.makespan_minutes == 20
    assert result.schedule.kpis.total_weighted_tardiness == 0


def test_multi_operation_order_precedence() -> None:
    """Case 2: Linear sequence within an order strictly enforces S_{j, k+1} >= C_{j, k}."""
    factory = Factory(
        workspace_id="WS-TEST-2",
        machines=[Machine(id="M1", name="Mill"), Machine(id="M2", name="Lathe")],
        downtimes=[],
        orders=[
            ProductionOrder(
                id="ORD-1",
                order_code="J1",
                release_time_minutes=0,
                due_date_minutes=100,
                tardiness_weight=1,
                operations=[
                    Operation(id="OP-1", order_id="ORD-1", sequence_number=1, machine_id="M1", processing_duration_minutes=30),
                    Operation(id="OP-2", order_id="ORD-1", sequence_number=2, machine_id="M2", processing_duration_minutes=40),
                ],
            )
        ],
    )
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    ops = {op.operation_id: op for op in result.schedule.scheduled_operations}
    assert ops["OP-1"].end_minute <= ops["OP-2"].start_minute
    assert ops["OP-1"].start_minute == 0
    assert ops["OP-1"].end_minute == 30
    assert ops["OP-2"].start_minute == 30
    assert ops["OP-2"].end_minute == 70
    assert result.schedule.kpis.makespan_minutes == 70


def test_machine_competition_no_overlap() -> None:
    """Case 3: Two orders competing for one machine serialize without overlap."""
    factory = Factory(
        workspace_id="WS-TEST-3",
        machines=[Machine(id="M1", name="Mill")],
        downtimes=[],
        orders=[
            ProductionOrder(
                id="ORD-1", order_code="J1", release_time_minutes=0, due_date_minutes=100, tardiness_weight=1,
                operations=[Operation(id="OP-1", order_id="ORD-1", sequence_number=1, machine_id="M1", processing_duration_minutes=25)],
            ),
            ProductionOrder(
                id="ORD-2", order_code="J2", release_time_minutes=0, due_date_minutes=100, tardiness_weight=1,
                operations=[Operation(id="OP-2", order_id="ORD-2", sequence_number=1, machine_id="M1", processing_duration_minutes=35)],
            ),
        ],
    )
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.kpis.makespan_minutes == 60  # 25 + 35
    ops = sorted(result.schedule.scheduled_operations, key=lambda o: o.start_minute)
    assert ops[0].end_minute <= ops[1].start_minute


def test_concurrent_operations_different_machines() -> None:
    """Case 4: Independent orders on distinct machines execute in parallel."""
    factory = Factory(
        workspace_id="WS-TEST-4",
        machines=[Machine(id="M1", name="Mill"), Machine(id="M2", name="Lathe")],
        downtimes=[],
        orders=[
            ProductionOrder(
                id="ORD-1", order_code="J1", release_time_minutes=0, due_date_minutes=100, tardiness_weight=1,
                operations=[Operation(id="OP-1", order_id="ORD-1", sequence_number=1, machine_id="M1", processing_duration_minutes=40)],
            ),
            ProductionOrder(
                id="ORD-2", order_code="J2", release_time_minutes=0, due_date_minutes=100, tardiness_weight=1,
                operations=[Operation(id="OP-2", order_id="ORD-2", sequence_number=1, machine_id="M2", processing_duration_minutes=40)],
            ),
        ],
    )
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.kpis.makespan_minutes == 40  # Both run [0, 40)
    for op in result.schedule.scheduled_operations:
        assert op.start_minute == 0
        assert op.end_minute == 40


def test_downtime_displaces_operation() -> None:
    """Case 5: Unyielding downtime [0, 50) forces operation to start at minute 50."""
    factory = Factory(
        workspace_id="WS-TEST-5",
        machines=[Machine(id="M1", name="Mill")],
        downtimes=[MachineDowntime(id="DT-1", machine_id="M1", start_minute=0, end_minute=50, reason="Maintenance")],
        orders=[
            ProductionOrder(
                id="ORD-1", order_code="J1", release_time_minutes=0, due_date_minutes=100, tardiness_weight=1,
                operations=[Operation(id="OP-1", order_id="ORD-1", sequence_number=1, machine_id="M1", processing_duration_minutes=30)],
            )
        ],
    )
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    op = result.schedule.scheduled_operations[0]
    assert op.start_minute == 50
    assert op.end_minute == 80
    assert result.schedule.kpis.makespan_minutes == 80


def test_exact_boundary_contact_non_collision() -> None:
    """Case 6: Operation [0, 30) touching downtime [30, 60) touching op [60, 90) does not collide."""
    factory = Factory(
        workspace_id="WS-TEST-6",
        machines=[Machine(id="M1", name="Mill")],
        downtimes=[MachineDowntime(id="DT-1", machine_id="M1", start_minute=30, end_minute=60)],
        orders=[
            ProductionOrder(
                id="ORD-1", order_code="J1", release_time_minutes=0, due_date_minutes=120, tardiness_weight=1,
                operations=[Operation(id="OP-1", order_id="ORD-1", sequence_number=1, machine_id="M1", processing_duration_minutes=30)],
            ),
            ProductionOrder(
                id="ORD-2", order_code="J2", release_time_minutes=0, due_date_minutes=120, tardiness_weight=1,
                operations=[Operation(id="OP-2", order_id="ORD-2", sequence_number=1, machine_id="M1", processing_duration_minutes=30)],
            ),
        ],
    )
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.kpis.makespan_minutes == 90
    ops = sorted(result.schedule.scheduled_operations, key=lambda o: o.start_minute)
    assert ops[0].start_minute == 0
    assert ops[0].end_minute == 30  # Exact boundary contact with DT [30, 60)
    assert ops[1].start_minute == 60  # Exact boundary contact with DT [30, 60)
    assert ops[1].end_minute == 90


def test_genuine_infeasible_problem() -> None:
    """Case 7: Operation cannot fit within safe horizon due to precedence and downtime partition."""
    # OP1 needs 100m on M2 (finishes at 100). OP2 needs 100m on M1 (starts >= 100).
    # M1 downtime [150, 250) partitions [100, 300] horizon into two 50m slots. 100m op cannot fit!
    factory = Factory(
        workspace_id="WS-TEST-7",
        machines=[Machine(id="M1", name="M1"), Machine(id="M2", name="M2")],
        downtimes=[MachineDowntime(id="DT-1", machine_id="M1", start_minute=150, end_minute=250)],
        orders=[
            ProductionOrder(
                id="ORD-1", order_code="J1", release_time_minutes=0, due_date_minutes=300, tardiness_weight=1,
                operations=[
                    Operation(id="OP-1", order_id="ORD-1", sequence_number=1, machine_id="M2", processing_duration_minutes=100),
                    Operation(id="OP-2", order_id="ORD-1", sequence_number=2, machine_id="M1", processing_duration_minutes=100),
                ],
            )
        ],
    )
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.INFEASIBLE
    assert result.schedule is None
