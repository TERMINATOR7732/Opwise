"""Common API response envelopes, error structures, and metadata.

Governed by DATA_AND_API.md Section 3.1.
"""

import uuid
from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(UTC).isoformat()


def _generate_request_id() -> str:
    """Generate a random request UUID."""
    return f"req-{uuid.uuid4().hex[:12]}"


class Metadata(BaseModel):
    """Standard metadata envelope attached to all responses."""

    timestamp: str = Field(default_factory=_utc_now_iso)
    request_id: str = Field(default_factory=_generate_request_id)


class ErrorDetail(BaseModel):
    """Specific field or entity error detail."""

    field: str
    issue: str


class ErrorBody(BaseModel):
    """Standard error response body."""

    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ErrorEnvelope(BaseModel):
    """Standard error response envelope for 4xx / 5xx responses."""

    success: bool = False
    error: ErrorBody
    metadata: Metadata = Field(default_factory=Metadata)


class SuccessEnvelope(BaseModel, Generic[T]):
    """Standard success response envelope."""

    success: bool = True
    data: T
    metadata: Metadata = Field(default_factory=Metadata)
