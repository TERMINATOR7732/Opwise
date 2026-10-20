"""Shop-floor execution dispatching and discrete plant-clock advancement service.

Governed by SPECIFICATION.md, DATA_AND_API.md Section 3.4, and MILESTONE_15D_SCOPE_PROPOSAL.md.
Provides atomic plant-clock advancement, operation lifecycle state transitions, and concurrency protection.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from opwise.api.schemas.execution import (
    ActiveOperationSummary,
    ExecutionStatusResponse,
    OccupiedMachineSummary,
    ReadyOperationSummary,
)
from opwise.domain.entities import OperationStatus
from opwise.domain.exceptions import (
    LifecycleStateError,
    ReferentialIntegrityError,
    ResourceNotFoundError,
)
from opwise.persistence.models import (
    MachineModel,
    OperationModel,
    ProductionOrderModel,
    WorkspaceModel,
)


class ExecutionService:
    """Service orchestrating shop-floor execution, plant-clock advancement, and dispatching."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _acquire_workspace_write_lock(self, workspace_id: str) -> None:
        """Acquire SQLite write lock on workspace before reading graph to serialize transactions."""
        stmt = (
            update(WorkspaceModel)
            .where(WorkspaceModel.id == workspace_id)
            .values(current_time_minute=WorkspaceModel.current_time_minute)
        )
        await self.session.execute(stmt)

    async def _load_workspace_graph(self, workspace_id: str) -> WorkspaceModel | None:
        """Load workspace with all machines, downtimes, orders, and operations."""
        stmt = (
            select(WorkspaceModel)
            .where(WorkspaceModel.id == workspace_id)
            .options(
                selectinload(WorkspaceModel.machines).selectinload(MachineModel.downtimes),
                selectinload(WorkspaceModel.orders).selectinload(ProductionOrderModel.operations),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_execution_status(self, workspace_id: str) -> ExecutionStatusResponse:
        """Compile a comprehensive execution status response for the active shop floor."""
        ws = await self._load_workspace_graph(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        current_time = ws.current_time_minute

        machine_map = {m.id: m for m in ws.machines}
        all_ops: list[tuple[ProductionOrderModel, OperationModel]] = [
            (order, op) for order in ws.orders for op in order.operations
        ]

        # 1. Active (IN_PROGRESS) operations
        active_summaries: list[ActiveOperationSummary] = []
        for order, op in all_ops:
            if op.status == OperationStatus.IN_PROGRESS.value:
                start = op.actual_start_minute or current_time
                rem = op.remaining_duration_minutes or op.processing_minutes
                elapsed = max(0, current_time - start)
                projected_end = current_time + rem
                is_overdue = elapsed >= op.processing_minutes
                mach_name = machine_map[op.machine_id].name if op.machine_id in machine_map else op.machine_id

                active_summaries.append(
                    ActiveOperationSummary(
                        operation_id=op.id,
                        order_id=order.id,
                        order_code=order.external_id,
                        sequence_index=op.sequence_index,
                        machine_id=op.machine_id,
                        machine_name=mach_name,
                        actual_start_minute=start,
                        elapsed_minutes=elapsed,
                        remaining_duration_minutes=rem,
                        projected_end_minute=projected_end,
                        is_overdue=is_overdue,
                    )
                )

        # 2. Ready-to-start (PLANNED) operations
        # Must satisfy: order released, pred completed, order not busy, machine free, machine not in downtime
        occupied_machine_ids = {
            op.machine_id
            for _, op in all_ops
            if op.status == OperationStatus.IN_PROGRESS.value
        }
        busy_order_ids = {
            order.id
            for order, op in all_ops
            if op.status == OperationStatus.IN_PROGRESS.value
        }

        # Check machine downtime at current_time
        downtime_machine_ids = set()
        for m in ws.machines:
            for dt in m.downtimes:
                if dt.start_minute <= current_time < dt.end_minute:
                    downtime_machine_ids.add(m.id)
                    break

        ready_summaries: list[ReadyOperationSummary] = []
        for order, op in all_ops:
            if op.status == OperationStatus.PLANNED.value:
                # Check release time
                if order.release_minute > current_time:
                    continue
                # Check order concurrency
                if order.id in busy_order_ids:
                    continue
                # Check predecessor sequence
                if op.sequence_index > 1:
                    pred_ops = [
                        p for p in order.operations if p.sequence_index == op.sequence_index - 1
                    ]
                    if not pred_ops:
                        continue
                    pred = pred_ops[0]
                    if pred.status != OperationStatus.COMPLETED.value:
                        continue
                    if pred.actual_end_minute is None or pred.actual_end_minute > current_time:
                        continue
                # Check machine availability
                if op.machine_id in occupied_machine_ids:
                    continue
                # Check downtime
                if op.machine_id in downtime_machine_ids:
                    continue

                mach_name = machine_map[op.machine_id].name if op.machine_id in machine_map else op.machine_id
                ready_summaries.append(
                    ReadyOperationSummary(
                        operation_id=op.id,
                        order_id=order.id,
                        order_code=order.external_id,
                        sequence_index=op.sequence_index,
                        machine_id=op.machine_id,
                        machine_name=mach_name,
                        processing_minutes=op.processing_minutes,
                    )
                )

        # 3. Occupied / Status per machine
        machine_summaries: list[OccupiedMachineSummary] = []
        for m in ws.machines:
            active_op_on_m = next(
                (op for _, op in all_ops if op.machine_id == m.id and op.status == OperationStatus.IN_PROGRESS.value),
                None,
            )
            if active_op_on_m is not None:
                mach_status = "BUSY"
                active_id = active_op_on_m.id
            elif m.id in downtime_machine_ids:
                mach_status = "DOWNTIME"
                active_id = None
            else:
                mach_status = "IDLE"
                active_id = None

            machine_summaries.append(
                OccupiedMachineSummary(
                    machine_id=m.id,
                    machine_name=m.name,
                    status=mach_status,
                    active_operation_id=active_id,
                )
            )

        return ExecutionStatusResponse(
            workspace_id=ws.id,
            current_time_minute=current_time,
            active_operations=active_summaries,
            ready_to_start_operations=ready_summaries,
            occupied_machines=machine_summaries,
        )

    async def advance_clock(
        self,
        workspace_id: str,
        advance_by_minutes: int | None = None,
        target_time_minute: int | None = None,
        expected_current_time_minute: int | None = None,
        completed_operation_ids: list[str] | None = None,
        remaining_duration_overrides: dict[str, int] | None = None,
    ) -> ExecutionStatusResponse:
        """Advance the plant clock atomically, decrementing remaining work and reconciling overdue work."""
        await self._acquire_workspace_write_lock(workspace_id)
        completed_ids = completed_operation_ids or []
        overrides = remaining_duration_overrides or {}

        ws = await self._load_workspace_graph(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        t_0 = ws.current_time_minute

        # Determine target clock
        if advance_by_minutes is not None:
            t_1 = t_0 + advance_by_minutes
        elif target_time_minute is not None:
            t_1 = target_time_minute
        else:
            raise LifecycleStateError(
                "Must provide either 'advance_by_minutes' or 'target_time_minute'.",
                error_code="INVALID_CLOCK",
            )

        # Validate non-negative destination
        if t_1 < 0:
            raise LifecycleStateError(
                f"Plant clock destination cannot be negative: {t_1}.",
                error_code="INVALID_CLOCK",
            )

        # Concurrency check: optimistic fencing token
        if expected_current_time_minute is not None and expected_current_time_minute != t_0:
            raise LifecycleStateError(
                f"Stale execution state: expected clock {expected_current_time_minute}, but current clock is {t_0}.",
                error_code="STALE_EXECUTION_STATE",
                status_code=409,
            )

        # Monotonic forward progress
        if t_1 < t_0:
            raise LifecycleStateError(
                f"Cannot move plant clock backward from {t_0} to {t_1}.",
                error_code="INVALID_CLOCK",
            )

        baseline_token = expected_current_time_minute if expected_current_time_minute is not None else t_0

        # Idempotent no-op check
        if t_1 == t_0 and not completed_ids and not overrides:
            return await self.get_execution_status(workspace_id)

        # Map all operations and find active operations
        all_ops = {op.id: op for order in ws.orders for op in order.operations}
        active_ops = [op for op in all_ops.values() if op.status == OperationStatus.IN_PROGRESS.value]

        # Validate completed_operation_ids
        for op_id in completed_ids:
            if op_id not in all_ops:
                raise ReferentialIntegrityError("Operation", op_id, "completed_operation_ids")
            if all_ops[op_id].status != OperationStatus.IN_PROGRESS.value:
                raise LifecycleStateError(
                    f"Operation '{op_id}' is not IN_PROGRESS (status: {all_ops[op_id].status}).",
                    error_code="INVALID_LIFECYCLE_STATE",
                )

        # Validate remaining_duration_overrides
        for op_id, new_rem in overrides.items():
            if op_id not in all_ops:
                raise ReferentialIntegrityError("Operation", op_id, "remaining_duration_overrides")
            if all_ops[op_id].status != OperationStatus.IN_PROGRESS.value:
                raise LifecycleStateError(
                    f"Operation '{op_id}' is not IN_PROGRESS (status: {all_ops[op_id].status}).",
                    error_code="INVALID_LIFECYCLE_STATE",
                )
            if new_rem < 1:
                raise LifecycleStateError(
                    f"Remaining duration override for operation '{op_id}' must be >= 1.",
                    error_code="INVALID_DURATION",
                )

        # Ensure no operation is both completed and overridden
        conflict = set(completed_ids).intersection(overrides.keys())
        if conflict:
            raise LifecycleStateError(
                f"Operation(s) {conflict} cannot be both completed and overridden in the same request.",
                error_code="INVALID_LIFECYCLE_STATE",
            )

        delta = t_1 - t_0

        # Audit each active operation against advance
        for op in active_ops:
            if op.id in completed_ids:
                if t_1 <= (op.actual_start_minute or 0):
                    raise LifecycleStateError(
                        f"Completed operation '{op.id}' actual_end ({t_1}) must be strictly greater than start ({op.actual_start_minute}).",
                        error_code="INVALID_LIFECYCLE_STATE",
                    )
            elif op.id in overrides:
                pass  # overridden explicitly
            else:
                current_rem = op.remaining_duration_minutes or 0
                if delta < current_rem:
                    pass  # linear decrement
                else:
                    projected_finish = t_0 + current_rem
                    raise LifecycleStateError(
                        f"Operation '{op.id}' reached projected finish at {projected_finish}m. "
                        "Explicit reconciliation required.",
                        error_code="OVERDUE_RECONCILIATION_REQUIRED",
                    )

        # Audit downtime collisions on elapsed intervals [actual_start, t_1)
        machine_downtimes = {m.id: m.downtimes for m in ws.machines}
        for op in active_ops:
            start_min = op.actual_start_minute or t_0
            dts = machine_downtimes.get(op.machine_id, [])
            for dt in dts:
                # Interval is [start_min, t_1) vs [dt.start_minute, dt.end_minute)
                if max(start_min, dt.start_minute) < min(t_1, dt.end_minute):
                    raise LifecycleStateError(
                        f"Operation '{op.id}' execution interval [{start_min}, {t_1}) collides with "
                        f"downtime [{dt.start_minute}, {dt.end_minute}) on machine '{op.machine_id}'.",
                        error_code="HISTORICAL_DOWNTIME_CONFLICT",
                    )

        # Apply mutations
        for op in active_ops:
            if op.id in completed_ids:
                op.status = OperationStatus.COMPLETED.value
                op.actual_end_minute = t_1
                op.remaining_duration_minutes = None
            elif op.id in overrides:
                op.remaining_duration_minutes = overrides[op.id]
            else:
                op.remaining_duration_minutes = (op.remaining_duration_minutes or 0) - delta

        # Execute atomic conditional update on workspace clock
        stmt = (
            update(WorkspaceModel)
            .where(WorkspaceModel.id == workspace_id)
            .where(WorkspaceModel.current_time_minute == baseline_token)
            .values(current_time_minute=t_1)
        )
        res = await self.session.execute(stmt)
        if res.rowcount == 0:
            raise LifecycleStateError(
                f"Stale execution state: expected clock {baseline_token}, but current clock has changed concurrently.",
                error_code="STALE_EXECUTION_STATE",
                status_code=409,
            )

        await self.session.flush()
        return await self.get_execution_status(workspace_id)

    async def start_operation(
        self,
        workspace_id: str,
        operation_id: str,
        estimated_remaining_duration_minutes: int | None = None,
        expected_current_time_minute: int | None = None,
    ) -> ExecutionStatusResponse:
        """Start a PLANNED operation at the current plant clock."""
        await self._acquire_workspace_write_lock(workspace_id)
        ws = await self._load_workspace_graph(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        t_0 = ws.current_time_minute
        if expected_current_time_minute is not None and expected_current_time_minute != t_0:
            raise LifecycleStateError(
                f"Stale execution state: expected clock {expected_current_time_minute}, but current clock is {t_0}.",
                error_code="STALE_EXECUTION_STATE",
                status_code=409,
            )

        baseline_token = expected_current_time_minute if expected_current_time_minute is not None else t_0

        # Find operation and order
        target_pair = next(
            ((order, op) for order in ws.orders for op in order.operations if op.id == operation_id),
            None,
        )
        if target_pair is None:
            raise ResourceNotFoundError("Operation", operation_id)

        order, op = target_pair

        # 1. Lifecycle state must be PLANNED
        if op.status != OperationStatus.PLANNED.value:
            raise LifecycleStateError(
                f"Operation '{operation_id}' cannot start because status is {op.status}.",
                error_code="INVALID_LIFECYCLE_STATE",
            )

        # 2. Order release time
        if order.release_minute > t_0:
            raise LifecycleStateError(
                f"Operation '{operation_id}' cannot start before order release minute {order.release_minute} (current clock: {t_0}).",
                error_code="INVALID_SEQUENCE",
            )

        # 3. Order concurrency: at most one operation in progress per order
        if any(p.status == OperationStatus.IN_PROGRESS.value for p in order.operations):
            raise LifecycleStateError(
                f"Order '{order.id}' already has an operation in progress.",
                error_code="INVALID_SEQUENCE",
            )

        # 4. Predecessor operations must be completed
        if op.sequence_index > 1:
            pred_ops = [p for p in order.operations if p.sequence_index == op.sequence_index - 1]
            if not pred_ops:
                raise LifecycleStateError(
                    f"Predecessor step {op.sequence_index - 1} missing in order '{order.id}'.",
                    error_code="INVALID_SEQUENCE",
                )
            pred = pred_ops[0]
            if pred.status != OperationStatus.COMPLETED.value:
                raise LifecycleStateError(
                    f"Predecessor operation '{pred.id}' (step {pred.sequence_index}) is {pred.status}, not COMPLETED.",
                    error_code="INVALID_SEQUENCE",
                )
            if pred.actual_end_minute is not None and pred.actual_end_minute > t_0:
                raise LifecycleStateError(
                    f"Predecessor operation '{pred.id}' ends in the future ({pred.actual_end_minute} > {t_0}).",
                    error_code="INVALID_SEQUENCE",
                )

        # 5. Machine exclusivity: assigned machine must be free
        for other_order in ws.orders:
            for other_op in other_order.operations:
                if other_op.machine_id == op.machine_id and other_op.status == OperationStatus.IN_PROGRESS.value:
                    raise LifecycleStateError(
                        f"Machine '{op.machine_id}' is occupied by in-progress operation '{other_op.id}'.",
                        error_code="MACHINE_OCCUPIED",
                    )

        # 6. Machine active downtime
        target_machine = next((m for m in ws.machines if m.id == op.machine_id), None)
        if target_machine is not None:
            for dt in target_machine.downtimes:
                if dt.start_minute <= t_0 < dt.end_minute:
                    raise LifecycleStateError(
                        f"Machine '{op.machine_id}' is in maintenance downtime [{dt.start_minute}, {dt.end_minute}) at clock {t_0}m.",
                        error_code="HISTORICAL_DOWNTIME_CONFLICT",
                    )

        # Validate initial remaining estimate if provided
        rem_dur = (
            estimated_remaining_duration_minutes
            if estimated_remaining_duration_minutes is not None
            else op.processing_minutes
        )
        if rem_dur < 1:
            raise LifecycleStateError(
                f"Remaining duration must be >= 1 (got {rem_dur}).",
                error_code="INVALID_DURATION",
            )

        # Mutate operation
        op.status = OperationStatus.IN_PROGRESS.value
        op.actual_start_minute = t_0
        op.actual_end_minute = None
        op.remaining_duration_minutes = rem_dur

        # Atomic conditional verification on workspace clock
        stmt = (
            update(WorkspaceModel)
            .where(WorkspaceModel.id == workspace_id)
            .where(WorkspaceModel.current_time_minute == baseline_token)
            .values(current_time_minute=baseline_token)
        )
        res = await self.session.execute(stmt)
        if res.rowcount == 0:
            raise LifecycleStateError(
                f"Stale execution state: expected clock {baseline_token}, but current clock has changed concurrently.",
                error_code="STALE_EXECUTION_STATE",
                status_code=409,
            )

        await self.session.flush()
        return await self.get_execution_status(workspace_id)

    async def complete_operation(
        self,
        workspace_id: str,
        operation_id: str,
        expected_current_time_minute: int | None = None,
    ) -> ExecutionStatusResponse:
        """Mark an IN_PROGRESS operation as COMPLETED at the current plant clock."""
        await self._acquire_workspace_write_lock(workspace_id)
        ws = await self._load_workspace_graph(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        t_0 = ws.current_time_minute
        if expected_current_time_minute is not None and expected_current_time_minute != t_0:
            raise LifecycleStateError(
                f"Stale execution state: expected clock {expected_current_time_minute}, but current clock is {t_0}.",
                error_code="STALE_EXECUTION_STATE",
                status_code=409,
            )

        baseline_token = expected_current_time_minute if expected_current_time_minute is not None else t_0

        # Find operation
        target_pair = next(
            ((order, op) for order in ws.orders for op in order.operations if op.id == operation_id),
            None,
        )
        if target_pair is None:
            raise ResourceNotFoundError("Operation", operation_id)

        _, op = target_pair

        # 1. Lifecycle state must be IN_PROGRESS
        if op.status != OperationStatus.IN_PROGRESS.value:
            raise LifecycleStateError(
                f"Operation '{operation_id}' cannot complete because status is {op.status}.",
                error_code="INVALID_LIFECYCLE_STATE",
            )

        # 2. Strictly positive execution duration
        start = op.actual_start_minute or 0
        if t_0 <= start:
            raise LifecycleStateError(
                f"Operation '{operation_id}' cannot complete at start minute ({t_0}m). Advance plant clock first.",
                error_code="INVALID_LIFECYCLE_STATE",
            )

        # 3. Downtime collision audit on [start, t_0)
        target_machine = next((m for m in ws.machines if m.id == op.machine_id), None)
        if target_machine is not None:
            for dt in target_machine.downtimes:
                if max(start, dt.start_minute) < min(t_0, dt.end_minute):
                    raise LifecycleStateError(
                        f"Completed operation interval [{start}, {t_0}) collides with downtime "
                        f"[{dt.start_minute}, {dt.end_minute}) on machine '{op.machine_id}'.",
                        error_code="HISTORICAL_DOWNTIME_CONFLICT",
                    )

        # Mutate operation
        op.status = OperationStatus.COMPLETED.value
        op.actual_end_minute = t_0
        op.remaining_duration_minutes = None

        # Atomic conditional check on workspace clock
        stmt = (
            update(WorkspaceModel)
            .where(WorkspaceModel.id == workspace_id)
            .where(WorkspaceModel.current_time_minute == baseline_token)
            .values(current_time_minute=baseline_token)
        )
        res = await self.session.execute(stmt)
        if res.rowcount == 0:
            raise LifecycleStateError(
                f"Stale execution state: expected clock {baseline_token}, but current clock has changed concurrently.",
                error_code="STALE_EXECUTION_STATE",
                status_code=409,
            )

        await self.session.flush()
        return await self.get_execution_status(workspace_id)

    async def adjust_remaining_duration(
        self,
        workspace_id: str,
        operation_id: str,
        remaining_duration_minutes: int,
        expected_current_time_minute: int | None = None,
    ) -> ExecutionStatusResponse:
        """Adjust remaining duration for an IN_PROGRESS operation without advancing plant clock."""
        await self._acquire_workspace_write_lock(workspace_id)
        ws = await self._load_workspace_graph(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        t_0 = ws.current_time_minute
        if expected_current_time_minute is not None and expected_current_time_minute != t_0:
            raise LifecycleStateError(
                f"Stale execution state: expected clock {expected_current_time_minute}, but current clock is {t_0}.",
                error_code="STALE_EXECUTION_STATE",
                status_code=409,
            )

        baseline_token = expected_current_time_minute if expected_current_time_minute is not None else t_0

        # Find operation
        target_pair = next(
            ((order, op) for order in ws.orders for op in order.operations if op.id == operation_id),
            None,
        )
        if target_pair is None:
            raise ResourceNotFoundError("Operation", operation_id)

        _, op = target_pair

        if op.status != OperationStatus.IN_PROGRESS.value:
            raise LifecycleStateError(
                f"Operation '{operation_id}' is not IN_PROGRESS (status: {op.status}).",
                error_code="INVALID_LIFECYCLE_STATE",
            )

        if remaining_duration_minutes < 1:
            raise LifecycleStateError(
                f"Remaining duration must be >= 1 (got {remaining_duration_minutes}).",
                error_code="INVALID_DURATION",
            )

        op.remaining_duration_minutes = remaining_duration_minutes

        stmt = (
            update(WorkspaceModel)
            .where(WorkspaceModel.id == workspace_id)
            .where(WorkspaceModel.current_time_minute == baseline_token)
            .values(current_time_minute=baseline_token)
        )
        res = await self.session.execute(stmt)
        if res.rowcount == 0:
            raise LifecycleStateError(
                f"Stale execution state: expected clock {baseline_token}, but current clock has changed concurrently.",
                error_code="STALE_EXECUTION_STATE",
                status_code=409,
            )

        await self.session.flush()
        return await self.get_execution_status(workspace_id)
