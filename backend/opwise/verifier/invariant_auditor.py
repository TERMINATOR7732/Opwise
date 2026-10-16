"""Clean-room invariant auditor for physical shop floor constraints (Invariants 1-7).

Governed by SOLVER_MODEL.md Section 6 and PROJECT_RULES.md Section 6.3.
Decoupled completely from OR-Tools and persistence.
"""

from collections import defaultdict

from opwise.domain.downtime import (
    calculate_effective_horizon,
    normalize_machine_downtimes,
)
from opwise.domain.entities import (
    Factory,
    MachineDowntime,
    Operation,
    ScheduledOperation,
)
from opwise.verifier.verification_types import (
    InvariantRule,
    InvariantViolation,
)


def audit_cardinality(
    factory: Factory,
    scheduled_ops: list[ScheduledOperation],
) -> list[InvariantViolation]:
    """Invariant 1: Every factory operation must appear exactly once in the schedule."""
    violations: list[InvariantViolation] = []
    factory_ops = {op.id for order in factory.orders for op in order.operations}
    seen_ops: set[str] = set()

    for op in scheduled_ops:
        if op.operation_id in seen_ops:
            violations.append(
                InvariantViolation(
                    rule=InvariantRule.INV_1_CARDINALITY,
                    entity_type="Operation",
                    entity_id=op.operation_id,
                    message=f"Duplicate scheduled operation '{op.operation_id}'.",
                )
            )
        seen_ops.add(op.operation_id)
        if op.operation_id not in factory_ops:
            violations.append(
                InvariantViolation(
                    rule=InvariantRule.INV_1_CARDINALITY,
                    entity_type="Operation",
                    entity_id=op.operation_id,
                    message=f"Scheduled operation '{op.operation_id}' not found in factory definition.",
                )
            )

    for f_op_id in factory_ops:
        if f_op_id not in seen_ops:
            violations.append(
                InvariantViolation(
                    rule=InvariantRule.INV_1_CARDINALITY,
                    entity_type="Operation",
                    entity_id=f_op_id,
                    message=f"Factory operation '{f_op_id}' is missing from schedule.",
                )
            )
    return violations


def audit_duration_and_machine(
    factory: Factory,
    scheduled_ops: list[ScheduledOperation],
) -> list[InvariantViolation]:
    """Invariant 2: C - S == p and machine matches required workstation."""
    violations: list[InvariantViolation] = []
    op_lookup: dict[str, Operation] = {
        op.id: op for order in factory.orders for op in order.operations
    }

    for s_op in scheduled_ops:
        f_op = op_lookup.get(s_op.operation_id)
        if not f_op:
            continue

        actual_duration = s_op.end_minute - s_op.start_minute
        if actual_duration != f_op.processing_duration_minutes:
            violations.append(
                InvariantViolation(
                    rule=InvariantRule.INV_2_DURATION_MACHINE,
                    entity_type="Operation",
                    entity_id=s_op.operation_id,
                    message=(
                        f"Operation '{s_op.operation_id}' duration mismatch: "
                        f"span [{s_op.start_minute}, {s_op.end_minute}) = {actual_duration}m, "
                        f"expected {f_op.processing_duration_minutes}m."
                    ),
                    expected=f_op.processing_duration_minutes,
                    actual=actual_duration,
                )
            )

        if s_op.machine_id != f_op.machine_id:
            violations.append(
                InvariantViolation(
                    rule=InvariantRule.INV_2_DURATION_MACHINE,
                    entity_type="Operation",
                    entity_id=s_op.operation_id,
                    message=(
                        f"Operation '{s_op.operation_id}' scheduled on machine '{s_op.machine_id}', "
                        f"expected required machine '{f_op.machine_id}'."
                    ),
                    expected=f_op.machine_id,
                    actual=s_op.machine_id,
                )
            )
    return violations


def audit_release_times(
    factory: Factory,
    scheduled_ops: list[ScheduledOperation],
) -> list[InvariantViolation]:
    """Invariant 3: First operation of an order must start at or after release time."""
    violations: list[InvariantViolation] = []
    ops_by_order: dict[str, list[ScheduledOperation]] = defaultdict(list)
    for s_op in scheduled_ops:
        ops_by_order[s_op.order_id].append(s_op)

    for order in factory.orders:
        order_ops = ops_by_order.get(order.id, [])
        if not order_ops:
            continue
        first_op = min(order_ops, key=lambda op: op.sequence_number)
        if first_op.start_minute < order.release_time_minutes:
            violations.append(
                InvariantViolation(
                    rule=InvariantRule.INV_3_RELEASE_TIME,
                    entity_type="Order",
                    entity_id=order.id,
                    message=(
                        f"Order '{order.id}' first operation '{first_op.operation_id}' starts at minute "
                        f"{first_op.start_minute}, prior to release time {order.release_time_minutes}."
                    ),
                    expected=order.release_time_minutes,
                    actual=first_op.start_minute,
                )
            )
    return violations


