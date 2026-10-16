"""Evidence-backed mathematical explanation generator for Opwise production schedules.

Governed by SPECIFICATION.md Section 5.2 and ADR-006.
Generates deterministic explanations citing exact quantities, formulas, and thresholds.
"""

from opwise.domain.entities import ScheduledOperation
from opwise.domain.metrics_types import (
    BOTTLENECK_DISCLAIMER,
    BottleneckAnalysis,
    MachineMetrics,
    OrderMetrics,
    ScheduleExplanation,
)


def _explain_makespan(
    schedule_id: str,
    makespan: int,
    scheduled_ops: list[ScheduledOperation],
) -> ScheduleExplanation:
    """Generate makespan origin and final-operation explanation."""
    if makespan == 0 or not scheduled_ops:
        return ScheduleExplanation(
            category="MAKESPAN",
            entity_type="Schedule",
            entity_id=schedule_id,
            summary="Schedule makespan is 0 minutes for empty or no-work factory.",
            measured_value=0,
            threshold_or_target=None,
            mathematical_formula="C_max = max(C_{j,k}) - 0",
            reason="No production operations scheduled; makespan is 0 minutes from origin t=0.",
        )

    last_op = min(
        (op for op in scheduled_ops if op.end_minute == makespan),
        key=lambda o: (o.order_id, o.sequence_number),
    )
    return ScheduleExplanation(
        category="MAKESPAN",
        entity_type="Schedule",
        entity_id=schedule_id,
        summary=(
            f"Schedule makespan is {makespan} minutes, determined by completion of "
            f"operation {last_op.operation_id} (Order {last_op.order_id}) at minute {makespan}."
        ),
        measured_value=makespan,
        threshold_or_target=None,
        mathematical_formula="C_max = max(C_{j,k}) - 0",
        reason=f"Final operation {last_op.operation_id} on machine {last_op.machine_id} completes at minute {makespan}.",
    )


def _explain_delivery_performance(
    schedule_id: str,
    total_weighted_tardiness: int,
    late_order_count: int,
    on_time_order_count: int,
    total_order_count: int,
    on_time_rate_pct: float,
) -> ScheduleExplanation:
    """Generate plant delivery and weighted tardiness explanation."""
    tardiness_reason = (
        "All scheduled production orders completed on or before their agreed customer due dates."
        if late_order_count == 0
        else f"{late_order_count} out of {total_order_count} orders completed after their contracted due dates."
    )
    return ScheduleExplanation(
        category="DELIVERY_PERFORMANCE",
        entity_type="Schedule",
        entity_id=schedule_id,
        summary=(
            f"Plant delivery performance: {on_time_rate_pct:.2f}% on-time "
            f"({on_time_order_count}/{total_order_count} orders), total weighted tardiness: "
            f"{total_weighted_tardiness} penalty points ({late_order_count} late orders)."
        ),
        measured_value=total_weighted_tardiness,
        threshold_or_target=0,
        mathematical_formula="sum(w_j * max(0, C_j - d_j))",
        reason=tardiness_reason,
    )


def _explain_order_tardiness(order_metrics: dict[str, OrderMetrics]) -> list[ScheduleExplanation]:
    """Generate deterministic order completion and tardiness explanations."""
    explanations: list[ScheduleExplanation] = []
    for o_id in sorted(order_metrics.keys()):
        om = order_metrics[o_id]
        if om.is_late:
            summary = (
                f"Order {om.order_id} ({om.order_code}) completed at minute {om.completion_minute}, "
                f"which is {om.tardiness_minutes} minutes after its due date of minute {om.due_date_minute}, "
                f"incurring {om.weighted_tardiness} penalty points ({om.tardiness_minutes} min x weight {om.tardiness_weight})."
            )
            reason = f"Completion at minute {om.completion_minute} exceeds due date {om.due_date_minute} by {om.tardiness_minutes} minutes."
        elif om.operation_count > 0:
            summary = (
                f"Order {om.order_id} ({om.order_code}) completed at minute {om.completion_minute}, "
                f"on-time before its due date of minute {om.due_date_minute} with {om.slack_minutes} minutes "
                f"of terminal slack (0 penalty points)."
            )
            reason = f"Completed on or before due date {om.due_date_minute} (slack: {om.slack_minutes} min)."
        else:
            summary = f"Order {om.order_id} ({om.order_code}) has 0 operations scheduled."
            reason = "No operations defined or scheduled for this order."

        explanations.append(
            ScheduleExplanation(
                category="ORDER_TARDINESS",
                entity_type="Order",
                entity_id=om.order_id,
                summary=summary,
                measured_value=om.completion_minute,
                threshold_or_target=om.due_date_minute,
                mathematical_formula="T_j = max(0, C_j - d_j); Weighted = w_j * T_j",
                reason=reason,
            )
        )
    return explanations


