"""Mathematical analysis, disruption synthesis, and divergence detection for scenarios.

Governed by SPECIFICATION.md Section 6 and DATA_AND_API.md Section 1.1 (Tables 8 & 9).
"""

import uuid

from opwise.api.schemas.scenario import DisruptionDelta, OperationDivergence
from opwise.domain.entities import (
    Factory,
    MachineDowntime,
    Operation,
    OperationStatus,
    ProductionOrder,
)
from opwise.domain.exceptions import (
    DomainError,
    InvalidIntervalError,
    InvalidSequenceError,
    LifecycleStateError,
    ReferentialIntegrityError,
)
from opwise.persistence.models import ScheduledOperationModel

UNLIKE_WARNING_TEXT = (
    "Baseline and Scenario differ in objective mode, order set, solver status, or time limit. "
    "Metric deltas reflect the compound effect of structural changes and must not be interpreted as pure delay on baseline orders."
)


def validate_disruption(base_factory: Factory, disruption_type: str, delta: DisruptionDelta) -> None:
    """Validate disruption consistency against baseline factory machines, clock, and invariants."""
    valid_types = {"MACHINE_DOWNTIME", "URGENT_ORDER", "COMBINED"}
    if disruption_type not in valid_types:
        raise DomainError(f"Invalid disruption_type '{disruption_type}'. Must be one of {valid_types}.")

    clock = base_factory.current_time_minute
    valid_machine_ids = {m.id for m in base_factory.machines}

    # 1. Validate injected downtimes
    for dt in delta.added_downtimes:
        if dt.machine_id not in valid_machine_ids:
            raise ReferentialIntegrityError("Machine", dt.machine_id, "Scenario downtime injection")
        if dt.start_minute < 0 or dt.end_minute <= dt.start_minute:
            raise InvalidIntervalError("scenario_dt", dt.start_minute, dt.end_minute)

        # Downtime cannot end in the past relative to the plant clock
        if dt.end_minute <= clock:
            raise LifecycleStateError(
                f"Injected downtime [{dt.start_minute}, {dt.end_minute}) on machine '{dt.machine_id}' "
                f"cannot end at or before plant clock {clock}.",
                error_code="HISTORICAL_DOWNTIME_CONFLICT",
            )

        # Collision checks against baseline operations on that machine
        for order in base_factory.orders:
            for op in order.operations:
                if op.machine_id == dt.machine_id:
                    if (
                        op.status == OperationStatus.COMPLETED
                        and op.actual_start_minute is not None
                        and op.actual_end_minute is not None
                        and max(dt.start_minute, op.actual_start_minute) < min(dt.end_minute, op.actual_end_minute)
                    ):
                        raise LifecycleStateError(
                            f"Injected downtime [{dt.start_minute}, {dt.end_minute}) collides with completed "
                            f"operation '{op.id}' [{op.actual_start_minute}, {op.actual_end_minute}) on machine '{dt.machine_id}'.",
                            error_code="HISTORICAL_DOWNTIME_CONFLICT",
                        )
                    if (
                        op.status == OperationStatus.IN_PROGRESS
                        and op.actual_start_minute is not None
                        and op.remaining_duration_minutes is not None
                    ):
                        in_prog_end = clock + op.remaining_duration_minutes
                        if max(dt.start_minute, op.actual_start_minute) < min(dt.end_minute, in_prog_end):
                            raise LifecycleStateError(
                                f"Injected downtime [{dt.start_minute}, {dt.end_minute}) collides with in-progress "
                                f"operation '{op.id}' [{op.actual_start_minute}, {in_prog_end}) on machine '{dt.machine_id}'.",
                                error_code="HISTORICAL_DOWNTIME_CONFLICT",
                            )

    # 2. Validate injected rush orders
    for ord_item in delta.added_orders:
        if not ord_item.operations:
            raise DomainError(f"Rush order '{ord_item.order_code}' must contain at least one operation.")

        # Rush order release time cannot precede plant clock
        if ord_item.release_time_minutes < clock:
            raise LifecycleStateError(
                f"Rush order '{ord_item.order_code}' release time {ord_item.release_time_minutes} "
                f"cannot precede plant clock {clock}.",
                error_code="INVALID_SEQUENCE",
            )

        if ord_item.due_date_minutes < ord_item.release_time_minutes:
            raise DomainError(
                f"Rush order '{ord_item.order_code}' due date {ord_item.due_date_minutes} "
                f"cannot precede release time {ord_item.release_time_minutes}."
            )

        if ord_item.tardiness_weight < 0:
            raise DomainError(
                f"Rush order '{ord_item.order_code}' tardiness weight {ord_item.tardiness_weight} cannot be negative."
            )

        sorted_ops = sorted(ord_item.operations, key=lambda rop: rop.sequence_index)
        for expected_idx, rush_op in enumerate(sorted_ops, start=1):
            if rush_op.sequence_index != expected_idx:
                raise InvalidSequenceError(ord_item.order_code, expected_idx, rush_op.sequence_index)
            if rush_op.machine_id not in valid_machine_ids:
                raise ReferentialIntegrityError("Machine", rush_op.machine_id, f"Rush order {ord_item.order_code}")
            if rush_op.processing_minutes <= 0:
                raise DomainError(
                    f"Rush order '{ord_item.order_code}' operation step {rush_op.sequence_index} "
                    f"must have positive duration (got {rush_op.processing_minutes})."
                )


