"""Repository pattern isolating database queries from domain and service layers.

Governed by DATA_AND_API.md, ARCHITECTURE.md, and PROJECT_RULES.md.
All operations are scoped to a workspace and execute within caller-managed sessions.
"""

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from opwise.domain.entities import (
    Factory,
    Machine,
    MachineDowntime,
    ObjectiveMode,
    Operation,
    ProductionOrder,
    Schedule,
    ScheduledOperation,
    ScheduleKPIs,
    ScheduleStatus,
)
from opwise.persistence.models import (
    MachineModel,
    ProductionOrderModel,
    ScheduledOperationModel,
    ScheduleModel,
    WorkspaceModel,
)


class WorkspaceRepository:
    """Repository managing Workspace entity persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, workspace_id: str) -> WorkspaceModel | None:
        """Fetch a workspace by primary key."""
        stmt = select(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_name(self, name: str) -> WorkspaceModel | None:
        """Fetch a workspace by unique name."""
        stmt = select(WorkspaceModel).where(WorkspaceModel.name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_all(self) -> list[WorkspaceModel]:
        """List all workspaces ordered by creation date."""
        stmt = select(WorkspaceModel).order_by(WorkspaceModel.created_at.asc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create(self, name: str, description: str | None = None) -> WorkspaceModel:
        """Create and persist a new workspace."""
        ws = WorkspaceModel(name=name, description=description)
        self.session.add(ws)
        await self.session.flush()
        return ws

    async def delete(self, workspace_id: str) -> bool:
        """Delete a workspace and cascade-delete all related records."""
        ws = await self.get_by_id(workspace_id)
        if ws is None:
            return False
        await self.session.delete(ws)
        await self.session.flush()
        return True


def _map_workspace_to_factory(ws: WorkspaceModel) -> Factory:
    """Map ORM WorkspaceModel graph to pure domain Factory aggregate."""
    machines = [Machine(id=m.id, name=m.name) for m in ws.machines]
    downtimes = [
        MachineDowntime(
            id=dt.id,
            machine_id=dt.machine_id,
            start_minute=dt.start_minute,
            end_minute=dt.end_minute,
            reason=dt.reason or "",
        )
        for m in ws.machines
        for dt in m.downtimes
    ]
    orders = [
        ProductionOrder(
            id=o.id,
            order_code=o.external_id,
            release_time_minutes=o.release_minute,
            due_date_minutes=o.due_minute,
            tardiness_weight=o.tardiness_weight,
            operations=[
                Operation(
                    id=op.id,
                    order_id=op.order_id,
                    sequence_number=op.sequence_index,
                    machine_id=op.machine_id,
                    processing_duration_minutes=op.processing_minutes,
                )
                for op in o.operations
            ],
        )
        for o in ws.orders
    ]
    return Factory(workspace_id=ws.id, machines=machines, downtimes=downtimes, orders=orders)


class FactoryRepository:
    """Repository managing machines, downtimes, orders, and operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_factory(self, workspace_id: str) -> Factory | None:
        """Load complete workspace factory configuration as a pure domain object."""
        ws_stmt = (
            select(WorkspaceModel)
            .where(WorkspaceModel.id == workspace_id)
            .options(
                selectinload(WorkspaceModel.machines).selectinload(MachineModel.downtimes),
                selectinload(WorkspaceModel.orders).selectinload(ProductionOrderModel.operations),
            )
        )
        res = await self.session.execute(ws_stmt)
        ws = res.scalar_one_or_none()
        if ws is None:
            return None
        return _map_workspace_to_factory(ws)

    async def replace_factory(
        self,
        workspace_id: str,
        machines: list[MachineModel],
        orders: list[ProductionOrderModel],
    ) -> None:
        """Atomically replace all machines, downtimes, orders, and ops in a workspace."""
        # Delete existing orders and machines (cascading to ops and downtimes)
        await self.session.execute(
            delete(ProductionOrderModel).where(ProductionOrderModel.workspace_id == workspace_id)
        )
        await self.session.execute(
            delete(MachineModel).where(MachineModel.workspace_id == workspace_id)
        )
        for m in machines:
            m.workspace_id = workspace_id
            self.session.add(m)
        for o in orders:
            o.workspace_id = workspace_id
            self.session.add(o)
        await self.session.flush()


def _map_str_to_objective_mode(mode_str: str) -> ObjectiveMode:
    """Map string representation to ObjectiveMode enum."""
    if mode_str in ("HIERARCHICAL", "HIERARCHICAL_LEXICOGRAPHIC"):
        return ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC
    if mode_str == "PURE_WEIGHTED_TARDINESS":
        return ObjectiveMode.PURE_WEIGHTED_TARDINESS
    return ObjectiveMode.PURE_MAKESPAN


