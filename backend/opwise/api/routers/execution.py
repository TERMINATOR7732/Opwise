"""Execution dispatching and plant-clock advancement API router.

Governed by DATA_AND_API.md Section 3.4 and MILESTONE_15D_SCOPE_PROPOSAL.md.
"""

from fastapi import APIRouter

from opwise.api.dependencies import ExecutionServiceDep
from opwise.api.schemas.common import SuccessEnvelope
from opwise.api.schemas.execution import (
    AdjustRemainingPayload,
    ClockAdvancePayload,
    CompleteOperationPayload,
    ExecutionStatusResponse,
    StartOperationPayload,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/execution", tags=["execution"])


@router.post("/clock/advance", response_model=SuccessEnvelope[ExecutionStatusResponse])
async def advance_clock(
    workspace_id: str,
    payload: ClockAdvancePayload,
    service: ExecutionServiceDep,
) -> SuccessEnvelope[ExecutionStatusResponse]:
    """Advance the plant clock, decrement remaining durations, and reconcile overdue operations."""
    data = await service.advance_clock(
        workspace_id=workspace_id,
        advance_by_minutes=payload.advance_by_minutes,
        target_time_minute=payload.target_time_minute,
        expected_current_time_minute=payload.expected_current_time_minute,
        completed_operation_ids=payload.completed_operation_ids,
        remaining_duration_overrides=payload.remaining_duration_overrides,
    )
    await service.session.commit()
    return SuccessEnvelope(data=data)


@router.post("/operations/{operation_id}/start", response_model=SuccessEnvelope[ExecutionStatusResponse])
async def start_operation(
    workspace_id: str,
    operation_id: str,
    payload: StartOperationPayload,
    service: ExecutionServiceDep,
) -> SuccessEnvelope[ExecutionStatusResponse]:
    """Start a planned operation at the current plant clock."""
    data = await service.start_operation(
        workspace_id=workspace_id,
        operation_id=operation_id,
        estimated_remaining_duration_minutes=payload.estimated_remaining_duration_minutes,
        expected_current_time_minute=payload.expected_current_time_minute,
    )
    await service.session.commit()
    return SuccessEnvelope(data=data)


@router.post("/operations/{operation_id}/complete", response_model=SuccessEnvelope[ExecutionStatusResponse])
async def complete_operation(
    workspace_id: str,
    operation_id: str,
    payload: CompleteOperationPayload,
    service: ExecutionServiceDep,
) -> SuccessEnvelope[ExecutionStatusResponse]:
    """Mark an in-progress operation as completed at the current plant clock."""
    data = await service.complete_operation(
        workspace_id=workspace_id,
        operation_id=operation_id,
        expected_current_time_minute=payload.expected_current_time_minute,
    )
    await service.session.commit()
    return SuccessEnvelope(data=data)


@router.patch("/operations/{operation_id}/remaining", response_model=SuccessEnvelope[ExecutionStatusResponse])
async def adjust_remaining_duration(
    workspace_id: str,
    operation_id: str,
    payload: AdjustRemainingPayload,
    service: ExecutionServiceDep,
) -> SuccessEnvelope[ExecutionStatusResponse]:
    """Adjust remaining duration for an in-progress operation without advancing clock."""
    data = await service.adjust_remaining_duration(
        workspace_id=workspace_id,
        operation_id=operation_id,
        remaining_duration_minutes=payload.remaining_duration_minutes,
        expected_current_time_minute=payload.expected_current_time_minute,
    )
    await service.session.commit()
    return SuccessEnvelope(data=data)


@router.get("/status", response_model=SuccessEnvelope[ExecutionStatusResponse])
async def get_execution_status(
    workspace_id: str,
    service: ExecutionServiceDep,
) -> SuccessEnvelope[ExecutionStatusResponse]:
    """Retrieve execution dispatching overview and machine occupancy."""
    data = await service.get_execution_status(workspace_id)
    return SuccessEnvelope(data=data)
