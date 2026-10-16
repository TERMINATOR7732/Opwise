"""CP-SAT constraint builders for operations, precedence, release bounds, and machine non-overlap.

Governed by SOLVER_MODEL.md Section 4.2 and Section 3.3.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

from opwise.domain.entities import (
    Machine,
    MachineDowntime,
    ProductionOrder,
)
from opwise.solver.solver_types import OperationVarBundle

if TYPE_CHECKING:
    from ortools.sat.python import cp_model


def build_operation_intervals(
    model: "cp_model.CpModel",
    orders: list[ProductionOrder],
    horizon: int,
) -> dict[str, OperationVarBundle]:
    """Create integer start/end variables and interval variables for all operations."""
    var_bundles: dict[str, OperationVarBundle] = {}

    for order in orders:
        for op in order.operations:
            duration = op.processing_duration_minutes
            start_var = model.NewIntVar(0, horizon, f"start_{op.id}")
            end_var = model.NewIntVar(0, horizon, f"end_{op.id}")
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

    return var_bundles


def add_release_time_constraints(
    model: "cp_model.CpModel",
    orders: list[ProductionOrder],
    var_bundles: dict[str, OperationVarBundle],
) -> None:
    """Enforce Invariant 3: Order first operation cannot start before release time (S_{j,1} >= r_j)."""
    for order in orders:
        if not order.operations:
            continue
        first_op = min(order.operations, key=lambda o: o.sequence_number)
        bundle = var_bundles.get(first_op.id)
        if bundle:
            model.Add(bundle.start_var >= order.release_time_minutes)


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
            model.Add(next_bundle.start_var >= curr_bundle.end_var)


def add_machine_exclusivity_and_downtime(
    model: "cp_model.CpModel",
    machines: list[Machine],
    merged_downtimes: list[MachineDowntime],
    var_bundles: dict[str, OperationVarBundle],
    horizon: int,
) -> None:
    """Enforce Invariants 5 & 6: Machine exclusivity and downtime non-collision via AddNoOverlap."""
    intervals_by_machine: dict[str, list[cp_model.IntervalVar]] = defaultdict(list)

    # 1. Add operation intervals to their designated workstation
    for bundle in var_bundles.values():
        intervals_by_machine[bundle.operation.machine_id].append(bundle.interval_var)

    # 2. Add fixed downtime intervals respecting boundary clamping relative to H
    for dt in merged_downtimes:
        if dt.start_minute >= horizon:
            # Downtime starts beyond effective horizon H; excluded per SOLVER_MODEL.md Section 3.3
            continue

        clamped_end = min(dt.end_minute, horizon)
        clamped_duration = clamped_end - dt.start_minute
        if clamped_duration <= 0:
            continue

        dt_interval = model.NewFixedSizeIntervalVar(
            dt.start_minute,
            clamped_duration,
            f"downtime_{dt.id}",
        )
        intervals_by_machine[dt.machine_id].append(dt_interval)

    # 3. Apply NoOverlap constraint per machine
    for machine in machines:
        m_intervals = intervals_by_machine.get(machine.id, [])
        if len(m_intervals) > 1:
            model.AddNoOverlap(m_intervals)
