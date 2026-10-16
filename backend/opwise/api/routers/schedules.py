"""Schedule inspection and on-demand verification endpoints.

Governed by DATA_AND_API.md Section 3.2.
"""

from fastapi import APIRouter

from opwise.api.dependencies import OptimizationServiceDep, ScheduleRepoDep, WorkspaceRepoDep
from opwise.api.schemas.common import SuccessEnvelope
from opwise.api.schemas.schedule import (
    ScheduleDetailResponse,
    ScheduledOperationResponse,
    ScheduleMetricsResponse,
    ScheduleSummaryResponse,
    ScheduleTelemetryResponse,
    StageTelemetryResponse,
    VerificationReportResponse,
)
from opwise.domain.exceptions import ResourceNotFoundError
from opwise.persistence.models import ScheduleModel

router = APIRouter(prefix="/workspaces/{workspace_id}/schedules", tags=["schedules"])


def _build_schedule_detail(m: ScheduleModel) -> ScheduleDetailResponse:
    """Format an ORM ScheduleModel into ScheduleDetailResponse."""
    ops = [
        ScheduledOperationResponse(
            operation_id=op.operation_id,
            order_id=op.order_id,
            sequence_index=op.sequence_number,
            machine_id=op.machine_id,
            start_minute=op.start_minute,
            end_minute=op.end_minute,
            duration=op.processing_duration_minutes,
            slack_minutes=op.slack_minutes,
        )
        for op in m.scheduled_operations
    ]
    metrics = ScheduleMetricsResponse(
        makespan_minutes=m.makespan_minutes,
        weighted_tardiness=m.weighted_tardiness,
        late_order_count=m.late_order_count,
        on_time_rate=m.on_time_rate,
        objective_value=m.objective_value,
        best_objective_bound=m.best_objective_bound,
        optimality_gap=m.optimality_gap,
    )
    telem = ScheduleTelemetryResponse(
        wall_clock_time_seconds=m.solver_wall_clock_seconds,
        deterministic_time=m.solver_deterministic_time,
        termination_reason=f"SOLVER_STATUS_{m.solver_status}",
    )
    st1 = (
        StageTelemetryResponse(
            status=m.stage1_status,
            objective_value=m.stage1_objective_value,
            best_bound=m.stage1_best_bound,
            wall_clock_seconds=m.stage1_wall_clock_seconds,
        )
        if m.stage1_status is not None
        else None
    )
    st2 = (
        StageTelemetryResponse(
            status=m.stage2_status,
            objective_value=m.stage2_objective_value,
            best_bound=m.stage2_best_bound,
            wall_clock_seconds=m.stage2_wall_clock_seconds,
        )
        if m.stage2_status is not None
        else None
    )
    return ScheduleDetailResponse(
        id=m.id,
        workspace_id=m.workspace_id,
        name=m.name,
        objective_type=m.objective_type,
        solver_status=m.solver_status,
        verification_status=m.verification_status,
        stage1_telemetry=st1,
        stage2_telemetry=st2,
        metrics=metrics,
        solver_telemetry=telem,
        scheduled_operations=ops,
        created_at=m.created_at,
    )


@router.get("", response_model=SuccessEnvelope[list[ScheduleSummaryResponse]])
async def list_schedules(
    workspace_id: str,
    repo: ScheduleRepoDep,
    ws_repo: WorkspaceRepoDep,
) -> SuccessEnvelope[list[ScheduleSummaryResponse]]:
    """List historical optimization schedules for a workspace."""
    ws = await ws_repo.get_by_id(workspace_id)
    if ws is None:
        raise ResourceNotFoundError("Workspace", workspace_id)

    models = await repo.list_by_workspace(workspace_id)
    data = [
        ScheduleSummaryResponse(
            id=m.id,
            workspace_id=m.workspace_id,
            name=m.name,
            objective_type=m.objective_type,
            solver_status=m.solver_status,
            verification_status=m.verification_status,
            makespan_minutes=m.makespan_minutes,
            weighted_tardiness=m.weighted_tardiness,
            late_order_count=m.late_order_count,
            on_time_rate=m.on_time_rate,
            created_at=m.created_at,
        )
        for m in models
    ]
    return SuccessEnvelope(data=data)


@router.get("/{schedule_id}", response_model=SuccessEnvelope[ScheduleDetailResponse])
async def get_schedule(
    workspace_id: str,
    schedule_id: str,
    repo: ScheduleRepoDep,
    ws_repo: WorkspaceRepoDep,
) -> SuccessEnvelope[ScheduleDetailResponse]:
    """Get full schedule details, Gantt timestamps, and solver telemetry."""
    ws = await ws_repo.get_by_id(workspace_id)
    if ws is None:
        raise ResourceNotFoundError("Workspace", workspace_id)

    m = await repo.get_by_id(workspace_id, schedule_id)
    if m is None:
        raise ResourceNotFoundError("Schedule", schedule_id)
    return SuccessEnvelope(data=_build_schedule_detail(m))


@router.post("/{schedule_id}/verify", response_model=SuccessEnvelope[VerificationReportResponse])
async def verify_schedule(
    workspace_id: str,
    schedule_id: str,
    service: OptimizationServiceDep,
) -> SuccessEnvelope[VerificationReportResponse]:
    """Trigger on-demand clean-room independent verification against all 8 operational invariants."""
    report = await service.verify_schedule(workspace_id, schedule_id)
    return SuccessEnvelope(data=report)
