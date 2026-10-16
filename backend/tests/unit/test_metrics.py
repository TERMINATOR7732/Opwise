"""Unit tests for the deterministic metrics engine and mathematical explanations.

Governed by SPECIFICATION.md Section 5.1, Section 5.2, and TEST_AND_RELEASE_PLAN.md Milestone 06.
Verifies analytical calculations, zero-denominator guards, bottleneck identification, and explanations.
"""

import sys

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
from opwise.domain.metrics import (
    BOTTLENECK_DISCLAIMER,
    calculate_metrics_from_operations,
    calculate_schedule_metrics,
    reconcile_kpis,
)


def _build_test_factory_and_schedule() -> tuple[Factory, Schedule]:
    """Construct a hand-calculable 3-machine, 2-order shop with planned maintenance."""
    factory = Factory(
        workspace_id="WS-METRICS-1",
        machines=[
            Machine(id="M1", name="CNC Mill"),
            Machine(id="M2", name="Lathe"),
            Machine(id="M3", name="Grinder"),
        ],
        downtimes=[
            MachineDowntime(id="DT-1", machine_id="M1", start_minute=60, end_minute=90, reason="Maintenance")
        ],
        orders=[
            ProductionOrder(
                id="ORD-1", order_code="J1", release_time_minutes=0, due_date_minutes=100, tardiness_weight=2,
                operations=[
                    Operation(id="OP-1-1", order_id="ORD-1", sequence_number=1, machine_id="M1", processing_duration_minutes=30),
                    Operation(id="OP-1-2", order_id="ORD-1", sequence_number=2, machine_id="M2", processing_duration_minutes=45),
                ],
            ),
            ProductionOrder(
                id="ORD-2", order_code="J2", release_time_minutes=10, due_date_minutes=150, tardiness_weight=3,
                operations=[
                    Operation(id="OP-2-1", order_id="ORD-2", sequence_number=1, machine_id="M2", processing_duration_minutes=40),
                    Operation(id="OP-2-2", order_id="ORD-2", sequence_number=2, machine_id="M3", processing_duration_minutes=50),
                ],
            ),
        ],
    )
    scheduled_ops = [
        ScheduledOperation("OP-1-1", "ORD-1", "M1", 1, 0, 30, 30, slack_minutes=0),
        ScheduledOperation("OP-1-2", "ORD-1", "M2", 2, 30, 75, 45, slack_minutes=25),
        ScheduledOperation("OP-2-1", "ORD-2", "M2", 1, 75, 115, 40, slack_minutes=0),
        ScheduledOperation("OP-2-2", "ORD-2", "M3", 2, 115, 165, 50, slack_minutes=0),
    ]
    schedule = Schedule(
        id="SCHED-MTR-1",
        workspace_id="WS-METRICS-1",
        status=ScheduleStatus.OPTIMAL,
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        kpis=ScheduleKPIs(makespan_minutes=165, total_weighted_tardiness=45, late_order_count=1, on_time_rate=50.0),
        scheduled_operations=scheduled_ops,
        verified=True,
    )
    return factory, schedule


def test_makespan_and_approved_time_origin() -> None:
    """Case 1: Makespan is measured from relative grid origin t=0 to max completion minute."""
    factory = Factory(
        workspace_id="WS-ORIGIN",
        machines=[Machine("M1", "M1")],
        downtimes=[],
        orders=[ProductionOrder("O1", "J1", 0, 150, 1, [Operation("OP1", "O1", 1, "M1", 40)])],
    )
    # Operation starts at minute 30 and finishes at minute 70. Makespan is 70, not 40.
    ops = [ScheduledOperation("OP1", "O1", "M1", 1, 30, 70, 40)]
    metrics = calculate_metrics_from_operations(factory, ops)

    assert metrics.makespan_minutes == 70
    assert metrics.order_metrics["O1"].completion_minute == 70
    assert metrics.order_metrics["O1"].slack_minutes == 80  # due 150 - 70


