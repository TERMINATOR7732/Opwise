"""Deterministic metrics engine for Opwise discrete production scheduling.

Governed by SPECIFICATION.md Section 5.1, Section 5.2, and TEST_AND_RELEASE_PLAN.md Milestone 06.
Pure Python, zero OR-Tools, persistence, or web framework imports.
"""

from collections import defaultdict

from opwise.domain.downtime import normalize_machine_downtimes
from opwise.domain.entities import (
    Factory,
    MachineDowntime,
    Schedule,
    ScheduledOperation,
    ScheduleKPIs,
)
from opwise.domain.explanations import generate_schedule_explanations
from opwise.domain.metrics_types import (
    BOTTLENECK_DISCLAIMER,
    BottleneckAnalysis,
    MachineMetrics,
    OrderMetrics,
    ProductionScheduleMetrics,
    ScheduleExplanation,
)

__all__ = [
    "BOTTLENECK_DISCLAIMER",
    "BottleneckAnalysis",
    "MachineMetrics",
    "OrderMetrics",
    "ProductionScheduleMetrics",
    "ScheduleExplanation",
    "calculate_metrics_from_operations",
    "calculate_schedule_metrics",
    "reconcile_kpis",
]


def _compute_order_metrics(
    factory: Factory,
    scheduled_ops: list[ScheduledOperation],
) -> tuple[dict[str, OrderMetrics], int, int, int, float]:
    """Calculate per-order completion times, tardiness, and aggregate delivery rates."""
    ops_by_order: dict[str, list[ScheduledOperation]] = defaultdict(list)
    for op in scheduled_ops:
        ops_by_order[op.order_id].append(op)

    order_metrics: dict[str, OrderMetrics] = {}
    for order in factory.orders:
        order_ops = ops_by_order.get(order.id, [])
        c_j = max((op.end_minute for op in order_ops), default=0) if order_ops else 0
        d_j = order.due_date_minutes
        tardiness = max(0, c_j - d_j) if order_ops else 0
        w_j = order.tardiness_weight
        weighted = w_j * tardiness
        is_late = bool(order_ops and c_j > d_j)
        slack = max(0, d_j - c_j) if order_ops else 0
        proc_time = sum(op.processing_duration_minutes for op in order_ops)

        order_metrics[order.id] = OrderMetrics(
            order_id=order.id,
            order_code=order.order_code,
            completion_minute=c_j,
            due_date_minute=d_j,
            tardiness_minutes=tardiness,
            tardiness_weight=w_j,
            weighted_tardiness=weighted,
            is_late=is_late,
            slack_minutes=slack,
            operation_count=len(order_ops),
            total_processing_minutes=proc_time,
        )

    total_weighted_tardiness = sum(m.weighted_tardiness for m in order_metrics.values())
    late_orders = sum(1 for m in order_metrics.values() if m.is_late)
    total_orders = len(factory.orders)
    on_time_orders = total_orders - late_orders
    on_time_rate = (
        100.0 if total_orders == 0 else round((on_time_orders / total_orders) * 100.0, 2)
    )

    return order_metrics, total_weighted_tardiness, late_orders, on_time_orders, on_time_rate


def _compute_machine_metrics(
    factory: Factory,
    scheduled_ops: list[ScheduledOperation],
    makespan: int,
) -> dict[str, MachineMetrics]:
    """Calculate machine workload, downtime within makespan, idle time, and utilization."""
    norm = normalize_machine_downtimes(factory.downtimes)
    dts_by_machine: dict[str, list[MachineDowntime]] = defaultdict(list)
    for dt in norm.merged_downtimes:
        dts_by_machine[dt.machine_id].append(dt)

    ops_by_machine: dict[str, list[ScheduledOperation]] = defaultdict(list)
    for op in scheduled_ops:
        ops_by_machine[op.machine_id].append(op)

    metrics: dict[str, MachineMetrics] = {}
    for machine in factory.machines:
        m_ops = ops_by_machine.get(machine.id, [])
        workload = sum(op.processing_duration_minutes for op in m_ops)
        observed_downtime = 0
        for dt in dts_by_machine.get(machine.id, []):
            dt_start = max(0, dt.start_minute)
            dt_end = min(makespan, dt.end_minute)
            if dt_end > dt_start:
                observed_downtime += dt_end - dt_start

        available = max(0, makespan - observed_downtime)
        idle = max(0, available - workload)
        net_util = round((workload / available) * 100.0, 2) if available > 0 else 0.0
        gross_util = round((workload / makespan) * 100.0, 2) if makespan > 0 else 0.0

        metrics[machine.id] = MachineMetrics(
            machine_id=machine.id,
            workload_minutes=workload,
            downtime_minutes=observed_downtime,
            idle_minutes=idle,
            available_capacity_minutes=available,
            net_utilization_pct=net_util,
            gross_utilization_pct=gross_util,
            assigned_operation_count=len(m_ops),
        )

    return metrics


