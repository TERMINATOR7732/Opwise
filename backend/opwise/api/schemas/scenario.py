"""Disruption scenario and comparison schemas.

Governed by DATA_AND_API.md Section 1.1, Section 3.2, and SPECIFICATION.md Section 6.
"""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator


class DowntimeDisruptionItem(BaseModel):
    """Machine downtime disruption window."""

    machine_id: str = Field(..., description="Target machine identifier.")
    start_minute: int = Field(..., ge=0, description="Downtime start minute.")
    end_minute: int = Field(..., gt=0, description="Downtime end minute.")
    reason: str | None = Field(default=None, max_length=255, description="Reason for downtime.")

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        """Ensure interval has positive span."""
        if self.end_minute <= self.start_minute:
            raise ValueError(
                f"end_minute ({self.end_minute}) must be strictly greater than start_minute ({self.start_minute})"
            )
        return self


class OperationDisruptionItem(BaseModel):
    """Step in an injected rush order."""

    sequence_index: int = Field(..., ge=1, description="1-based sequence step.")
    machine_id: str = Field(..., description="Target workstation identifier.")
    processing_minutes: int = Field(..., gt=0, description="Operation duration in minutes.")


class OrderDisruptionItem(BaseModel):
    """Urgent rush order injected into scenario."""

    order_code: str = Field(..., min_length=1, max_length=64, description="Order code (e.g. RUSH-101).")
    release_time_minutes: int = Field(default=0, ge=0, description="Earliest release minute.")
    due_date_minutes: int = Field(..., ge=1, description="Target due date in minutes.")
    tardiness_weight: int = Field(default=1, ge=1, description="Tardiness penalty weight.")
    operations: list[OperationDisruptionItem] = Field(
        ..., min_length=1, description="Sequence of operations for this rush order."
    )


class DisruptionDelta(BaseModel):
    """Structured container for scenario modifications."""

    added_downtimes: list[DowntimeDisruptionItem] = Field(default_factory=list)
    added_orders: list[OrderDisruptionItem] = Field(default_factory=list)


class ScenarioCreateRequest(BaseModel):
    """Payload to create an isolated disruption scenario."""

    name: str = Field(..., min_length=1, max_length=128, description="Scenario name.")
    baseline_schedule_id: str = Field(..., description="UUID of the baseline schedule to branch from.")
    disruption_type: str = Field(
        default="MACHINE_DOWNTIME",
        description="MACHINE_DOWNTIME | URGENT_ORDER | COMBINED",
    )
    disruption_delta: DisruptionDelta = Field(default_factory=DisruptionDelta)
    description: str | None = Field(default=None, max_length=512)


class ScenarioReoptimizeRequest(BaseModel):
    """Optional solver parameters for reoptimizing a scenario."""

    primary_time_budget_seconds: int = Field(default=60, ge=1, le=60)
    num_workers: int = Field(default=4, ge=1, le=16)
    random_seed: int = Field(default=42, ge=0)


class OperationDivergence(BaseModel):
    """Operation timing difference between baseline and scenario."""

    order_id: str
    sequence_index: int
    machine_id: str
    baseline_start: int | None = None
    baseline_end: int | None = None
    compared_start: int
    compared_end: int
    delta_start_minutes: int | None = None
    status: str = Field(description="UNMODIFIED | DELAYED | EXPEDITED | NEW_RUSH_OPERATION | REMOVED")


class ScenarioComparisonResponse(BaseModel):
    """Detailed mathematical comparison between baseline and scenario schedules."""

    id: str
    scenario_id: str | None = None
    baseline_schedule_id: str
    compared_schedule_id: str
    delta_makespan: int
    delta_weighted_tardiness: int
    delta_late_order_count: int
    delta_on_time_rate: float
    objective_diff_detected: bool
    order_set_diff_detected: bool
    status_diff_detected: bool
    time_limit_diff_detected: bool
    unlike_comparison_warning: str | None = None
    diverged_operations: list[OperationDivergence] = Field(default_factory=list)
    created_at: datetime


class ScenarioResponse(BaseModel):
    """Scenario details representation."""

    id: str
    workspace_id: str
    baseline_schedule_id: str
    reoptimized_schedule_id: str | None = None
    name: str
    description: str | None = None
    disruption_type: str
    disruption_delta: DisruptionDelta
    created_at: datetime
    comparison: ScenarioComparisonResponse | None = None


class ScenarioCompareRequest(BaseModel):
    """Payload to request comparison between baseline and scenario schedules."""

    baseline_schedule_id: str = Field(..., description="Baseline schedule UUID.")
    compared_schedule_id: str = Field(..., description="Compared schedule UUID.")
    scenario_id: str | None = Field(default=None, description="Optional associated scenario UUID.")