class ScheduleRepository:
    """Repository managing Schedule and ScheduledOperation persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, workspace_id: str, schedule_id: str) -> ScheduleModel | None:
        """Retrieve a schedule with scheduled operations, enforcing workspace scoping."""
        stmt = (
            select(ScheduleModel)
            .where(
                ScheduleModel.id == schedule_id,
                ScheduleModel.workspace_id == workspace_id,
            )
            .options(selectinload(ScheduleModel.scheduled_operations))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_workspace(self, workspace_id: str) -> list[ScheduleModel]:
        """List all schedules for a workspace ordered by creation date descending."""
        stmt = (
            select(ScheduleModel)
            .where(ScheduleModel.workspace_id == workspace_id)
            .order_by(ScheduleModel.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    def _build_schedule_model(
        self,
        workspace_id: str,
        schedule: Schedule,
        name: str,
        wall_clock_seconds: float,
        deterministic_time: float | None,
        input_snapshot_json: str,
        stage_telemetry: dict[str, Any] | None,
        objective_value: int | None = None,
        best_objective_bound: int | None = None,
        optimality_gap: float | None = None,
        verification_status: str | None = None,
    ) -> ScheduleModel:
        """Construct an ORM ScheduleModel instance from domain objects and solver telemetry."""
        telem = stage_telemetry or {}
        st1 = telem.get("stage1", {})
        st2 = telem.get("stage2", {})
        verif_status = (
            verification_status
            if verification_status is not None
            else ("VERIFIED" if schedule.verified else "VERIFICATION_FAILED")
        )
        return ScheduleModel(
            id=schedule.id,
            workspace_id=workspace_id,
            name=name,
            objective_type=schedule.objective_mode.value,
            solver_status=schedule.status.value,
            verification_status=verif_status,
            objective_value=objective_value,
            best_objective_bound=best_objective_bound,
            optimality_gap=optimality_gap,
            stage1_status=st1.get("status"),
            stage1_objective_value=st1.get("objective_value"),
            stage1_best_bound=st1.get("best_bound"),
            stage1_wall_clock_seconds=st1.get("wall_clock_seconds"),
            stage2_status=st2.get("status"),
            stage2_objective_value=st2.get("objective_value"),
            stage2_best_bound=st2.get("best_bound"),
            stage2_wall_clock_seconds=st2.get("wall_clock_seconds"),
            makespan_minutes=schedule.kpis.makespan_minutes,
            weighted_tardiness=schedule.kpis.total_weighted_tardiness,
            late_order_count=schedule.kpis.late_order_count,
            on_time_rate=schedule.kpis.on_time_rate,
            solver_wall_clock_seconds=wall_clock_seconds,
            solver_deterministic_time=deterministic_time,
            input_snapshot_json=input_snapshot_json,
        )

    async def save_schedule(
        self,
        workspace_id: str,
        schedule: Schedule,
        name: str,
        wall_clock_seconds: float,
        deterministic_time: float | None = None,
        input_snapshot_json: str = "{}",
        stage_telemetry: dict[str, Any] | None = None,
        objective_value: int | None = None,
        best_objective_bound: int | None = None,
        optimality_gap: float | None = None,
        verification_status: str | None = None,
    ) -> ScheduleModel:
        """Persist a schedule and its allocated operations atomically."""
        sched_model = self._build_schedule_model(
            workspace_id=workspace_id,
            schedule=schedule,
            name=name,
            wall_clock_seconds=wall_clock_seconds,
            deterministic_time=deterministic_time,
            input_snapshot_json=input_snapshot_json,
            stage_telemetry=stage_telemetry,
            objective_value=objective_value,
            best_objective_bound=best_objective_bound,
            optimality_gap=optimality_gap,
            verification_status=verification_status,
        )
        self.session.add(sched_model)

        for op in schedule.scheduled_operations:
            op_model = ScheduledOperationModel(
                schedule_id=schedule.id,
                operation_id=op.operation_id,
                order_id=op.order_id,
                machine_id=op.machine_id,
                sequence_number=op.sequence_number,
                start_minute=op.start_minute,
                end_minute=op.end_minute,
                processing_duration_minutes=op.processing_duration_minutes,
                slack_minutes=op.slack_minutes,
            )
            self.session.add(op_model)

        await self.session.flush()
        return sched_model

    def to_domain_schedule(self, model: ScheduleModel) -> Schedule:
        """Convert a persisted ScheduleModel to a pure domain Schedule entity."""
        kpis = ScheduleKPIs(
            makespan_minutes=model.makespan_minutes,
            total_weighted_tardiness=model.weighted_tardiness,
            late_order_count=model.late_order_count,
            on_time_rate=model.on_time_rate,
        )
        scheduled_ops = [
            ScheduledOperation(
                operation_id=op.operation_id,
                order_id=op.order_id,
                machine_id=op.machine_id,
                sequence_number=op.sequence_number,
                start_minute=op.start_minute,
                end_minute=op.end_minute,
                processing_duration_minutes=op.processing_duration_minutes,
                slack_minutes=op.slack_minutes,
            )
            for op in model.scheduled_operations
        ]
        return Schedule(
            id=model.id,
            workspace_id=model.workspace_id,
            status=ScheduleStatus(model.solver_status),
            objective_mode=_map_str_to_objective_mode(model.objective_type),
            kpis=kpis,
            scheduled_operations=scheduled_ops,
            verified=model.verification_status == "VERIFIED",
        )
