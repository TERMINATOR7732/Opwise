"""Mathematical analysis, disruption synthesis, and divergence detection for scenarios.

Governed by SPECIFICATION.md Section 6 and DATA_AND_API.md Section 1.1 (Tables 8 & 9).
"""

import uuid

from opwise.api.schemas.scenario import DisruptionDelta, OperationDivergence
from opwise.domain.entities import (
    Factory,
    MachineDowntime,
    Operation,
    ProductionOrder,
)
from opwise.domain.exceptions import (
    DomainError,
    InvalidIntervalError,
    InvalidSequenceError,
    ReferentialIntegrityError,
)
from opwise.persistence.models import ScheduledOperationModel

UNLIKE_WARNING_TEXT = (
    "Baseline and Scenario differ in objective mode, order set, solver status, or time limit. "
    "Metric deltas reflect the compound effect of structural changes and must not be interpreted as pure delay on baseline orders."
)


def validate_disruption(base_factory: Factory, disruption_type: str, delta: DisruptionDelta) -> None:
    """Validate disruption consistency against baseline factory machines and invariants."""
    valid_types = {"MACHINE_DOWNTIME", "URGENT_ORDER", "COMBINED"}
    if disruption_type not in valid_types:
        raise DomainError(f"Invalid disruption_type '{disruption_type}'. Must be one of {valid_types}.")

    valid_machine_ids = {m.id for m in base_factory.machines}
    for dt in delta.added_downtimes:
        if dt.machine_id not in valid_machine_ids:
            raise ReferentialIntegrityError("Machine", dt.machine_id, "Scenario downtime injection")
        if dt.end_minute <= dt.start_minute:
            raise InvalidIntervalError("scenario_dt", dt.start_minute, dt.end_minute)

    for ord_item in delta.added_orders:
        if not ord_item.operations:
            raise DomainError(f"Rush order '{ord_item.order_code}' must contain at least one operation.")
        sorted_ops = sorted(ord_item.operations, key=lambda op: op.sequence_index)
        for expected_idx, op in enumerate(sorted_ops, start=1):
            if op.sequence_index != expected_idx:
                raise InvalidSequenceError(ord_item.order_code, expected_idx, op.sequence_index)
            if op.machine_id not in valid_machine_ids:
                raise ReferentialIntegrityError("Machine", op.machine_id, f"Rush order {ord_item.order_code}")


def synthesize_disrupted_factory(workspace_id: str, base_factory: Factory, delta: DisruptionDelta) -> Factory:
    """Clone base factory and apply disruption delta without mutating original state."""
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

    return Factory(workspace_id=workspace_id, machines=base_factory.machines, downtimes=downtimes, orders=orders)


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
