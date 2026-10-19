"""Factory configuration, machine, downtime, order, and operation schemas.

Governed by DATA_AND_API.md Section 1.1 and Section 3.2.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class MachineCreate(BaseModel):
    """Payload to create or update a machine."""

    external_id: str = Field(..., min_length=1, max_length=64, description="Machine code (e.g. M1).")
    name: str = Field(..., min_length=1, max_length=128, description="Machine description.")


class MachineResponse(BaseModel):
    """Machine entity representation."""

    id: str
    external_id: str
    name: str
    created_at: datetime


class DowntimeCreate(BaseModel):
    """Payload to create a maintenance window."""

    machine_id: str = Field(..., description="Machine external_id or id.")
    start_minute: int = Field(..., ge=0, description="Start minute.")
    end_minute: int = Field(..., ge=1, description="End minute.")
    reason: str | None = Field(default=None, max_length=255, description="Reason for downtime.")


class DowntimeResponse(BaseModel):
    """Machine downtime window representation."""

    id: str
    machine_id: str
    start_minute: int
    end_minute: int
    reason: str | None = None


class OperationCreate(BaseModel):
    """Payload to define an operation within an order."""

    sequence_index: int = Field(..., ge=1, description="1-based sequence number.")
    machine_id: str = Field(..., description="Target machine external_id or id.")
    processing_minutes: int = Field(..., ge=1, description="Duration in minutes.")
    status: str = Field(default="PLANNED", description="Operation status: PLANNED, IN_PROGRESS, COMPLETED.")
    actual_start_minute: int | None = Field(default=None, ge=0, description="Actual start time in minutes.")
    actual_end_minute: int | None = Field(default=None, ge=0, description="Actual end time in minutes.")
    remaining_duration_minutes: int | None = Field(
        default=None, ge=1, description="Remaining duration in minutes for in-progress operations."
    )


class OperationResponse(BaseModel):
    """Operation representation."""

    id: str
    order_id: str
    sequence_index: int
    machine_id: str
    processing_minutes: int
    status: str = "PLANNED"
    actual_start_minute: int | None = None
    actual_end_minute: int | None = None
    remaining_duration_minutes: int | None = None


class OrderCreate(BaseModel):
    """Payload to create or update a production order."""

    external_id: str = Field(..., min_length=1, max_length=64, description="Order code (e.g. ORD-101).")
    name: str = Field(..., min_length=1, max_length=128, description="Product / order name.")
    release_minute: int = Field(default=0, ge=0, description="Earliest release minute.")
    due_minute: int = Field(..., ge=0, description="Target due minute.")
    tardiness_weight: int = Field(default=1, ge=0, description="Penalty weight per late minute.")
    operations: list[OperationCreate] = Field(default_factory=list, description="Ordered routing operations.")


class OrderResponse(BaseModel):
    """Production order representation."""

    id: str
    external_id: str
    name: str
    release_minute: int
    due_minute: int
    tardiness_weight: int
    operations: list[OperationResponse] = Field(default_factory=list)


class FactoryConfigPayload(BaseModel):
    """Full factory configuration replacement payload."""

    current_time_minute: int | None = Field(
        default=None, ge=0, description="Plant clock in minutes. If omitted, existing factory clock is retained."
    )
    machines: list[MachineCreate] = Field(default_factory=list)
    downtimes: list[DowntimeCreate] = Field(default_factory=list)
    orders: list[OrderCreate] = Field(default_factory=list)


class FactoryConfigResponse(BaseModel):
    """Full factory configuration response."""

    workspace_id: str
    current_time_minute: int = 0
    machines: list[MachineResponse] = Field(default_factory=list)
    downtimes: list[DowntimeResponse] = Field(default_factory=list)
    orders: list[OrderResponse] = Field(default_factory=list)


class FactoryValidationResponse(BaseModel):
    """Dry-run validation result for factory inputs."""

    is_valid: bool
    classification: str
    issues: list[str] = Field(default_factory=list)
