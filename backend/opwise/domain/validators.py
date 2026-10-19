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
    Operation,
    OperationStatus,
    ProductionOrder,
)
from opwise.domain.exceptions import (
    EmptyWorkspaceError,
    InvalidBoundsError,
    InvalidDurationError,
    InvalidSequenceError,
    LifecycleStateError,
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


def validate_plant_clock(clock_or_factory: int | Factory) -> None:
    """Validate that the plant clock is non-negative and operations respect clock bounds."""
    if isinstance(clock_or_factory, Factory):
        current_time_minute = clock_or_factory.current_time_minute
        factory: Factory | None = clock_or_factory
    else:
        current_time_minute = clock_or_factory
        factory = None

    if current_time_minute < 0:
        raise LifecycleStateError(
            f"Plant clock cannot be negative: {current_time_minute}.",
            error_code="INVALID_CLOCK",
        )

    if factory is not None:
        for order in factory.orders:
            for op in order.operations:
                if op.status == OperationStatus.COMPLETED:
                    if op.actual_end_minute is not None and op.actual_end_minute > current_time_minute:
                        raise LifecycleStateError(
                            f"Completed operation '{op.id}' actual_end ({op.actual_end_minute}) cannot be in the future (clock: {current_time_minute}).",
                            error_code="INVALID_CLOCK",
                        )
                elif (
                    op.status == OperationStatus.IN_PROGRESS
                    and op.actual_start_minute is not None
                    and op.actual_start_minute > current_time_minute
                ):
                    raise LifecycleStateError(
                        f"In-progress operation '{op.id}' start ({op.actual_start_minute}) cannot be in the future (clock: {current_time_minute}).",
                        error_code="INVALID_CLOCK",
                    )


def validate_operation_lifecycle(op: Operation, current_time_minute: int | None = None) -> None:
    """Validate single operation lifecycle fields and timestamp constraints."""
    if op.status == OperationStatus.PLANNED:
        if (
            op.actual_start_minute is not None
            or op.actual_end_minute is not None
            or op.remaining_duration_minutes is not None
        ):
            raise LifecycleStateError(
                f"Planned operation '{op.id}' cannot have actual timestamps or remaining duration.",
                error_code="INVALID_LIFECYCLE_STATE",
            )

    elif op.status == OperationStatus.IN_PROGRESS:
        if op.actual_start_minute is None:
            raise LifecycleStateError(
                f"In-progress operation '{op.id}' is missing actual_start_minute.",
                error_code="INVALID_LIFECYCLE_STATE",
            )
        if current_time_minute is not None and op.actual_start_minute > current_time_minute:
            raise LifecycleStateError(
                f"In-progress operation '{op.id}' start ({op.actual_start_minute}) cannot be in the future (clock: {current_time_minute}).",
                error_code="INVALID_LIFECYCLE_STATE",
            )
        if op.remaining_duration_minutes is None or op.remaining_duration_minutes <= 0:
            raise LifecycleStateError(
                f"In-progress operation '{op.id}' requires a positive remaining_duration_minutes.",
                error_code="INVALID_LIFECYCLE_STATE",
            )
        if op.actual_end_minute is not None:
            raise LifecycleStateError(
                f"In-progress operation '{op.id}' cannot have actual_end_minute.",
                error_code="INVALID_LIFECYCLE_STATE",
            )

    elif op.status == OperationStatus.COMPLETED:
        if op.actual_start_minute is None or op.actual_end_minute is None:
            raise LifecycleStateError(
                f"Completed operation '{op.id}' must have both actual_start_minute and actual_end_minute.",
                error_code="INVALID_LIFECYCLE_STATE",
            )
        if op.actual_end_minute <= op.actual_start_minute:
            raise LifecycleStateError(
                f"Completed operation '{op.id}' actual_end ({op.actual_end_minute}) must be strictly greater than actual_start ({op.actual_start_minute}).",
                error_code="INVALID_LIFECYCLE_STATE",
            )
        if current_time_minute is not None and op.actual_end_minute > current_time_minute:
            raise LifecycleStateError(
                f"Completed operation '{op.id}' actual_end ({op.actual_end_minute}) cannot be in the future (clock: {current_time_minute}).",
                error_code="INVALID_LIFECYCLE_STATE",
            )
        if op.remaining_duration_minutes is not None:
            raise LifecycleStateError(
                f"Completed operation '{op.id}' cannot have remaining_duration_minutes.",
                error_code="INVALID_LIFECYCLE_STATE",
            )


def validate_order_lifecycle_sequence(order: ProductionOrder, current_time_minute: int | None = None) -> None:
    """Validate order-level lifecycle monotonic arrangement and temporal precedence."""
    sorted_ops = sorted(order.operations, key=lambda op: op.sequence_number)

    # 1. At most one operation in progress per order
    in_progress_ops = [op for op in sorted_ops if op.status == OperationStatus.IN_PROGRESS]
    if len(in_progress_ops) > 1:
        raise LifecycleStateError(
            f"Order '{order.id}' has multiple operations in progress ({len(in_progress_ops)}). At most one is allowed.",
            error_code="INVALID_SEQUENCE",
        )

    # 2. Check release time adherence for any started/completed operation
    for op in sorted_ops:
        validate_operation_lifecycle(op, current_time_minute)
        if op.actual_start_minute is not None and op.actual_start_minute < order.release_time_minutes:
            raise LifecycleStateError(
                f"Operation '{op.id}' actual start {op.actual_start_minute} precedes order release time {order.release_time_minutes}.",
                error_code="INVALID_SEQUENCE",
            )

    # 3. Verify monotonic lifecycle sequence and timestamp precedence
    for i in range(len(sorted_ops)):
        curr = sorted_ops[i]
        if i > 0:
            prev = sorted_ops[i - 1]
            if curr.status == OperationStatus.COMPLETED:
                if prev.status != OperationStatus.COMPLETED:
                    raise LifecycleStateError(
                        f"Operation '{curr.id}' is COMPLETED but predecessor '{prev.id}' is {prev.status.value}.",
                        error_code="INVALID_SEQUENCE",
                    )
                if (
                    prev.actual_end_minute is not None
                    and curr.actual_start_minute is not None
                    and curr.actual_start_minute < prev.actual_end_minute
                ):
                    raise LifecycleStateError(
                        f"Operation '{curr.id}' starts at {curr.actual_start_minute} before completed predecessor '{prev.id}' ends at {prev.actual_end_minute}.",
                        error_code="INVALID_SEQUENCE",
                    )
            elif curr.status == OperationStatus.IN_PROGRESS:
                if prev.status != OperationStatus.COMPLETED:
                    raise LifecycleStateError(
                        f"Operation '{curr.id}' is IN_PROGRESS but predecessor '{prev.id}' is {prev.status.value}.",
                        error_code="INVALID_SEQUENCE",
                    )
                if (
                    prev.actual_end_minute is not None
                    and curr.actual_start_minute is not None
                    and curr.actual_start_minute < prev.actual_end_minute
                ):
                    raise LifecycleStateError(
                        f"Operation '{curr.id}' starts at {curr.actual_start_minute} before completed predecessor '{prev.id}' ends at {prev.actual_end_minute}.",
                        error_code="INVALID_SEQUENCE",
                    )


def validate_historical_machine_exclusivity(factory: Factory) -> None:
    """Validate pairwise half-open non-overlap across all historical operations on each machine."""
    for machine in factory.machines:
        hist_intervals: list[tuple[int, int, str]] = []
        for order in factory.orders:
            for op in order.operations:
                if op.machine_id == machine.id:
                    if op.status == OperationStatus.COMPLETED:
                        if op.actual_start_minute is not None and op.actual_end_minute is not None:
                            hist_intervals.append((op.actual_start_minute, op.actual_end_minute, op.id))
                    elif (
                        op.status == OperationStatus.IN_PROGRESS
                        and op.actual_start_minute is not None
                        and op.actual_start_minute < factory.current_time_minute
                    ):
                        # Elapsed portion is [actual_start, current_time_minute)
                        # If actual_start == current_time_minute, [t_now, t_now) is empty set (0 points)
                        hist_intervals.append(
                            (op.actual_start_minute, factory.current_time_minute, op.id)
                        )

        hist_intervals.sort(key=lambda item: (item[0], item[1]))
        for i in range(len(hist_intervals) - 1):
            s1, e1, id1 = hist_intervals[i]
            s2, e2, id2 = hist_intervals[i + 1]
            if s2 < e1:
                raise LifecycleStateError(
                    f"Historical machine collision on machine '{machine.id}': operation '{id2}' starts at {s2} before operation '{id1}' ends at {e1}.",
                    error_code="HISTORICAL_MACHINE_CONFLICT",
                )


def validate_historical_and_active_downtimes(factory: Factory) -> None:
    """Validate that historical operations and active in-progress operations do not collide with downtimes."""
    norm_result = normalize_machine_downtimes(factory.downtimes)
    for machine in factory.machines:
        # 1. Check historical downtime collision (t < current_time_minute)
        for dt in norm_result.merged_downtimes:
            if dt.machine_id == machine.id and dt.start_minute < factory.current_time_minute:
                dt_past_end = min(dt.end_minute, factory.current_time_minute)
                for order in factory.orders:
                    for op in order.operations:
                        if op.machine_id == machine.id:
                            if (
                                op.status == OperationStatus.COMPLETED
                                and op.actual_start_minute is not None
                                and op.actual_end_minute is not None
                            ):
                                if max(op.actual_start_minute, dt.start_minute) < min(
                                    op.actual_end_minute, dt_past_end
                                ):
                                    raise LifecycleStateError(
                                        f"Completed operation '{op.id}' [{op.actual_start_minute}, {op.actual_end_minute}) collides with past downtime [{dt.start_minute}, {dt.end_minute}) on machine '{machine.id}'.",
                                        error_code="HISTORICAL_DOWNTIME_CONFLICT",
                                    )
                            elif (
                                op.status == OperationStatus.IN_PROGRESS
                                and op.actual_start_minute is not None
                                and op.actual_start_minute < factory.current_time_minute
                                and max(op.actual_start_minute, dt.start_minute)
                                < min(factory.current_time_minute, dt_past_end)
                            ):
                                raise LifecycleStateError(
                                    f"In-progress operation '{op.id}' elapsed interval [{op.actual_start_minute}, {factory.current_time_minute}) collides with past downtime [{dt.start_minute}, {dt.end_minute}) on machine '{machine.id}'.",
                                    error_code="HISTORICAL_DOWNTIME_CONFLICT",
                                )

        # 2. Check active downtime collision at current_time_minute
        for dt in norm_result.merged_downtimes:
            if dt.machine_id == machine.id and dt.start_minute <= factory.current_time_minute < dt.end_minute:
                for order in factory.orders:
                    for op in order.operations:
                        if op.machine_id == machine.id and op.status == OperationStatus.IN_PROGRESS:
                            raise LifecycleStateError(
                                f"Operation '{op.id}' cannot be IN_PROGRESS on machine '{machine.id}' which is actively in downtime [{dt.start_minute}, {dt.end_minute}) at plant clock {factory.current_time_minute}.",
                                error_code="HISTORICAL_DOWNTIME_CONFLICT",
                            )


def _validate_orders_and_operations(
    orders: Sequence[ProductionOrder], machine_ids: set[str], current_time_minute: int = 0
) -> None:
    """Validate numerical bounds, operation sequences, and lifecycles for all production orders."""
    for order in orders:
        if order.release_time_minutes < 0:
            raise InvalidBoundsError("release_time_minutes", order.release_time_minutes, 0)
        if order.due_date_minutes < 0:
            raise InvalidBoundsError("due_date_minutes", order.due_date_minutes, 0)
        if order.tardiness_weight < 1:
            raise InvalidBoundsError("tardiness_weight", order.tardiness_weight, 1)

        _validate_order_operations(order, machine_ids)
        validate_order_lifecycle_sequence(order, current_time_minute)


def validate_factory_for_optimization(factory: Factory) -> FactoryValidationResult:
    """Validate a complete factory against all structural, referential, numerical, and lifecycle rules.

    Formal Taxonomy:
    - Case 1: Empty Workspace (|M|=0, |J|=0) -> Raises EmptyWorkspaceError
    - Case 2: No-Work State (|M|>=1, |J|=0) -> Valid No-Work State (is_optimizable=False)
    - Case 3: Incomplete Orders (0 ops) -> Raises OrderWithoutOperationsError
    - Case 4: Missing Reference -> Raises ReferentialIntegrityError
    - Case 5: Valid Non-Empty Factory -> Valid (is_optimizable=True)
    - Case 6: Infeasible Constraints -> Passed to CP-SAT solver to prove contradiction
    """
    validate_plant_clock(factory.current_time_minute)
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

    _validate_orders_and_operations(factory.orders, machine_ids, factory.current_time_minute)
    validate_historical_machine_exclusivity(factory)
    validate_historical_and_active_downtimes(factory)
    norm_result = _validate_and_normalize_downtimes(factory.downtimes, machine_ids)

    horizon = calculate_effective_horizon(
        orders=factory.orders,
        merged_downtimes=norm_result.merged_downtimes,
        current_time_minute=factory.current_time_minute,
    )

    return FactoryValidationResult(
        classification=InputClassification.VALID_NON_EMPTY_FACTORY,
        is_optimizable=True,
        effective_horizon_minutes=horizon,
        normalization=norm_result,
        message="Factory validation passed.",
    )
