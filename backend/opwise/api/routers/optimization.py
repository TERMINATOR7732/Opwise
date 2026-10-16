"""Optimization submission and solver orchestration endpoint.

Governed by DATA_AND_API.md Section 3.2 and Section 3.3.
"""

from fastapi import APIRouter

from opwise.api.dependencies import OptimizationServiceDep
from opwise.api.schemas.common import SuccessEnvelope
from opwise.api.schemas.schedule import OptimizeRequest, OptimizeResponseData

router = APIRouter(prefix="/workspaces/{workspace_id}/optimize", tags=["optimization"])


@router.post("", response_model=SuccessEnvelope[OptimizeResponseData])
async def optimize_schedule(
    workspace_id: str,
    request: OptimizeRequest,
    service: OptimizationServiceDep,
) -> SuccessEnvelope[OptimizeResponseData]:
    """Execute CP-SAT optimization, independent verification, and persist schedule snapshot."""
    data = await service.optimize(workspace_id, request)
    await service.session.commit()
    return SuccessEnvelope(data=data)
