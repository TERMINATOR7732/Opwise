"""Schedule, optimization request, telemetry, and verification schemas.

Governed by DATA_AND_API.md Section 3.2 and Section 3.3.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class OptimizeParameters(BaseModel):
    """Solver control parameters."""

    primary_objective: str = Field(default="PURE_MAKESPAN", description="PURE_MAKESPAN or PURE_WEIGHTED_TARDINESS")
    secondary_objective: str | None = Field(default=None, description="Optional second stage objective")
    primary_time_budget_seconds: float = Field(default=10.0, gt=0, le=300.0)
    secondary_time_budget_seconds: float = Field(default=5.0, gt=0, le=300.0)
    num_workers: int = Field(default=1, ge=1, le=16)
    random_seed: int = Field(default=42)


class OptimizeRequest(BaseModel):
    """Payload to trigger optimization solve."""

    name: str = Field(default="Optimization Run", min_length=1, max_length=128)
    objective_type: str = Field(
        default="PURE_MAKESPAN",
        description="PURE_MAKESPAN | PURE_WEIGHTED_TARDINESS | HIERARCHICAL",
    )
    parameters: OptimizeParameters = Field(default_factory=OptimizeParameters)


class ScheduledOperationResponse(BaseModel):
    """Allocated operation timestamp details for Gantt rendering."""

    operation_id: str
    order_id: str
    sequence_index: int
    machine_id: str
    start_minute: int
    end_minute: int
    duration: int
    slack_minutes: int = 0


class ScheduleMetricsResponse(BaseModel):
    """KPI and objective metrics for a schedule."""

    makespan_minutes: int
    weighted_tardiness: int
    late_order_count: int
    on_time_rate: float
    objective_value: int | None = None
    best_objective_bound: int | None = None
    optimality_gap: float | None = None


class ScheduleTelemetryResponse(BaseModel):
    """Solver execution telemetry."""

    wall_clock_time_seconds: float
    deterministic_time: float | None = None
    user_cpu_time_seconds: float | None = None
    termination_reason: str = ""


class StageTelemetryResponse(BaseModel):
    """Telemetry outcome for an individual lexicographic solve stage."""

    status: str | None = None
    objective_value: int | None = None
    best_bound: int | None = None
    wall_clock_seconds: float | None = None


class VerificationReportResponse(BaseModel):
    """Clean-room independent verifier audit report."""

    is_valid: bool
    checks_run: int
    checks_passed: int
    violations: list[str] = Field(default_factory=list)


class OptimizeResponseData(BaseModel):
    """Complete response payload for optimization submission."""

    schedule_id: str
    name: str
    objective_type: str
    solver_status: str
    verification_status: str
    stage1_telemetry: StageTelemetryResponse | None = None
    stage2_telemetry: StageTelemetryResponse | None = None
    metrics: ScheduleMetricsResponse
    solver_telemetry: ScheduleTelemetryResponse | None = None
    verification_report: VerificationReportResponse | None = None
    scheduled_operations: list[ScheduledOperationResponse] = Field(default_factory=list)


class ScheduleSummaryResponse(BaseModel):
    """Concise schedule summary for list views."""

    id: str
    workspace_id: str
    name: str
    objective_type: str
    solver_status: str
    verification_status: str
    makespan_minutes: int
    weighted_tardiness: int
    late_order_count: int
    on_time_rate: float
    created_at: datetime


class ScheduleDetailResponse(BaseModel):
    """Full schedule details including Gantt operations."""

    id: str
    workspace_id: str
    name: str
    objective_type: str
    solver_status: str
    verification_status: str
    stage1_telemetry: StageTelemetryResponse | None = None
    stage2_telemetry: StageTelemetryResponse | None = None
    metrics: ScheduleMetricsResponse
    solver_telemetry: ScheduleTelemetryResponse | None = None
    scheduled_operations: list[ScheduledOperationResponse] = Field(default_factory=list)
    created_at: datetime
