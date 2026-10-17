"""Shop floor and factory validation layer.

Governed by SPECIFICATION.md, SOLVER_MODEL.md, and DATA_AND_API.md.
Implements the 6 formal input classification rules and numerical validation.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from opwise.domain.downtime import (
    NormalizationResult,
    calculate_effective_horizon,
    normalize_machine_downtimes,
)
from opwise.domain.entities import (
    Factory,
    InputClassification,
    MachineDowntime,
    ProductionOrder,
)
from opwise.domain.exceptions import (
    EmptyWorkspaceError,
    InvalidBoundsError,
    InvalidDurationError,
    InvalidSequenceError,
    OrderWithoutOperationsError,
    ReferentialIntegrityError,
)


@dataclass(frozen=True)
class FactoryValidationResult:
    """The outcome of factory structural and numeric validation."""

    classification: InputClassification
    is_optimizable: bool
    effective_horizon_minutes: int
    normalization: NormalizationResult | None = None
    message: str = ""


def _validate_unique_ids(factory: Factory) -> set[str]:
    """Ensure machine and order identifiers are unique within the factory."""
    machine_ids = {m.id for m in factory.machines}
    if len(machine_ids) != len(factory.machines):
        raise ReferentialIntegrityError(
            entity_type="Machine",
            missing_id="duplicate",
            context="Duplicate machine IDs detected in factory definition",
        )

    order_ids = {o.id for o in factory.orders}
    if len(order_ids) != len(factory.orders):
        raise ReferentialIntegrityError(
            entity_type="Order",
            missing_id="duplicate",
            context="Duplicate order IDs detected in factory definition",
        )
    return machine_ids


def _validate_and_normalize_downtimes(
    downtimes: list[MachineDowntime], machine_ids: set[str]
) -> NormalizationResult:
    """Normalize downtimes and ensure every downtime references an existing machine."""
    norm_result = normalize_machine_downtimes(downtimes)
    for dt in norm_result.merged_downtimes:
        if dt.machine_id not in machine_ids:
            raise ReferentialIntegrityError(
                entity_type="Machine",
                missing_id=dt.machine_id,
                context=f"Downtime {dt.id}",
            )
    return norm_result


def _validate_order_operations(order: ProductionOrder, machine_ids: set[str]) -> None:
    """Validate operation sequence, positive duration, and referential integrity."""
    if not order.operations:
        raise OrderWithoutOperationsError(order_id=order.id)

    sorted_ops = sorted(order.operations, key=lambda op: op.sequence_number)
    for expected_seq, op in enumerate(sorted_ops, start=1):
        if op.sequence_number != expected_seq:
            raise InvalidSequenceError(
                order_id=order.id,
                expected_seq=expected_seq,
                found_seq=op.sequence_number,
            )

        if op.processing_duration_minutes <= 0:
            raise InvalidDurationError(
                operation_id=op.id,
                duration=op.processing_duration_minutes,
            )

        if op.machine_id not in machine_ids:
            raise ReferentialIntegrityError(
                entity_type="Machine",
                missing_id=op.machine_id,
                context=f"Operation {op.id} in order {order.id}",
            )

        if op.order_id != order.id:
            raise ReferentialIntegrityError(
                entity_type="Order",
                missing_id=op.order_id,
                context=f"Operation {op.id} references inconsistent order {op.order_id}",
            )


def _validate_orders_and_operations(
    orders: Sequence[ProductionOrder], machine_ids: set[str]
) -> None:
    """Validate numerical bounds and operation sequences for all production orders."""
    for order in orders:
        if order.release_time_minutes < 0:
            raise InvalidBoundsError("release_time_minutes", order.release_time_minutes, 0)
        if order.due_date_minutes < 0:
            raise InvalidBoundsError("due_date_minutes", order.due_date_minutes, 0)
        if order.tardiness_weight < 1:
            raise InvalidBoundsError("tardiness_weight", order.tardiness_weight, 1)

        _validate_order_operations(order, machine_ids)


def validate_factory_for_optimization(factory: Factory) -> FactoryValidationResult:
    """Validate a complete factory against all structural, referential, and numerical rules.

    Formal Taxonomy:
    - Case 1: Empty Workspace (|M|=0, |J|=0) -> Raises EmptyWorkspaceError
    - Case 2: No-Work State (|M|>=1, |J|=0) -> Valid No-Work State (is_optimizable=False)
    - Case 3: Incomplete Orders (0 ops) -> Raises OrderWithoutOperationsError
    - Case 4: Missing Reference -> Raises ReferentialIntegrityError
    - Case 5: Valid Non-Empty Factory -> Valid (is_optimizable=True)
    - Case 6: Infeasible Constraints -> Passed to CP-SAT solver to prove contradiction
    """
    machine_ids = _validate_unique_ids(factory)
    if not factory.machines and not factory.orders:
        raise EmptyWorkspaceError()

    if factory.machines and not factory.orders:
        norm_result = _validate_and_normalize_downtimes(factory.downtimes, machine_ids)
        return FactoryValidationResult(
            classification=InputClassification.NO_WORK_STATE,
            is_optimizable=False,
            effective_horizon_minutes=0,
            normalization=norm_result,
            message="Factory contains machines but zero production orders. Evaluated as No-Work state.",
        )

    if not factory.machines and factory.orders:
        raise EmptyWorkspaceError("Workspace contains orders but zero machines.")

    _validate_orders_and_operations(factory.orders, machine_ids)
    norm_result = _validate_and_normalize_downtimes(factory.downtimes, machine_ids)

    horizon = calculate_effective_horizon(
        orders=factory.orders,
        merged_downtimes=norm_result.merged_downtimes,
    )

    return FactoryValidationResult(
        classification=InputClassification.VALID_NON_EMPTY_FACTORY,
        is_optimizable=True,
        effective_horizon_minutes=horizon,
        normalization=norm_result,
        message="Factory validation passed.",
    )
