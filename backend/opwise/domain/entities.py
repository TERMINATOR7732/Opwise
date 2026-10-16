"""Pure domain entities and enums for Opwise.

Governed by SPECIFICATION.md, SOLVER_MODEL.md, and DATA_AND_API.md.
Completely decoupled from persistence (SQLAlchemy), solver (OR-Tools), and web (FastAPI).
"""

from dataclasses import dataclass, field
from enum import Enum


class ScheduleStatus(str, Enum):
    """Execution status of a production schedule."""

    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    NO_WORK_STATE = "NO_WORK_STATE"
    TIMEOUT = "TIMEOUT"
    MODEL_INVALID = "MODEL_INVALID"


class ObjectiveMode(str, Enum):
    """The active mathematical optimization objective."""

    PURE_MAKESPAN = "PURE_MAKESPAN"
    PURE_WEIGHTED_TARDINESS = "PURE_WEIGHTED_TARDINESS"
    HIERARCHICAL_LEXICOGRAPHIC = "HIERARCHICAL_LEXICOGRAPHIC"


class InputClassification(str, Enum):
    """Formal taxonomy of input conditions (Cases 1-6)."""

    EMPTY_WORKSPACE = "EMPTY_WORKSPACE"
    NO_WORK_STATE = "NO_WORK_STATE"
    ORDER_WITHOUT_OPERATIONS = "ORDER_WITHOUT_OPERATIONS"
    REFERENTIAL_INTEGRITY_VIOLATION = "REFERENTIAL_INTEGRITY_VIOLATION"
    VALID_NON_EMPTY_FACTORY = "VALID_NON_EMPTY_FACTORY"
    INFEASIBLE_CONSTRAINTS = "INFEASIBLE_CONSTRAINTS"


@dataclass(frozen=True)
class Machine:
    """A manufacturing workstation with exclusive processing capacity."""

    id: str
    name: str
    description: str = ""


@dataclass(frozen=True)
class MachineDowntime:
    """An unyielding maintenance window on a machine occupying half-open [start_minute, end_minute)."""

    id: str
    machine_id: str
    start_minute: int
    end_minute: int
    reason: str = ""

    @property
    def duration_minutes(self) -> int:
        """The total duration in relative minutes."""
        return max(0, self.end_minute - self.start_minute)

    def overlaps_with(self, other: "MachineDowntime") -> bool:
        """Check if two downtimes on the same machine overlap or touch boundaries."""
        if self.machine_id != other.machine_id:
            return False
        return self.start_minute < other.end_minute and other.start_minute < self.end_minute

    def is_adjacent_to(self, other: "MachineDowntime") -> bool:
        """Check if two downtimes share an exact boundary (e.g. [0, 30) and [30, 60))."""
        if self.machine_id != other.machine_id:
            return False
        return self.end_minute == other.start_minute or other.end_minute == self.start_minute


@dataclass(frozen=True)
class Operation:
    """An atomic processing step within a production order assigned to a specific machine."""

    id: str
    order_id: str
    sequence_number: int
    machine_id: str
    processing_duration_minutes: int


@dataclass
class ProductionOrder:
    """A manufacturing job order comprising a linear sequence of non-preemptive operations."""

    id: str
    order_code: str
    release_time_minutes: int = 0
    due_date_minutes: int = 0
    tardiness_weight: int = 1
    operations: list[Operation] = field(default_factory=list)

    @property
    def total_processing_time(self) -> int:
        """Sum of all constituent operation durations."""
        return sum(op.processing_duration_minutes for op in self.operations)


@dataclass
class Factory:
    """A complete shop floor configuration within a workspace."""

    workspace_id: str
    machines: list[Machine] = field(default_factory=list)
    downtimes: list[MachineDowntime] = field(default_factory=list)
    orders: list[ProductionOrder] = field(default_factory=list)

    def get_machine(self, machine_id: str) -> Machine | None:
        """Retrieve a machine by its ID."""
        for m in self.machines:
            if m.id == machine_id:
                return m
        return None

    def get_order(self, order_id: str) -> ProductionOrder | None:
        """Retrieve an order by its ID."""
        for o in self.orders:
            if o.id == order_id:
                return o
        return None


@dataclass(frozen=True)
class ScheduledOperation:
    """The calculated placement of an operation in the schedule."""

    operation_id: str
    order_id: str
    machine_id: str
    sequence_number: int
    start_minute: int
    end_minute: int
    processing_duration_minutes: int
    slack_minutes: int = 0


@dataclass(frozen=True)
class ScheduleKPIs:
    """Deterministic scheduling performance metrics."""

    makespan_minutes: int
    total_weighted_tardiness: int
    late_order_count: int
    on_time_rate: float


@dataclass
class Schedule:
    """An immutable, complete production plan produced by optimization or demo fixtures."""

    id: str
    workspace_id: str
    status: ScheduleStatus
    objective_mode: ObjectiveMode
    kpis: ScheduleKPIs
    scheduled_operations: list[ScheduledOperation] = field(default_factory=list)
    verified: bool = False