def synthesize_disrupted_factory(workspace_id: str, base_factory: Factory, delta: DisruptionDelta) -> Factory:
    """Clone base factory and apply disruption delta without mutating original state, preserving plant clock and lifecycles."""
    downtimes = [
        MachineDowntime(
            id=dt.id,
            machine_id=dt.machine_id,
            start_minute=dt.start_minute,
            end_minute=dt.end_minute,
        )
        for dt in base_factory.downtimes
    ]
    for dt_item in delta.added_downtimes:
        downtimes.append(
            MachineDowntime(
                id=str(uuid.uuid4()),
                machine_id=dt_item.machine_id,
                start_minute=dt_item.start_minute,
                end_minute=dt_item.end_minute,
            )
        )

    orders = [
        ProductionOrder(
            id=o.id,
            order_code=o.order_code,
            release_time_minutes=o.release_time_minutes,
            due_date_minutes=o.due_date_minutes,
            tardiness_weight=o.tardiness_weight,
            operations=[
                Operation(
                    id=op.id,
                    order_id=op.order_id,
                    sequence_number=op.sequence_number,
                    machine_id=op.machine_id,
                    processing_duration_minutes=op.processing_duration_minutes,
                    status=op.status,
                    actual_start_minute=op.actual_start_minute,
                    actual_end_minute=op.actual_end_minute,
                    remaining_duration_minutes=op.remaining_duration_minutes,
                )
                for op in o.operations
            ],
        )
        for o in base_factory.orders
    ]
    for ord_item in delta.added_orders:
        order_id = str(uuid.uuid4())
        ops = [
            Operation(
                id=str(uuid.uuid4()),
                order_id=order_id,
                sequence_number=op.sequence_index,
                machine_id=op.machine_id,
                processing_duration_minutes=op.processing_minutes,
                status=OperationStatus.PLANNED,
                actual_start_minute=None,
                actual_end_minute=None,
                remaining_duration_minutes=None,
            )
            for op in ord_item.operations
        ]
        orders.append(
            ProductionOrder(
                id=order_id,
                order_code=ord_item.order_code,
                release_time_minutes=ord_item.release_time_minutes,
                due_date_minutes=ord_item.due_date_minutes,
                tardiness_weight=ord_item.tardiness_weight,
                operations=ops,
            )
        )

    return Factory(
        workspace_id=workspace_id,
        machines=base_factory.machines,
        downtimes=downtimes,
        orders=orders,
        current_time_minute=base_factory.current_time_minute,
    )


def compute_operation_divergences(
    base_ops: list[ScheduledOperationModel],
    comp_ops: list[ScheduledOperationModel],
) -> list[OperationDivergence]:
    """Calculate operation timing divergences between baseline and compared schedules."""
    base_map = {(op.order_id, op.sequence_number): op for op in base_ops}
    comp_map = {(op.order_id, op.sequence_number): op for op in comp_ops}
    divergences: list[OperationDivergence] = []

    for key, c_op in comp_map.items():
        if key in base_map:
            b_op = base_map[key]
            delta = c_op.start_minute - b_op.start_minute
            st = "DELAYED" if delta > 0 else ("EXPEDITED" if delta < 0 else "UNMODIFIED")
            divergences.append(
                OperationDivergence(
                    order_id=c_op.order_id,
                    sequence_index=c_op.sequence_number,
                    machine_id=c_op.machine_id,
                    baseline_start=b_op.start_minute,
                    baseline_end=b_op.end_minute,
                    compared_start=c_op.start_minute,
                    compared_end=c_op.end_minute,
                    delta_start_minutes=delta,
                    status=st,
                )
            )
        else:
            divergences.append(
                OperationDivergence(
                    order_id=c_op.order_id,
                    sequence_index=c_op.sequence_number,
                    machine_id=c_op.machine_id,
                    baseline_start=None,
                    baseline_end=None,
                    compared_start=c_op.start_minute,
                    compared_end=c_op.end_minute,
                    delta_start_minutes=None,
                    status="NEW_RUSH_OPERATION",
                )
            )

    for key, b_op in base_map.items():
        if key not in comp_map:
            divergences.append(
                OperationDivergence(
                    order_id=b_op.order_id,
                    sequence_index=b_op.sequence_number,
                    machine_id=b_op.machine_id,
                    baseline_start=b_op.start_minute,
                    baseline_end=b_op.end_minute,
                    compared_start=0,
                    compared_end=0,
                    delta_start_minutes=None,
                    status="REMOVED",
                )
            )

    return sorted(divergences, key=lambda d: (d.order_id, d.sequence_index))

