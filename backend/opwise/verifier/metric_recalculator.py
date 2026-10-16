"""Analytical metric recalculation and metric concordance auditor for Opwise.

Governed by SPECIFICATION.md Section 5.1 and SOLVER_MODEL.md Section 6.
Pure Python, zero OR-Tools or persistence imports.
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
from opwise.verifier.verification_types import (
    InvariantRule,
    InvariantViolation,
    MachineUtilizationMetrics,
    RecomputedMetrics,
)


def compute_machine_utilizations(
    factory: Factory,
    scheduled_ops: list[ScheduledOperation],
    makespan: int,
) -> dict[str, MachineUtilizationMetrics]:
    """Calculate workload, downtime within makespan window, idle, and utilization rates."""
    norm = normalize_machine_downtimes(factory.downtimes)
    dts_by_machine: dict[str, list[MachineDowntime]] = defaultdict(list)
    for dt in norm.merged_downtimes:
        dts_by_machine[dt.machine_id].append(dt)

    ops_by_machine: dict[str, list[ScheduledOperation]] = defaultdict(list)
    for op in scheduled_ops:
        ops_by_machine[op.machine_id].append(op)

    metrics: dict[str, MachineUtilizationMetrics] = {}
    for machine in factory.machines:
        m_ops = ops_by_machine.get(machine.id, [])
        workload = sum(op.processing_duration_minutes for op in m_ops)
        observed_downtime = 0
        for dt in dts_by_machine.get(machine.id, []):
            dt_start = max(0, dt.start_minute)
            dt_end = min(makespan, dt.end_minute)
            if dt_end > dt_start:
                observed_downtime += dt_end - dt_start

        available = makespan - observed_downtime
        idle = max(0, available - workload)
        net_util = round((workload / available) * 100.0, 2) if available > 0 else 0.0
        gross_util = round((workload / makespan) * 100.0, 2) if makespan > 0 else 0.0

        metrics[machine.id] = MachineUtilizationMetrics(
            machine_id=machine.id,
            workload_minutes=workload,
            downtime_minutes=observed_downtime,
            idle_minutes=idle,
            net_utilization_pct=net_util,
            gross_utilization_pct=gross_util,
        )
    return metrics


def recompute_schedule_metrics(
    factory: Factory,
    scheduled_ops: list[ScheduledOperation],
) -> RecomputedMetrics:
    """Pure analytical recalculation of makespan, weighted tardiness, and utilization."""
    makespan = max((op.end_minute for op in scheduled_ops), default=0)
    ops_by_order: dict[str, list[ScheduledOperation]] = defaultdict(list)
    for op in scheduled_ops:
        ops_by_order[op.order_id].append(op)

    total_tardiness = 0
    late_orders = 0
    total_orders = len(factory.orders)

    for order in factory.orders:
        order_ops = ops_by_order.get(order.id, [])
        c_j = max((op.end_minute for op in order_ops), default=0) if order_ops else 0
        tardiness = max(0, c_j - order.due_date_minutes) if order_ops else 0
        if order_ops and c_j > order.due_date_minutes:
            late_orders += 1
        total_tardiness += order.tardiness_weight * tardiness

    on_time_rate = 100.0 if total_orders == 0 else round(((total_orders - late_orders) / total_orders) * 100.0, 2)
    machine_utils = compute_machine_utilizations(factory, scheduled_ops, makespan)

    return RecomputedMetrics(
        makespan_minutes=makespan,
        total_weighted_tardiness=total_tardiness,
        late_order_count=late_orders,
        on_time_rate=on_time_rate,
        machine_utilizations=machine_utils,
    )


def check_candidate_kpi_concordance(
    schedule: Schedule,
    recomputed: RecomputedMetrics,
) -> list[InvariantViolation]:
    """Audit Invariant 8: Compare claimed KPIs with independently calculated metrics."""
    violations: list[InvariantViolation] = []
    kpis = schedule.kpis

    if kpis.makespan_minutes != recomputed.makespan_minutes:
        violations.append(
            InvariantViolation(
                rule=InvariantRule.INV_8_METRIC_CONCORDANCE,
                entity_type="Schedule",
                entity_id=schedule.id,
                message=f"Makespan discrepancy: claimed {kpis.makespan_minutes}m, recomputed {recomputed.makespan_minutes}m.",
                expected=recomputed.makespan_minutes,
                actual=kpis.makespan_minutes,
            )
        )
    if kpis.total_weighted_tardiness != recomputed.total_weighted_tardiness:
        violations.append(
            InvariantViolation(
                rule=InvariantRule.INV_8_METRIC_CONCORDANCE,
                entity_type="Schedule",
                entity_id=schedule.id,
                message=f"Tardiness discrepancy: claimed {kpis.total_weighted_tardiness}, recomputed {recomputed.total_weighted_tardiness}.",
                expected=recomputed.total_weighted_tardiness,
                actual=kpis.total_weighted_tardiness,
            )
        )
    if kpis.late_order_count != recomputed.late_order_count:
        violations.append(
            InvariantViolation(
                rule=InvariantRule.INV_8_METRIC_CONCORDANCE,
                entity_type="Schedule",
                entity_id=schedule.id,
                message=f"Late count discrepancy: claimed {kpis.late_order_count}, recomputed {recomputed.late_order_count}.",
                expected=recomputed.late_order_count,
                actual=kpis.late_order_count,
            )
        )
    if abs(kpis.on_time_rate - recomputed.on_time_rate) > 1e-4:
        violations.append(
            InvariantViolation(
                rule=InvariantRule.INV_8_METRIC_CONCORDANCE,
                entity_type="Schedule",
                entity_id=schedule.id,
                message=f"On-time rate discrepancy: claimed {kpis.on_time_rate}%, recomputed {recomputed.on_time_rate}%.",
                expected=recomputed.on_time_rate,
                actual=kpis.on_time_rate,
            )
        )
    return violations


def check_stage1_preservation(
    schedule: Schedule,
    recomputed: RecomputedMetrics,
    stage1_bound: int | None,
) -> list[InvariantViolation]:
    """Audit Invariant 8 (Lexicographic): Validate Stage 2 does not degrade Stage 1 optimum."""
    if stage1_bound is None:
        return []

    if recomputed.total_weighted_tardiness > stage1_bound:
        return [
            InvariantViolation(
                rule=InvariantRule.INV_8_STAGE1_PRESERVATION,
                entity_type="Schedule",
                entity_id=schedule.id,
                message=(
                    f"Stage-1 preservation breached: recomputed tardiness {recomputed.total_weighted_tardiness} "
                    f"exceeds Stage-1 optimal bound {stage1_bound}."
                ),
                expected=stage1_bound,
                actual=recomputed.total_weighted_tardiness,
            )
        ]
    return []


def metrics_concordant(kpis: ScheduleKPIs, recomputed: RecomputedMetrics) -> bool:
    """Helper to check if all four primary schedule KPIs match recomputed metrics."""
    return (
        kpis.makespan_minutes == recomputed.makespan_minutes
        and kpis.total_weighted_tardiness == recomputed.total_weighted_tardiness
        and kpis.late_order_count == recomputed.late_order_count
        and abs(kpis.on_time_rate - recomputed.on_time_rate) < 1e-4
    )