def test_multiple_orders_tardiness_and_weighted_reconciliation() -> None:
    """Case 2 & 3: Hand-calculated order completion, tardiness, and weighted penalty sum."""
    factory, schedule = _build_test_factory_and_schedule()
    metrics = calculate_schedule_metrics(factory, schedule)

    # ORD-1: C_1 = 75 <= 100 -> on-time, tardiness 0, weight 2 -> weighted 0
    ord1 = metrics.order_metrics["ORD-1"]
    assert ord1.completion_minute == 75
    assert ord1.tardiness_minutes == 0
    assert ord1.weighted_tardiness == 0
    assert ord1.is_late is False
    assert ord1.slack_minutes == 25

    # ORD-2: C_2 = 165 > 150 -> late by 15m, weight 3 -> weighted 45
    ord2 = metrics.order_metrics["ORD-2"]
    assert ord2.completion_minute == 165
    assert ord2.tardiness_minutes == 15
    assert ord2.weighted_tardiness == 45
    assert ord2.is_late is True
    assert ord2.slack_minutes == 0

    assert metrics.total_weighted_tardiness == 45
    assert metrics.late_order_count == 1
    assert metrics.on_time_order_count == 1
    assert metrics.on_time_rate_pct == 50.0


def test_machine_workload_downtime_idle_and_utilization() -> None:
    """Case 4 & 6: Machine capacity separation: active workload, downtime, idle, net vs gross."""
    factory, schedule = _build_test_factory_and_schedule()
    metrics = calculate_schedule_metrics(factory, schedule)

    # Machine M1: 30m op, 30m downtime inside [0, 165], available 135, idle 105
    m1 = metrics.machine_metrics["M1"]
    assert m1.workload_minutes == 30
    assert m1.downtime_minutes == 30
    assert m1.available_capacity_minutes == 135
    assert m1.idle_minutes == 105
    assert m1.net_utilization_pct == 22.22  # 30 / 135 * 100
    assert m1.gross_utilization_pct == 18.18  # 30 / 165 * 100
    assert m1.assigned_operation_count == 1

    # Machine M2: 85m ops (45 + 40), 0m downtime, available 165, idle 80
    m2 = metrics.machine_metrics["M2"]
    assert m2.workload_minutes == 85
    assert m2.downtime_minutes == 0
    assert m2.available_capacity_minutes == 165
    assert m2.idle_minutes == 80
    assert m2.net_utilization_pct == 51.52  # 85 / 165 * 100
    assert m2.gross_utilization_pct == 51.52
    assert m2.assigned_operation_count == 2

    # Machine M3: 50m ops, 0m downtime, available 165, idle 115
    m3 = metrics.machine_metrics["M3"]
    assert m3.workload_minutes == 50
    assert m3.downtime_minutes == 0
    assert m3.available_capacity_minutes == 165
    assert m3.idle_minutes == 115
    assert m3.net_utilization_pct == 30.30
    assert m3.gross_utilization_pct == 30.30


def test_bottleneck_ranking_and_deterministic_ordering() -> None:
    """Case 5: Machine load ranking and primary candidate identification with disclaimer."""
    factory, schedule = _build_test_factory_and_schedule()
    metrics = calculate_schedule_metrics(factory, schedule)

    bottleneck = metrics.bottleneck
    assert bottleneck.primary_bottleneck_machine_id == "M2"
    assert bottleneck.ranked_machines == ["M2", "M3", "M1"]  # Workloads: 85, 50, 30
    assert bottleneck.highest_workload_minutes == 85
    assert bottleneck.highest_net_utilization_pct == 51.52
    assert bottleneck.disclaimer == BOTTLENECK_DISCLAIMER


def test_tied_bottlenecks_lexicographic_tie_break() -> None:
    """Case 5b: Identical workload and utilization breaks ties deterministically by machine_id."""
    factory = Factory(
        workspace_id="WS-TIE",
        machines=[Machine("M_ZETA", "Zeta"), Machine("M_ALPHA", "Alpha")],
        downtimes=[],
        orders=[
            ProductionOrder("O1", "J1", 0, 100, 1, [Operation("OP1", "O1", 1, "M_ZETA", 40)]),
            ProductionOrder("O2", "J2", 0, 100, 1, [Operation("OP2", "O2", 1, "M_ALPHA", 40)]),
        ],
    )
    ops = [
        ScheduledOperation("OP1", "O1", "M_ZETA", 1, 0, 40, 40),
        ScheduledOperation("OP2", "O2", "M_ALPHA", 1, 0, 40, 40),
    ]
    metrics = calculate_metrics_from_operations(factory, ops)

    # Both have workload 40 and net util 100.0%. "M_ALPHA" < "M_ZETA" alphabetically
    assert metrics.bottleneck.ranked_machines == ["M_ALPHA", "M_ZETA"]
    assert metrics.bottleneck.primary_bottleneck_machine_id == "M_ALPHA"


