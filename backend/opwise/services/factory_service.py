"""Factory service managing machine and order configuration updates.

Governed by DATA_AND_API.md Section 3.2, ARCHITECTURE.md, and PROJECT_RULES.md.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from opwise.api.schemas.factory import (
    DowntimeCreate,
    DowntimeResponse,
    FactoryConfigPayload,
    FactoryConfigResponse,
    FactoryValidationResponse,
    MachineCreate,
    MachineResponse,
    OperationResponse,
    OrderCreate,
    OrderResponse,
)
from opwise.domain.entities import Factory, Machine, MachineDowntime, Operation, ProductionOrder
from opwise.domain.exceptions import (
    DomainError,
    InvalidIntervalError,
    ReferentialIntegrityError,
    ResourceNotFoundError,
)
from opwise.domain.validators import validate_factory_for_optimization
from opwise.persistence.models import (
    MachineDowntimeModel,
    MachineModel,
    OperationModel,
    ProductionOrderModel,
)
from opwise.persistence.repository import FactoryRepository, WorkspaceRepository


def _map_order_models_to_response(orders: list[ProductionOrderModel]) -> list[OrderResponse]:
    """Map ORM orders to API response models."""
    res: list[OrderResponse] = []
    for o in orders:
        ops = [
            OperationResponse(
                id=op.id,
                order_id=op.order_id,
                sequence_index=op.sequence_index,
                machine_id=op.machine_id,
                processing_minutes=op.processing_minutes,
            )
            for op in o.operations
        ]
        res.append(
            OrderResponse(
                id=o.id,
                external_id=o.external_id,
                name=o.name,
                release_minute=o.release_minute,
                due_minute=o.due_minute,
                tardiness_weight=o.tardiness_weight,
                operations=ops,
            )
        )
    return res


class FactoryService:
    """Service orchestrating factory configuration read, update, and validation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workspace_repo = WorkspaceRepository(session)
        self.factory_repo = FactoryRepository(session)

    async def get_factory_config(self, workspace_id: str) -> FactoryConfigResponse:
        """Fetch complete factory configuration for a workspace."""
        ws = await self.factory_repo.get_factory_models(workspace_id)
        if ws is None:
            if await self.workspace_repo.get_by_id(workspace_id) is None:
                raise ResourceNotFoundError("Workspace", workspace_id)
            return FactoryConfigResponse(workspace_id=workspace_id)

        machines = [
            MachineResponse(id=m.id, external_id=m.external_id, name=m.name, created_at=m.created_at)
            for m in ws.machines
        ]
        downtimes = [
            DowntimeResponse(
                id=dt.id,
                machine_id=dt.machine_id,
                start_minute=dt.start_minute,
                end_minute=dt.end_minute,
                reason=dt.reason,
            )
            for m in ws.machines
            for dt in m.downtimes
        ]
        return FactoryConfigResponse(
            workspace_id=workspace_id,
            machines=machines,
            downtimes=downtimes,
            orders=_map_order_models_to_response(ws.orders),
        )

    def _build_machine_models(
        self, machines_in: list[MachineCreate], downtimes_in: list[DowntimeCreate]
    ) -> tuple[list[MachineModel], dict[str, str]]:
        """Construct MachineModel and MachineDowntimeModel objects with ID mapping."""
        machine_models: list[MachineModel] = []
        ext_to_id: dict[str, str] = {}

        for m_in in machines_in:
            m_id = str(uuid.uuid4())
            ext_to_id[m_in.external_id] = m_id
            ext_to_id[m_id] = m_id
            machine_models.append(MachineModel(id=m_id, external_id=m_in.external_id, name=m_in.name))

        for dt_in in downtimes_in:
            if dt_in.machine_id not in ext_to_id:
                raise ReferentialIntegrityError("Machine", dt_in.machine_id, "Machine downtime")
            if dt_in.start_minute >= dt_in.end_minute:
                raise InvalidIntervalError("new_dt", dt_in.start_minute, dt_in.end_minute)
            target_m_id = ext_to_id[dt_in.machine_id]
            target_model = next(m for m in machine_models if m.id == target_m_id)
            target_model.downtimes.append(
                MachineDowntimeModel(
                    id=str(uuid.uuid4()),
                    machine_id=target_m_id,
                    start_minute=dt_in.start_minute,
                    end_minute=dt_in.end_minute,
                    reason=dt_in.reason,
                )
            )

        return machine_models, ext_to_id

    def _build_order_models(
        self, orders_in: list[OrderCreate], ext_to_id: dict[str, str]
    ) -> list[ProductionOrderModel]:
        """Construct ProductionOrderModel and OperationModel objects."""
        order_models: list[ProductionOrderModel] = []
        for o_in in orders_in:
            o_id = str(uuid.uuid4())
            ops: list[OperationModel] = []
            for op_in in o_in.operations:
                if op_in.machine_id not in ext_to_id:
                    raise ReferentialIntegrityError("Machine", op_in.machine_id, f"Order {o_in.external_id}")
                ops.append(
                    OperationModel(
                        id=str(uuid.uuid4()),
                        order_id=o_id,
                        sequence_index=op_in.sequence_index,
                        machine_id=ext_to_id[op_in.machine_id],
                        processing_minutes=op_in.processing_minutes,
                    )
                )
            order_models.append(
                ProductionOrderModel(
                    id=o_id,
                    external_id=o_in.external_id,
                    name=o_in.name,
                    release_minute=o_in.release_minute,
                    due_minute=o_in.due_minute,
                    tardiness_weight=o_in.tardiness_weight,
                    operations=ops,
                )
            )
        return order_models

    async def replace_factory_config(
        self, workspace_id: str, payload: FactoryConfigPayload
    ) -> FactoryConfigResponse:
        """Atomically replace workspace factory configuration."""
        ws = await self.workspace_repo.get_by_id(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        machines, ext_to_id = self._build_machine_models(payload.machines, payload.downtimes)
        orders = self._build_order_models(payload.orders, ext_to_id)

        await self.factory_repo.replace_factory(workspace_id, machines, orders)
        return await self.get_factory_config(workspace_id)

    def _payload_to_factory(self, workspace_id: str, payload: FactoryConfigPayload) -> Factory:
        """Map API payload to pure Factory domain object for dry-run validation."""
        machines = [Machine(id=m.external_id, name=m.name) for m in payload.machines]
        downtimes = [
            MachineDowntime(
                id=f"dt-{i}",
                machine_id=dt.machine_id,
                start_minute=dt.start_minute,
                end_minute=dt.end_minute,
                reason=dt.reason or "",
            )
            for i, dt in enumerate(payload.downtimes)
        ]
        orders = [
            ProductionOrder(
                id=o.external_id,
                order_code=o.external_id,
                release_time_minutes=o.release_minute,
                due_date_minutes=o.due_minute,
                tardiness_weight=o.tardiness_weight,
                operations=[
                    Operation(
                        id=f"{o.external_id}-{op.sequence_index}",
                        order_id=o.external_id,
                        sequence_number=op.sequence_index,
                        machine_id=op.machine_id,
                        processing_duration_minutes=op.processing_minutes,
                    )
                    for op in o.operations
                ],
            )
            for o in payload.orders
        ]
        return Factory(workspace_id=workspace_id, machines=machines, downtimes=downtimes, orders=orders)

    async def validate_factory_config(
        self, workspace_id: str, payload: FactoryConfigPayload
    ) -> FactoryValidationResponse:
        """Perform dry-run structural validation of factory inputs."""
        factory = self._payload_to_factory(workspace_id, payload)
        try:
            res = validate_factory_for_optimization(factory)
            return FactoryValidationResponse(
                is_valid=True,
                classification=res.classification.value,
                issues=[] if not res.message else [res.message],
            )
        except DomainError as err:
            return FactoryValidationResponse(
                is_valid=False,
                classification="INVALID",
                issues=[err.message],
            )
