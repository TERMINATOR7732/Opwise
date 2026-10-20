"""Execution schemas for shop-floor plant-clock advancement and operation lifecycle dispatching.

Governed by DATA_AND_API.md Section 3.4 and MILESTONE_15D_SCOPE_PROPOSAL.md.
"""

from pydantic import BaseModel, Field, model_validator


class ClockAdvancePayload(BaseModel):
    """Payload to advance the plant clock and optionally reconcile active operations."""

    advance_by_minutes: int | None = Field(
        default=None, ge=0, description="Relative minutes to advance the plant clock."
    )
    target_time_minute: int | None = Field(
        default=None, ge=0, description="Absolute destination plant clock in minutes."
    )
    expected_current_time_minute: int | None = Field(
        default=None, ge=0, description="Optimistic concurrency fencing token."
    )
    completed_operation_ids: list[str] = Field(
        default_factory=list,
        description="IDs of in-progress operations confirmed completed upon arrival at destination clock.",
    )
    remaining_duration_overrides: dict[str, int] = Field(
        default_factory=dict,
        description="Updated supervisor remaining-work estimates (in minutes >= 1) at destination clock.",
    )

    @model_validator(mode="after")
    def validate_advance_parameters(self) -> "ClockAdvancePayload":
        """Assert exactly one of advance_by_minutes or target_time_minute is provided."""
        if self.advance_by_minutes is None and self.target_time_minute is None:
            raise ValueError("Exactly one of 'advance_by_minutes' or 'target_time_minute' must be provided.")
        if self.advance_by_minutes is not None and self.target_time_minute is not None:
            raise ValueError("Cannot specify both 'advance_by_minutes' and 'target_time_minute'.")
        for op_id, rem in self.remaining_duration_overrides.items():
            if rem < 1:
                raise ValueError(f"Remaining duration override for operation '{op_id}' must be >= 1.")
        return self


class StartOperationPayload(BaseModel):
    """Payload to start a PLANNED operation at the current plant clock."""

    estimated_remaining_duration_minutes: int | None = Field(
        default=None,
        ge=1,
        description="Optional initial estimate of remaining duration (defaults to operation processing duration).",
    )
    expected_current_time_minute: int | None = Field(
        default=None, ge=0, description="Optimistic concurrency fencing token."
    )


class CompleteOperationPayload(BaseModel):
    """Payload to mark an IN_PROGRESS operation as COMPLETED at the current plant clock."""

    expected_current_time_minute: int | None = Field(
        default=None, ge=0, description="Optimistic concurrency fencing token."
    )


class AdjustRemainingPayload(BaseModel):
    """Payload to adjust remaining duration for an IN_PROGRESS operation without advancing clock."""

    remaining_duration_minutes: int = Field(
        ..., ge=1, description="Supervisor updated remaining processing minutes."
    )
    expected_current_time_minute: int | None = Field(
        default=None, ge=0, description="Optimistic concurrency fencing token."
    )


class ActiveOperationSummary(BaseModel):
    """Summary of an operation currently IN_PROGRESS."""

    operation_id: str
    order_id: str
    order_code: str
    sequence_index: int
    machine_id: str
    machine_name: str
    actual_start_minute: int
    elapsed_minutes: int
    remaining_duration_minutes: int
    projected_end_minute: int
    is_overdue: bool


class ReadyOperationSummary(BaseModel):
    """Summary of an operation that is PLANNED and eligible to start immediately."""

    operation_id: str
    order_id: str
    order_code: str
    sequence_index: int
    machine_id: str
    machine_name: str
    processing_minutes: int


class OccupiedMachineSummary(BaseModel):
    """Status summary of a shop-floor machine."""

    machine_id: str
    machine_name: str
    status: str  # "BUSY", "IDLE", "DOWNTIME"
    active_operation_id: str | None = None


class ExecutionStatusResponse(BaseModel):
    """Overall execution dispatching and shop-floor status response."""

    workspace_id: str
    current_time_minute: int
    active_operations: list[ActiveOperationSummary]
    ready_to_start_operations: list[ReadyOperationSummary]
    occupied_machines: list[OccupiedMachineSummary]
