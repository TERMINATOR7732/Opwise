"""Extract and assemble domain Schedule entities from CP-SAT solution variables.

Governed by SOLVER_MODEL.md Section 6 and DATA_AND_API.md Section 4.
Decoupled: candidate schedules are immediately verified through the independent verifier.
"""

import uuid
from collections import defaultdict
from typing import TYPE_CHECKING

from opwise.domain.entities import (
    Factory,
    ObjectiveMode,
    Schedule,
    ScheduledOperation,
    ScheduleKPIs,
    ScheduleStatus,
)
from opwise.solver.solver_types import OperationVarBundle
from opwise.verifier.independent_verifier import ScheduleVerifier
from opwise.verifier.verification_types import VerificationReport

if TYPE_CHECKING:
    from ortools.sat.python import cp_model


def extract_schedule_operations(
    factory: Factory,
    solver: "cp_model.CpSolver",
    var_bundles: dict[str, OperationVarBundle],
) -> list[ScheduledOperation]:
    """Extract solved operation placements and calculate individual slack times."""
    # Group operation variables by order to determine slack relative to subsequent operations
    ops_by_order: dict[str, list[tuple[int, OperationVarBundle, int, int]]] = defaultdict(list)
    for bundle in var_bundles.values():
        start = solver.Value(bundle.start_var)
        end = solver.Value(bundle.end_var)
        ops_by_order[bundle.operation.order_id].append(
            (bundle.operation.sequence_number, bundle, start, end)
        )

    scheduled_operations: list[ScheduledOperation] = []

    for order in factory.orders:
        order_ops = sorted(ops_by_order.get(order.id, []), key=lambda t: t[0])
        n_ops = len(order_ops)
        for i, (seq, bundle, start, end) in enumerate(order_ops):
            if i < n_ops - 1:
                # Internal slack before next operation in sequence
                next_start = order_ops[i + 1][2]
                slack = max(0, next_start - end)
            else:
                # Terminal slack before order due date
                slack = max(0, order.due_date_minutes - end)

            scheduled_operations.append(
                ScheduledOperation(
                    operation_id=bundle.operation.id,
                    order_id=order.id,
                    machine_id=bundle.operation.machine_id,
                    sequence_number=seq,
                    start_minute=start,
                    end_minute=end,
                    processing_duration_minutes=bundle.operation.processing_duration_minutes,
                    slack_minutes=slack,
                )
            )

    return scheduled_operations


def extract_and_verify_schedule(
    factory: Factory,
    solver: "cp_model.CpSolver",
    var_bundles: dict[str, OperationVarBundle],
    objective_mode: ObjectiveMode,
    solver_status: ScheduleStatus,
    stage1_bound: int | None = None,
) -> tuple[Schedule, VerificationReport]:
    """Assemble a complete candidate schedule and audit it with the clean-room verifier."""
    scheduled_ops = extract_schedule_operations(factory, solver, var_bundles)

    # Recompute KPIs directly from extracted placements
    verifier = ScheduleVerifier()
    temp_schedule = Schedule(
        id="TEMP-RECOMPUTE",
        workspace_id=factory.workspace_id,
        status=solver_status,
        objective_mode=objective_mode,
        kpis=ScheduleKPIs(
            makespan_minutes=0,
            total_weighted_tardiness=0,
            late_order_count=0,
            on_time_rate=100.0,
        ),
        scheduled_operations=scheduled_ops,
    )
    recomputed = verifier.recompute_metrics(factory, temp_schedule)

    kpis = ScheduleKPIs(
        makespan_minutes=recomputed.makespan_minutes,
        total_weighted_tardiness=recomputed.total_weighted_tardiness,
        late_order_count=recomputed.late_order_count,
        on_time_rate=recomputed.on_time_rate,
    )

    candidate_schedule = Schedule(
        id=f"SCHED-{uuid.uuid4().hex[:12].upper()}",
        workspace_id=factory.workspace_id,
        status=solver_status,
        objective_mode=objective_mode,
        kpis=kpis,
        scheduled_operations=scheduled_ops,
        verified=False,
    )

    report = verifier.verify(factory, candidate_schedule, stage1_bound=stage1_bound)
    candidate_schedule.verified = report.is_valid

    return candidate_schedule, report
