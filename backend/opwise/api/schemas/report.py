"""Pydantic schemas for production schedule reports, analytics, and data exports.

Governed by SPECIFICATION.md Section 5.1, Section 8.1, and DATA_AND_API.md Section 4.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SummaryKPIs(BaseModel):
    """Aggregate schedule and solver KPIs."""

    model_config = ConfigDict(frozen=True)

    makespan_minutes: int = Field(..., ge=0)
    total_weighted_tardiness: int = Field(..., ge=0)
    late_order_count: int = Field(..., ge=0)
    on_time_order_count: int = Field(..., ge=0)
    total_order_count: int = Field(..., ge=0)
    on_time_rate_pct: float = Field(..., ge=0.0, le=100.0)
    solver_wall_clock_seconds: float = Field(..., ge=0.0)
    solver_deterministic_time: float | None = None


class MachineUtilizationItem(BaseModel):
    """Per-machine capacity, workload, downtime, and net utilization analytics."""

    model_config = ConfigDict(frozen=True)

    machine_id: str
    machine_name: str
    workload_minutes: int = Field(..., ge=0)
    downtime_minutes: int = Field(..., ge=0)
    idle_minutes: int = Field(..., ge=0)
    available_capacity_minutes: int = Field(..., ge=0)
    net_utilization_pct: float = Field(..., ge=0.0)
    gross_utilization_pct: float = Field(..., ge=0.0)
    assigned_operation_count: int = Field(..., ge=0)
    is_oversubscribed: bool = False


class OrderPerformanceItem(BaseModel):
    """Per-order timeline, due date, tardiness, and slack metrics."""

    model_config = ConfigDict(frozen=True)

    order_id: str
    order_code: str
    release_minute: int = Field(..., ge=0)
    due_date_minute: int = Field(..., ge=0)
    completion_minute: int = Field(..., ge=0)
    tardiness_minutes: int = Field(..., ge=0)
    tardiness_weight: int = Field(..., ge=1)
    weighted_tardiness: int = Field(..., ge=0)
    slack_minutes: int = Field(..., ge=0)
    is_late: bool
    is_on_time: bool
    operation_count: int = Field(..., ge=0)
    total_processing_minutes: int = Field(..., ge=0)


class BottleneckReportItem(BaseModel):
    """Primary bottleneck identification, ranked workstation demand, and disclaimer."""

    model_config = ConfigDict(frozen=True)

    primary_bottleneck_machine_id: str | None = None
    primary_bottleneck_machine_name: str | None = None
    highest_workload_minutes: int = Field(default=0, ge=0)
    highest_net_utilization_pct: float = Field(default=0.0, ge=0.0)
    ranked_machines: list[str] = Field(default_factory=list)
    disclaimer: str


class ScheduleExplanationItem(BaseModel):
    """Traceable evidence-backed explanation for schedule outcome."""

    model_config = ConfigDict(frozen=True)

    category: str
    entity_type: str
    entity_id: str
    summary: str
    measured_value: str
    threshold_or_target: str | None = None
    mathematical_formula: str
    reason: str


class VerificationAuditSummary(BaseModel):
    """Audit summary of clean-room invariant verifier."""

    model_config = ConfigDict(frozen=True)

    is_valid: bool
    checks_run: int = Field(..., ge=0)
    checks_passed: int = Field(..., ge=0)
    violations: list[str] = Field(default_factory=list)


class ScheduleReportResponse(BaseModel):
    """Comprehensive analytical report for a production schedule."""

    model_config = ConfigDict(frozen=True)

    workspace_id: str
    schedule_id: str
    schedule_name: str
    objective_type: str
    solver_status: str
    verification_status: str
    created_at: datetime
    summary: SummaryKPIs
    machine_utilization: list[MachineUtilizationItem]
    order_performance: list[OrderPerformanceItem]
    bottleneck: BottleneckReportItem
    explanations: list[ScheduleExplanationItem]
    verification_audit: VerificationAuditSummary
