"""Factory configuration CRUD and dry-run validation endpoints.

Governed by DATA_AND_API.md Section 3.2.
"""

from fastapi import APIRouter

from opwise.api.dependencies import FactoryServiceDep
from opwise.api.schemas.common import SuccessEnvelope
from opwise.api.schemas.factory import (
    FactoryConfigPayload,
    FactoryConfigResponse,
    FactoryValidationResponse,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/factory", tags=["factory"])


@router.get("", response_model=SuccessEnvelope[FactoryConfigResponse])
async def get_factory(
    workspace_id: str,
    service: FactoryServiceDep,
) -> SuccessEnvelope[FactoryConfigResponse]:
    """Retrieve complete factory machines, downtimes, orders, and operations."""
    data = await service.get_factory_config(workspace_id)
    return SuccessEnvelope(data=data)


@router.put("", response_model=SuccessEnvelope[FactoryConfigResponse])
async def replace_factory(
    workspace_id: str,
    payload: FactoryConfigPayload,
    service: FactoryServiceDep,
) -> SuccessEnvelope[FactoryConfigResponse]:
    """Atomically replace complete workspace factory configuration."""
    data = await service.replace_factory_config(workspace_id, payload)
    await service.session.commit()
    return SuccessEnvelope(data=data)


@router.post("/validate", response_model=SuccessEnvelope[FactoryValidationResponse])
async def validate_factory(
    workspace_id: str,
    payload: FactoryConfigPayload,
    service: FactoryServiceDep,
) -> SuccessEnvelope[FactoryValidationResponse]:
    """Perform dry-run structural validation of factory configuration without saving."""
    data = await service.validate_factory_config(workspace_id, payload)
    return SuccessEnvelope(data=data)