def test_empty_and_no_work_state_schedules() -> None:
    """Case 7: Factory with machines but 0 orders or empty schedule yields 0 metrics safely."""
    factory = Factory(workspace_id="WS-EMPTY", machines=[Machine("M1", "M1")], downtimes=[], orders=[])
    metrics = calculate_metrics_from_operations(factory, [])

    assert metrics.makespan_minutes == 0
    assert metrics.total_weighted_tardiness == 0
    assert metrics.late_order_count == 0
    assert metrics.on_time_order_count == 0
    assert metrics.on_time_rate_pct == 100.0
    assert metrics.bottleneck.primary_bottleneck_machine_id is None
    assert metrics.machine_metrics["M1"].net_utilization_pct == 0.0
    assert metrics.machine_metrics["M1"].gross_utilization_pct == 0.0


def test_zero_denominator_when_downtime_fills_makespan() -> None:
    """Case 8: When C_max - D_m <= 0, net utilization is clamped to 0.0% without ZeroDivisionError."""
    factory = Factory(
        workspace_id="WS-FULL-DT",
        machines=[Machine("M1", "M1"), Machine("M2", "M2")],
        downtimes=[MachineDowntime("DT1", "M1", 0, 100, "Full Downtime")],
        orders=[ProductionOrder("O1", "J1", 0, 100, 1, [Operation("OP1", "O1", 1, "M2", 50)])],
    )
    # M2 runs [0, 50). Makespan is 50. M1 has downtime [0, 100), observing 50 min in [0, 50].
    # Available on M1: max(0, 50 - 50) = 0.
    ops = [ScheduledOperation("OP1", "O1", "M2", 1, 0, 50, 50)]
    metrics = calculate_metrics_from_operations(factory, ops)

    m1 = metrics.machine_metrics["M1"]
    assert m1.workload_minutes == 0
    assert m1.downtime_minutes == 50
    assert m1.available_capacity_minutes == 0
    assert m1.idle_minutes == 0
    assert m1.net_utilization_pct == 0.0
    assert m1.gross_utilization_pct == 0.0


def test_overlapping_and_partial_downtimes_normalization() -> None:
    """Case 9: Overlapping downtimes do not double count, and downtimes past makespan clamp."""
    factory = Factory(
        workspace_id="WS-DT-NORM",
        machines=[Machine("M1", "M1")],
        downtimes=[
            MachineDowntime("DT1", "M1", 20, 50),
            MachineDowntime("DT2", "M1", 40, 70),  # Overlaps [20, 50) -> merged [20, 70) = 50m
            MachineDowntime("DT3", "M1", 80, 150),  # Clamped to makespan 100 -> [80, 100) = 20m
        ],
        orders=[ProductionOrder("O1", "J1", 0, 100, 1, [Operation("OP1", "O1", 1, "M1", 20)])],
    )
    ops = [ScheduledOperation("OP1", "O1", "M1", 1, 0, 20, 20), ScheduledOperation("OP2", "O1", "M1", 2, 70, 80, 10)]
    # Max end_minute is 80, but let's add a dummy op to reach 100:
    ops.append(ScheduledOperation("OP3", "O1", "M1", 3, 99, 100, 1))
    metrics = calculate_metrics_from_operations(factory, ops)

    m1 = metrics.machine_metrics["M1"]
    assert metrics.makespan_minutes == 100
    # Merged DT1+DT2 [20, 70) = 50m. DT3 [80, 150) clipped to 100 = 20m. Total = 70m.
    assert m1.downtime_minutes == 70
    assert m1.available_capacity_minutes == 30  # 100 - 70
    assert m1.workload_minutes == 31  # 20 + 10 + 1
    assert m1.idle_minutes == 0


