"""Unit tests for edge-case hardening, oversubscription, and KPI reconciliation.

Governed by SPECIFICATION.md Section 5.1, Section 5.2, and TEST_AND_RELEASE_PLAN.md Milestone 06.
Verifies machine oversubscription alerts, on-time delivery classification, and KPI reconciliation safety.
"""

from typing import cast

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
    calculate_metrics_from_operations,
    calculate_schedule_metrics,
    reconcile_kpis,
)
from opwise.domain.metrics_types import ProductionScheduleMetrics


def _build_simple_factory_and_schedule() -> tuple[Factory, Schedule]:
    """Build a baseline 1-machine, 1-order factory and valid schedule."""
    op = Operation("OP-1", "ORD-1", 1, "M1", 30)
    order = ProductionOrder("ORD-1", "J1", 0, 50, 1, operations=[op])
    factory = Factory("WS-HARDENING-1", machines=[Machine("M1", "CNC Mill")], downtimes=[], orders=[order])
    scheduled_ops = [ScheduledOperation("OP-1", "ORD-1", "M1", 1, 0, 30, 30, slack_minutes=20)]
    schedule = Schedule(
        id="SCHED-HARDENING-1",
        workspace_id="WS-HARDENING-1",
        status=ScheduleStatus.OPTIMAL,
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        kpis=ScheduleKPIs(30, 0, 0, 100.0),
        scheduled_operations=scheduled_ops,
        verified=True,
    )
    return factory, schedule


def test_machine_oversubscription_detection_and_warning() -> None:
    """When a candidate schedule has overlapping ops causing workload > available capacity."""
    factory = Factory(
        workspace_id="WS-OVERSUB",
        machines=[Machine("M1", "CNC Mill")],
        downtimes=[MachineDowntime("DT-1", "M1", 10, 20, "Breakdown")],
        orders=[
            ProductionOrder("O1", "J1", 0, 50, 1, [Operation("OP-1", "O1", 1, "M1", 20)]),
            ProductionOrder("O2", "J2", 0, 50, 1, [Operation("OP-2", "O2", 1, "M1", 20)]),
        ],
    )
    # Both ops run in [0, 20], creating an overlap of 40m workload in a 20m makespan
    overlapping_ops = [
        ScheduledOperation("OP-1", "O1", "M1", 1, 0, 20, 20),
        ScheduledOperation("OP-2", "O2", "M1", 1, 0, 20, 20),
    ]
    metrics = calculate_metrics_from_operations(factory, overlapping_ops)

    m1_metrics = metrics.machine_metrics["M1"]
    assert m1_metrics.is_oversubscribed is True
    assert m1_metrics.workload_minutes == 40
    # Makespan = 20, downtime in [10, 20] is 10m -> available = 10m
    assert m1_metrics.available_capacity_minutes == 10
    assert m1_metrics.idle_minutes == 0
    assert m1_metrics.net_utilization_pct == 400.0

    # Verify that the explanation issues a prominent warning
    m1_exp = next(e for e in metrics.explanations if e.category == "MACHINE_UTILIZATION")
    assert "WARNING: Machine M1 workload 40m exceeds available capacity" in m1_exp.summary
    assert "overlapping operations or downtime collisions" in m1_exp.reason


def test_on_time_order_flag_and_empty_order_distinction() -> None:
    """Orders with operations are flagged is_on_time=True if completed by due date."""
    factory = Factory(
        workspace_id="WS-DELIV",
        machines=[Machine("M1", "CNC Mill")],
        downtimes=[],
        orders=[
            ProductionOrder("O_ON_TIME", "J1", 0, 50, 1, [Operation("OP-1", "O_ON_TIME", 1, "M1", 20)]),
            ProductionOrder("O_LATE", "J2", 0, 15, 1, [Operation("OP-2", "O_LATE", 1, "M1", 25)]),
            ProductionOrder("O_EMPTY", "J3", 0, 100, 1, []),
        ],
    )
    ops = [
        ScheduledOperation("OP-1", "O_ON_TIME", "M1", 1, 0, 20, 20),
        ScheduledOperation("OP-2", "O_LATE", "M1", 1, 20, 45, 25),
    ]
    metrics = calculate_metrics_from_operations(factory, ops)

    assert metrics.order_metrics["O_ON_TIME"].is_on_time is True
    assert metrics.order_metrics["O_ON_TIME"].is_late is False

    assert metrics.order_metrics["O_LATE"].is_on_time is False
    assert metrics.order_metrics["O_LATE"].is_late is True

    # Empty order: neither on-time nor late
    assert metrics.order_metrics["O_EMPTY"].is_on_time is False
    assert metrics.order_metrics["O_EMPTY"].is_late is False

    # 1 on-time out of 3 total orders -> 33.33%
    assert metrics.on_time_order_count == 1
    assert metrics.late_order_count == 1
    assert metrics.on_time_rate_pct == 33.33


def test_reconcile_kpis_rejects_invalid_types() -> None:
    """reconcile_kpis returns False when passed non-KPI objects."""
    _, schedule = _build_simple_factory_and_schedule()
    metrics = calculate_schedule_metrics(_build_simple_factory_and_schedule()[0], schedule)

    assert reconcile_kpis(cast(ScheduleKPIs, "invalid_str"), metrics) is False
    assert reconcile_kpis(schedule.kpis, cast(ProductionScheduleMetrics, {})) is False
    assert reconcile_kpis(cast(ScheduleKPIs, None), metrics) is False


def test_reconcile_kpis_rejects_negative_or_nan_values() -> None:
    """reconcile_kpis returns False if any metric contains negative, NaN, or out-of-range values."""
    factory, schedule = _build_simple_factory_and_schedule()
    metrics = calculate_schedule_metrics(factory, schedule)

    # Negative makespan
    bad_kpis = ScheduleKPIs(makespan_minutes=-10, total_weighted_tardiness=0, late_order_count=0, on_time_rate=100.0)
    assert reconcile_kpis(bad_kpis, metrics) is False

    # Negative tardiness
    bad_kpis2 = ScheduleKPIs(makespan_minutes=30, total_weighted_tardiness=-5, late_order_count=0, on_time_rate=100.0)
    assert reconcile_kpis(bad_kpis2, metrics) is False

    # NaN on_time_rate
    bad_kpis3 = ScheduleKPIs(makespan_minutes=30, total_weighted_tardiness=0, late_order_count=0, on_time_rate=float("nan"))
    assert reconcile_kpis(bad_kpis3, metrics) is False

    # Inf on_time_rate
    bad_kpis4 = ScheduleKPIs(makespan_minutes=30, total_weighted_tardiness=0, late_order_count=0, on_time_rate=float("inf"))
    assert reconcile_kpis(bad_kpis4, metrics) is False

    # Out-of-range percentage (> 100)
    bad_kpis5 = ScheduleKPIs(makespan_minutes=30, total_weighted_tardiness=0, late_order_count=0, on_time_rate=105.0)
    assert reconcile_kpis(bad_kpis5, metrics) is False
