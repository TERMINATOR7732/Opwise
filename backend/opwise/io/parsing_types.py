"""Data exchange types and structures for CSV and Excel parsing.

Governed by DATA_AND_API.md Section 4 and SPECIFICATION.md Section 9.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RowError:
    """Row-level validation error describing an issue in imported data."""

    sheet: str
    row: int
    column: str
    value: str
    issue: str


@dataclass(frozen=True)
class ParsedMachine:
    """Raw parsed machine record from CSV or Excel."""

    machine_id: str
    name: str


@dataclass(frozen=True)
class ParsedOrder:
    """Raw parsed production order record from CSV or Excel."""

    order_id: str
    name: str
    release_minute: int
    due_minute: int
    tardiness_weight: int


@dataclass(frozen=True)
class ParsedOperation:
    """Raw parsed operation routing record from CSV or Excel."""

    operation_id: str
    order_id: str
    sequence_index: int
    machine_id: str
    processing_minutes: int


@dataclass(frozen=True)
class ParsedDowntime:
    """Raw parsed maintenance downtime record from CSV or Excel."""

    downtime_id: str
    machine_id: str
    start_minute: int
    end_minute: int
    reason: str


@dataclass
class ParsedFactoryData:
    """Aggregated parsed data with collected row errors and advisory warnings."""

    machines: list[ParsedMachine] = field(default_factory=list)
    orders: list[ParsedOrder] = field(default_factory=list)
    operations: list[ParsedOperation] = field(default_factory=list)
    downtimes: list[ParsedDowntime] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True if parsing yielded zero errors."""
        return len(self.errors) == 0
