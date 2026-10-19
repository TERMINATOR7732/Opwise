"""CP-SAT constraint builders for operations, precedence, release bounds, and machine non-overlap.

Governed by SOLVER_MODEL.md Section 4.2 and Section 3.3.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

from opwise.domain.entities import (
    Machine,
    MachineDowntime,
    OperationStatus,
    ProductionOrder,
)
from opwise.solver.solver_types import OperationVarBundle

if TYPE_CHECKING:
    from ortools.sat.python import cp_model


def build_operation_intervals(
    model: "cp_model.CpModel",
    orders: list[ProductionOrder],
    horizon: int,
    current_time_minute: int = 0,
) -> dict[str, OperationVarBundle]:
    """Create integer start/end variables and interval variables for operations based on lifecycle."""
    var_bundles: dict[str, OperationVarBundle] = {}

    for order in orders:
        for op in order.operations:
            if op.status == OperationStatus.PLANNED:
                duration = op.processing_duration_minutes
                min_start = max(current_time_minute, 0)
                start_var = model.NewIntVar(min_start, horizon, f"start_{op.id}")
                end_var = model.NewIntVar(min_start + duration, horizon, f"end_{op.id}")
                interval_var = model.NewIntervalVar(
                    start_var,
                    duration,
                    end_var,
                    f"interval_{op.id}",
                )
                var_bundles[op.id] = OperationVarBundle(
                    operation=op,
                    start_var=start_var,
                    end_var=end_var,
                    interval_var=interval_var,
                )
            elif op.status == OperationStatus.IN_PROGRESS:
                s = op.actual_start_minute if op.actual_start_minute is not None else 0
                r = (
                    op.remaining_duration_minutes
                    if op.remaining_duration_minutes is not None
                    else op.processing_duration_minutes
                )
                comp = current_time_minute + r
                start_var = model.NewConstant(s)
                end_var = model.NewConstant(comp)
                lock_start = model.NewConstant(current_time_minute)
                lock_end = model.NewConstant(comp)
                lock_interval = model.NewIntervalVar(
                    lock_start,
                    r,
                    lock_end,
                    f"lock_{op.id}",
                )
                var_bundles[op.id] = OperationVarBundle(
                    operation=op,
                    start_var=start_var,
                    end_var=end_var,
                    interval_var=lock_interval,
                )
            elif op.status == OperationStatus.COMPLETED:
                s = op.actual_start_minute if op.actual_start_minute is not None else 0
                e = (
                    op.actual_end_minute
                    if op.actual_end_minute is not None
                    else (s + op.processing_duration_minutes)
                )
                start_var = model.NewConstant(s)
                end_var = model.NewConstant(e)
                var_bundles[op.id] = OperationVarBundle(
                    operation=op,
                    start_var=start_var,
                    end_var=end_var,
                    interval_var=None,
                )

    return var_bundles


def add_release_time_constraints(
    model: "cp_model.CpModel",
    orders: list[ProductionOrder],
    var_bundles: dict[str, OperationVarBundle],
    current_time_minute: int = 0,
) -> None:
    """Enforce Invariant 3: Planned operations cannot start before max(r_j, current_time_minute)."""
    for order in orders:
        if not order.operations:
            continue
        first_op = min(order.operations, key=lambda o: o.sequence_number)
        bundle = var_bundles.get(first_op.id)
        if bundle and bundle.operation.status == OperationStatus.PLANNED:
            min_release = max(order.release_time_minutes, current_time_minute)
            model.Add(bundle.start_var >= min_release)


def add_precedence_constraints(
    model: "cp_model.CpModel",
    orders: list[ProductionOrder],
    var_bundles: dict[str, OperationVarBundle],
) -> None:
    """Enforce Invariant 4: Sequential intra-order precedence (S_{j, k+1} >= C_{j, k})."""
    for order in orders:
        sorted_ops = sorted(order.operations, key=lambda o: o.sequence_number)
        for i in range(len(sorted_ops) - 1):
            curr_bundle = var_bundles[sorted_ops[i].id]
            next_bundle = var_bundles[sorted_ops[i + 1].id]
            if next_bundle.operation.status == OperationStatus.PLANNED:
                model.Add(next_bundle.start_var >= curr_bundle.end_var)


def add_machine_exclusivity_and_downtime(
    model: "cp_model.CpModel",
    machines: list[Machine],
    merged_downtimes: list[MachineDowntime],
    var_bundles: dict[str, OperationVarBundle],
    horizon: int,
    current_time_minute: int = 0,
) -> None:
    """Enforce Invariants 5 & 6: Machine exclusivity and downtime non-collision via AddNoOverlap."""
    intervals_by_machine: dict[str, list[cp_model.IntervalVar]] = defaultdict(list)

    # 1. Add active operation intervals (planned intervals and in-progress future locks)
    for bundle in var_bundles.values():
        if bundle.interval_var is not None:
            intervals_by_machine[bundle.operation.machine_id].append(bundle.interval_var)

    # 2. Add future downtime intervals respecting boundary clamping relative to current_time_minute and H
    for dt in merged_downtimes:
        if dt.end_minute <= current_time_minute or dt.start_minute >= horizon:
            # Downtime ends before current clock or starts beyond effective horizon H
            continue

        effective_start = max(dt.start_minute, current_time_minute)
        clamped_end = min(dt.end_minute, horizon)
        clamped_duration = clamped_end - effective_start
        if clamped_duration <= 0:
            continue

        dt_interval = model.NewFixedSizeIntervalVar(
            effective_start,
            clamped_duration,
            f"downtime_{dt.id}",
        )
        intervals_by_machine[dt.machine_id].append(dt_interval)

    # 3. Apply NoOverlap constraint per machine
    for machine in machines:
        m_intervals = intervals_by_machine.get(machine.id, [])
        if len(m_intervals) > 1:
            model.AddNoOverlap(m_intervals)
