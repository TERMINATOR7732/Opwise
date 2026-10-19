"""Schedule inspection and on-demand verification endpoints.

Governed by DATA_AND_API.md Section 3.2.
"""

from fastapi import APIRouter

from opwise.api.dependencies import OptimizationServiceDep, ScheduleRepoDep, WorkspaceRepoDep
from opwise.api.schemas.common import SuccessEnvelope
from opwise.api.schemas.factory import DowntimeResponse
from opwise.api.schemas.schedule import (
    ScheduleDetailResponse,
    ScheduledOperationResponse,
    ScheduleMachineResponse,
    ScheduleMetricsResponse,
    ScheduleSummaryResponse,
    ScheduleTelemetryResponse,
    StageTelemetryResponse,
    VerificationReportResponse,
)
from opwise.domain.exceptions import ResourceNotFoundError
from opwise.persistence.models import ScheduleModel
from opwise.services.snapshot import extract_snapshot_overview

router = APIRouter(prefix="/workspaces/{workspace_id}/schedules", tags=["schedules"])


def _extract_snapshot_data(
    snapshot_json: str,
) -> tuple[list[ScheduleMachineResponse], list[DowntimeResponse]]:
    """Extract machine descriptors and downtime intervals from stored snapshot JSON."""
    raw_m, raw_dt = extract_snapshot_overview(snapshot_json)
    machines = [ScheduleMachineResponse(id=m["id"], name=m["name"]) for m in raw_m]
    downtimes = [
        DowntimeResponse(
            id=dt["id"],
            machine_id=dt["machine_id"],
            start_minute=dt["start"],
            end_minute=dt["end"],
            reason=dt.get("reason"),
        )
        for dt in raw_dt
    ]
    return machines, downtimes



def _build_stage_telemetry(
    status: str | None, val: int | None, bound: int | None, secs: float | None
) -> StageTelemetryResponse | None:
    """Construct StageTelemetryResponse if status is present."""
    if status is None:
        return None
    return StageTelemetryResponse(status=status, objective_value=val, best_bound=bound, wall_clock_seconds=secs)


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
            status=op.status,
        )
        for op in m.scheduled_operations
    ]
    machines, downtimes = _extract_snapshot_data(m.input_snapshot_json)
    return ScheduleDetailResponse(
        id=m.id,
        workspace_id=m.workspace_id,
        name=m.name,
        objective_type=m.objective_type,
        solver_status=m.solver_status,
        verification_status=m.verification_status,
        stage1_telemetry=_build_stage_telemetry(
            m.stage1_status, m.stage1_objective_value, m.stage1_best_bound, m.stage1_wall_clock_seconds
        ),
        stage2_telemetry=_build_stage_telemetry(
            m.stage2_status, m.stage2_objective_value, m.stage2_best_bound, m.stage2_wall_clock_seconds
        ),
        metrics=ScheduleMetricsResponse(
            makespan_minutes=m.makespan_minutes,
            weighted_tardiness=m.weighted_tardiness,
            late_order_count=m.late_order_count,
            on_time_rate=m.on_time_rate,
            objective_value=m.objective_value,
            best_objective_bound=m.best_objective_bound,
            optimality_gap=m.optimality_gap,
        ),
        solver_telemetry=ScheduleTelemetryResponse(
            wall_clock_time_seconds=m.solver_wall_clock_seconds,
            deterministic_time=m.solver_deterministic_time,
            termination_reason=f"SOLVER_STATUS_{m.solver_status}",
        ),
        scheduled_operations=ops,
        downtimes=downtimes,
        machines=machines,
        current_time_minute=m.current_time_minute,
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
            current_time_minute=m.current_time_minute,
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