def test_explanations_traceability_and_evidence() -> None:
    """Case 10: Mathematical explanations contain exact quantities, formulas, and entities."""
    factory, schedule = _build_test_factory_and_schedule()
    metrics = calculate_schedule_metrics(factory, schedule)

    categories = {exp.category for exp in metrics.explanations}
    assert "MAKESPAN" in categories
    assert "DELIVERY_PERFORMANCE" in categories
    assert "ORDER_TARDINESS" in categories
    assert "MACHINE_UTILIZATION" in categories
    assert "BOTTLENECK" in categories

    # Find the bottleneck explanation
    b_exp = next(e for e in metrics.explanations if e.category == "BOTTLENECK")
    assert b_exp.entity_id == "M2"
    assert b_exp.measured_value == 85
    assert b_exp.reason == BOTTLENECK_DISCLAIMER

    # Find late order explanation
    late_exp = next(e for e in metrics.explanations if e.category == "ORDER_TARDINESS" and e.entity_id == "ORD-2")
    assert late_exp.measured_value == 165
    assert late_exp.threshold_or_target == 150
    assert "exceeds due date 150 by 15 minutes" in late_exp.reason


def test_stable_output_ordering() -> None:
    """Case 11: Repeated calls produce identical explanation ordering and string contents."""
    factory, schedule = _build_test_factory_and_schedule()
    run1 = calculate_schedule_metrics(factory, schedule)
    run2 = calculate_schedule_metrics(factory, schedule)

    assert [e.summary for e in run1.explanations] == [e.summary for e in run2.explanations]
    assert run1.bottleneck.ranked_machines == run2.bottleneck.ranked_machines


def test_reconciliation_of_aggregates_and_kpis() -> None:
    """Case 13: Aggregates strictly equal component sums, and reconcile_kpis returns True."""
    factory, schedule = _build_test_factory_and_schedule()
    metrics = calculate_schedule_metrics(factory, schedule)

    # 1. Total weighted tardiness is exact sum of per-order weighted tardiness
    sum_tardiness = sum(om.weighted_tardiness for om in metrics.order_metrics.values())
    assert metrics.total_weighted_tardiness == sum_tardiness

    # 2. Late orders count matches boolean flag sum
    count_late = sum(1 for om in metrics.order_metrics.values() if om.is_late)
    assert metrics.late_order_count == count_late

    # 3. Sum of machine workloads matches total operation durations
    total_ops_duration = sum(op.processing_duration_minutes for op in schedule.scheduled_operations)
    total_machine_workload = sum(mm.workload_minutes for mm in metrics.machine_metrics.values())
    assert total_machine_workload == total_ops_duration

    # 4. KPI reconciliation helper returns True
    assert reconcile_kpis(schedule.kpis, metrics) is True


def test_independence_from_or_tools() -> None:
    """Case 14: Module calculates all metrics without importing OR-Tools into domain namespace."""
    assert "ortools" not in sys.modules or "ortools" not in globals()
    # Confirm metrics module does not import ortools
    import opwise.domain.metrics as m_mod
    assert not hasattr(m_mod, "cp_model")
    assert not hasattr(m_mod, "ortools")


def test_order_without_operations_and_empty_machines() -> None:
    """Case 15: Edge conditions: order without operations and empty machines list."""
    factory = Factory(
        workspace_id="WS-EMPTY-MACH",
        machines=[],
        downtimes=[],
        orders=[ProductionOrder("O_EMPTY", "J_EMPTY", 0, 100, 1, operations=[])],
    )
    metrics = calculate_metrics_from_operations(factory, [])

    assert metrics.order_metrics["O_EMPTY"].operation_count == 0
    assert metrics.order_metrics["O_EMPTY"].completion_minute == 0
    assert metrics.bottleneck.primary_bottleneck_machine_id is None
    order_exp = next(e for e in metrics.explanations if e.entity_id == "O_EMPTY")
    assert "0 operations scheduled" in order_exp.summary
