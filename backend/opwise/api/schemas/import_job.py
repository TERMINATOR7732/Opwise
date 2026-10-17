"""Pydantic schemas for two-phase CSV and Excel import.

Governed by DATA_AND_API.md Section 3.2 and Section 4.3.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from opwise.api.schemas.factory import (
    DowntimeCreate,
    FactoryConfigResponse,
    MachineCreate,
    OrderCreate,
)


class ImportRowError(BaseModel):
    """Specific row-level error diagnostic for an imported file or sheet."""

    sheet: str = Field(description="Name of the file or sheet where the error occurred")
    row: int = Field(description="1-based line or row number in the file/sheet")
    column: str = Field(description="Column header or field name with invalid content")
    value: str = Field(default="", description="Sanitized cell value causing the failure")
    issue: str = Field(description="Human-readable explanation of the validation failure")


class ImportSummary(BaseModel):
    """Aggregate entity counts parsed from valid import data."""

    machine_count: int
    order_count: int
    operation_count: int
    downtime_count: int


class ImportStagedData(BaseModel):
    """Parsed and validated factory entities staged for confirmation."""

    machines: list[MachineCreate] = Field(default_factory=list)
    orders: list[OrderCreate] = Field(default_factory=list)
    downtimes: list[DowntimeCreate] = Field(default_factory=list)


class ImportPreviewResponse(BaseModel):
    """Response payload for Phase 1 import preview."""

    job_id: str | None = Field(default=None, description="UUID of staged import job if valid")
    filename: str = Field(description="Name of uploaded file")
    status: str = Field(description="Staging status: PENDING_CONFIRMATION or FAILED")
    is_valid: bool = Field(description="True if completely free of errors and ready to confirm")
    summary: ImportSummary | None = Field(default=None, description="Entity counts if valid")
    warnings: list[str] = Field(default_factory=list, description="Advisory downtime normalization notes")
    staged_data: ImportStagedData | None = Field(default=None, description="Preview entities if valid")
    errors: list[ImportRowError] = Field(default_factory=list, description="Row-level validation errors")


class ImportConfirmRequest(BaseModel):
    """Request payload for Phase 2 import confirmation."""

    job_id: str = Field(description="UUID of the staged import job to commit")


class ImportConfirmResponse(BaseModel):
    """Response payload for Phase 2 import confirmation."""

    job_id: str
    status: str = Field(default="COMMITTED")
    message: str
    factory: FactoryConfigResponse


class ImportJobDetailResponse(BaseModel):
    """Detail response for inspecting a persisted import job."""

    id: str
    workspace_id: str
    filename: str
    status: str
    created_at: datetime
    summary: ImportSummary | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[ImportRowError] = Field(default_factory=list)