def audit_precedence(
    factory: Factory,
    scheduled_ops: list[ScheduledOperation],
) -> list[InvariantViolation]:
    """Invariant 4: Intra-order operations must execute sequentially without overlap."""
    violations: list[InvariantViolation] = []
    ops_by_order: dict[str, list[ScheduledOperation]] = defaultdict(list)
    for s_op in scheduled_ops:
        ops_by_order[s_op.order_id].append(s_op)

    for order in factory.orders:
        order_ops = sorted(ops_by_order.get(order.id, []), key=lambda op: op.sequence_number)
        for i in range(len(order_ops) - 1):
            curr_op = order_ops[i]
            next_op = order_ops[i + 1]
            if next_op.start_minute < curr_op.end_minute:
                violations.append(
                    InvariantViolation(
                        rule=InvariantRule.INV_4_PRECEDENCE,
                        entity_type="Operation",
                        entity_id=next_op.operation_id,
                        message=(
                            f"Precedence violation in order '{order.id}': operation '{next_op.operation_id}' "
                            f"starts at minute {next_op.start_minute} before preceding operation "
                            f"'{curr_op.operation_id}' ends at minute {curr_op.end_minute}."
                        ),
                        expected=curr_op.end_minute,
                        actual=next_op.start_minute,
                    )
                )
    return violations


def audit_machine_exclusivity(
    scheduled_ops: list[ScheduledOperation],
) -> list[InvariantViolation]:
    """Invariant 5: Operations on the same machine must not overlap in half-open time."""
    violations: list[InvariantViolation] = []
    ops_by_machine: dict[str, list[ScheduledOperation]] = defaultdict(list)
    for s_op in scheduled_ops:
        ops_by_machine[s_op.machine_id].append(s_op)

    for machine_id, m_ops in ops_by_machine.items():
        sorted_ops = sorted(m_ops, key=lambda op: (op.start_minute, op.end_minute))
        for i in range(len(sorted_ops) - 1):
            curr_op = sorted_ops[i]
            next_op = sorted_ops[i + 1]
            if next_op.start_minute < curr_op.end_minute:
                violations.append(
                    InvariantViolation(
                        rule=InvariantRule.INV_5_MACHINE_OVERLAP,
                        entity_type="Machine",
                        entity_id=machine_id,
                        message=(
                            f"Machine '{machine_id}' overlap collision: operation '{next_op.operation_id}' "
                            f"starts at minute {next_op.start_minute} before operation '{curr_op.operation_id}' "
                            f"completes at minute {curr_op.end_minute}."
                        ),
                        expected=curr_op.end_minute,
                        actual=next_op.start_minute,
                    )
                )
    return violations


def audit_downtime_respect(
    factory: Factory,
    scheduled_ops: list[ScheduledOperation],
) -> list[InvariantViolation]:
    """Invariant 6: Operations must not collide with canonical merged downtimes."""
    violations: list[InvariantViolation] = []
    norm = normalize_machine_downtimes(factory.downtimes)
    dts_by_machine: dict[str, list[MachineDowntime]] = defaultdict(list)
    for dt in norm.merged_downtimes:
        dts_by_machine[dt.machine_id].append(dt)

    for s_op in scheduled_ops:
        for dt in dts_by_machine.get(s_op.machine_id, []):
            # Half-open non-collision: [S, C) overlaps with [Ds, De) iff S < De and Ds < C
            if s_op.start_minute < dt.end_minute and dt.start_minute < s_op.end_minute:
                violations.append(
                    InvariantViolation(
                        rule=InvariantRule.INV_6_DOWNTIME_COLLISION,
                        entity_type="Operation",
                        entity_id=s_op.operation_id,
                        message=(
                            f"Operation '{s_op.operation_id}' on machine '{s_op.machine_id}' in "
                            f"[{s_op.start_minute}, {s_op.end_minute}) collides with downtime '{dt.id}' "
                            f"in [{dt.start_minute}, {dt.end_minute})."
                        ),
                        expected=dt.end_minute,
                        actual=s_op.start_minute,
                    )
                )
    return violations


def audit_horizon_bounds(
    factory: Factory,
    scheduled_ops: list[ScheduledOperation],
) -> list[InvariantViolation]:
    """Invariant 7: Timestamps must be non-negative integers bounded by dynamic horizon H."""
    violations: list[InvariantViolation] = []
    norm = normalize_machine_downtimes(factory.downtimes)
    horizon = calculate_effective_horizon(factory.orders, norm.merged_downtimes)

    for s_op in scheduled_ops:
        if s_op.start_minute < 0:
            violations.append(
                InvariantViolation(
                    rule=InvariantRule.INV_7_HORIZON_BOUNDS,
                    entity_type="Operation",
                    entity_id=s_op.operation_id,
                    message=f"Operation '{s_op.operation_id}' has negative start time {s_op.start_minute}.",
                    expected=0,
                    actual=s_op.start_minute,
                )
            )
        if s_op.end_minute <= s_op.start_minute:
            violations.append(
                InvariantViolation(
                    rule=InvariantRule.INV_7_HORIZON_BOUNDS,
                    entity_type="Operation",
                    entity_id=s_op.operation_id,
                    message=(
                        f"Operation '{s_op.operation_id}' has non-positive duration interval "
                        f"[{s_op.start_minute}, {s_op.end_minute})."
                    ),
                )
            )
        if s_op.end_minute > horizon:
            violations.append(
                InvariantViolation(
                    rule=InvariantRule.INV_7_HORIZON_BOUNDS,
                    entity_type="Operation",
                    entity_id=s_op.operation_id,
                    message=(
                        f"Operation '{s_op.operation_id}' completion minute {s_op.end_minute} "
                        f"exceeds calculated horizon {horizon}."
                    ),
                    expected=horizon,
                    actual=s_op.end_minute,
                )
            )
    return violations
