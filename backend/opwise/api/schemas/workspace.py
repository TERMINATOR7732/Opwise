"""Workspace request and response schemas.

Governed by DATA_AND_API.md Section 1.1 and Section 3.2.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreateRequest(BaseModel):
    """Payload to create a new workspace."""

    name: str = Field(..., min_length=1, max_length=128, description="Unique workspace name.")
    description: str | None = Field(default=None, max_length=1000, description="Optional description.")


class WorkspaceResponse(BaseModel):
    """Summary of workspace metadata."""

    id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