def _explain_machine_utilization(machine_metrics: dict[str, MachineMetrics]) -> list[ScheduleExplanation]:
    """Generate machine workload, downtime, and capacity utilization explanations."""
    explanations: list[ScheduleExplanation] = []
    for m_id in sorted(machine_metrics.keys()):
        mm = machine_metrics[m_id]
        explanations.append(
            ScheduleExplanation(
                category="MACHINE_UTILIZATION",
                entity_type="Machine",
                entity_id=mm.machine_id,
                summary=(
                    f"Machine {mm.machine_id} active machining: {mm.workload_minutes}m, "
                    f"maintenance downtime: {mm.downtime_minutes}m, idle: {mm.idle_minutes}m "
                    f"out of available capacity {mm.available_capacity_minutes}m "
                    f"(net utilization: {mm.net_utilization_pct:.2f}%, gross utilization: {mm.gross_utilization_pct:.2f}%)."
                ),
                measured_value=mm.net_utilization_pct,
                threshold_or_target=100.0,
                mathematical_formula="U_m = W_m / (C_max - D_m) * 100%",
                reason=f"Workload {mm.workload_minutes}m divided by available capacity {mm.available_capacity_minutes}m.",
            )
        )
    return explanations


def _explain_bottleneck(
    schedule_id: str,
    bottleneck: BottleneckAnalysis,
    machine_metrics: dict[str, MachineMetrics],
) -> ScheduleExplanation:
    """Generate candidate bottleneck resource explanation with disclaimer."""
    if bottleneck.primary_bottleneck_machine_id is None:
        return ScheduleExplanation(
            category="BOTTLENECK",
            entity_type="Schedule",
            entity_id=schedule_id,
            summary="No machine bottleneck identified (zero active workload across all workstations).",
            measured_value=0,
            threshold_or_target=None,
            mathematical_formula="argmax_m (W_m, U_m^net)",
            reason="Factory is in no-work state or has zero scheduled operation duration.",
        )

    b_id = bottleneck.primary_bottleneck_machine_id
    b_mm = machine_metrics[b_id]
    return ScheduleExplanation(
        category="BOTTLENECK",
        entity_type="Machine",
        entity_id=b_id,
        summary=(
            f"Machine {b_id} identified as primary capacity candidate with highest active workload "
            f"of {b_mm.workload_minutes} minutes (net utilization: {b_mm.net_utilization_pct:.2f}%, "
            f"gross utilization: {b_mm.gross_utilization_pct:.2f}%, {b_mm.assigned_operation_count} assigned operations)."
        ),
        measured_value=b_mm.workload_minutes,
        threshold_or_target=None,
        mathematical_formula="argmax_m (W_m, U_m^net)",
        reason=BOTTLENECK_DISCLAIMER,
    )


def generate_schedule_explanations(
    schedule_id: str,
    makespan: int,
    scheduled_ops: list[ScheduledOperation],
    total_weighted_tardiness: int,
    late_order_count: int,
    on_time_order_count: int,
    total_order_count: int,
    on_time_rate_pct: float,
    order_metrics: dict[str, OrderMetrics],
    machine_metrics: dict[str, MachineMetrics],
    bottleneck: BottleneckAnalysis,
) -> list[ScheduleExplanation]:
    """Assemble all structured, deterministic, evidence-based mathematical explanations."""
    explanations: list[ScheduleExplanation] = []
    explanations.append(_explain_makespan(schedule_id, makespan, scheduled_ops))
    explanations.append(
        _explain_delivery_performance(
            schedule_id,
            total_weighted_tardiness,
            late_order_count,
            on_time_order_count,
            total_order_count,
            on_time_rate_pct,
        )
    )
    explanations.extend(_explain_order_tardiness(order_metrics))
    explanations.extend(_explain_machine_utilization(machine_metrics))
    explanations.append(_explain_bottleneck(schedule_id, bottleneck, machine_metrics))
    return explanations