def _analyze_bottlenecks(machine_metrics: dict[str, MachineMetrics]) -> BottleneckAnalysis:
    """Identify primary candidate bottleneck workstation based on workload and utilization."""
    if not machine_metrics:
        return BottleneckAnalysis(None, [], 0, 0.0)

    # Deterministic ranking: workload desc, net_util desc, op_count desc, machine_id asc
    sorted_machines = sorted(
        machine_metrics.values(),
        key=lambda m: (
            -m.workload_minutes,
            -m.net_utilization_pct,
            -m.assigned_operation_count,
            m.machine_id,
        ),
    )
    ranked_ids = [m.machine_id for m in sorted_machines]
    top = sorted_machines[0]

    if top.workload_minutes == 0:
        return BottleneckAnalysis(None, ranked_ids, 0, 0.0)

    return BottleneckAnalysis(
        primary_bottleneck_machine_id=top.machine_id,
        ranked_machines=ranked_ids,
        highest_workload_minutes=top.workload_minutes,
        highest_net_utilization_pct=top.net_utilization_pct,
    )


def calculate_metrics_from_operations(
    factory: Factory,
    scheduled_operations: list[ScheduledOperation],
    schedule_id: str = "SCHED-ANALYTICAL",
) -> ProductionScheduleMetrics:
    """Calculate complete analytical metrics and mathematical explanations from scheduled operations."""
    makespan = max((op.end_minute for op in scheduled_operations), default=0)

    (
        order_metrics,
        total_weighted_tardiness,
        late_orders,
        on_time_orders,
        on_time_rate,
    ) = _compute_order_metrics(factory, scheduled_operations)

    machine_metrics = _compute_machine_metrics(factory, scheduled_operations, makespan)
    bottleneck = _analyze_bottlenecks(machine_metrics)

    explanations = generate_schedule_explanations(
        schedule_id=schedule_id,
        makespan=makespan,
        scheduled_ops=scheduled_operations,
        total_weighted_tardiness=total_weighted_tardiness,
        late_order_count=late_orders,
        on_time_order_count=on_time_orders,
        total_order_count=len(factory.orders),
        on_time_rate_pct=on_time_rate,
        order_metrics=order_metrics,
        machine_metrics=machine_metrics,
        bottleneck=bottleneck,
    )

    return ProductionScheduleMetrics(
        makespan_minutes=makespan,
        total_weighted_tardiness=total_weighted_tardiness,
        late_order_count=late_orders,
        on_time_order_count=on_time_orders,
        total_order_count=len(factory.orders),
        on_time_rate_pct=on_time_rate,
        order_metrics=order_metrics,
        machine_metrics=machine_metrics,
        bottleneck=bottleneck,
        explanations=explanations,
    )


def calculate_schedule_metrics(
    factory: Factory,
    schedule: Schedule,
) -> ProductionScheduleMetrics:
    """Calculate complete analytical metrics and mathematical explanations for a schedule."""
    return calculate_metrics_from_operations(
        factory=factory,
        scheduled_operations=schedule.scheduled_operations,
        schedule_id=schedule.id,
    )


def reconcile_kpis(kpis: ScheduleKPIs, metrics: ProductionScheduleMetrics) -> bool:
    """Verify that schedule KPIs match newly calculated analytical metrics."""
    return (
        kpis.makespan_minutes == metrics.makespan_minutes
        and kpis.total_weighted_tardiness == metrics.total_weighted_tardiness
        and kpis.late_order_count == metrics.late_order_count
        and abs(kpis.on_time_rate - metrics.on_time_rate_pct) <= 1e-4
    )
