"""Formal verification types, enums, and data models for Opwise.

Governed by SOLVER_MODEL.md Section 6, PROJECT_RULES.md Section 6.3,
and TEST_AND_RELEASE_PLAN.md Milestone 03.
Decoupled completely from OR-Tools and persistence.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VerificationStatus(str, Enum):
    """Overall outcome of the independent schedule verification audit."""

    VERIFIED = "VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    SKIPPED = "SKIPPED"


class InvariantRule(str, Enum):
    """The 8 formal domain invariant rules audited by the clean-room verifier."""

    INV_1_CARDINALITY = "INV_1_CARDINALITY"
    INV_2_DURATION_MACHINE = "INV_2_DURATION_MACHINE"
    INV_3_RELEASE_TIME = "INV_3_RELEASE_TIME"
    INV_4_PRECEDENCE = "INV_4_PRECEDENCE"
    INV_5_MACHINE_OVERLAP = "INV_5_MACHINE_OVERLAP"
    INV_6_DOWNTIME_COLLISION = "INV_6_DOWNTIME_COLLISION"
    INV_7_HORIZON_BOUNDS = "INV_7_HORIZON_BOUNDS"
    INV_8_METRIC_CONCORDANCE = "INV_8_METRIC_CONCORDANCE"
    INV_8_STAGE1_PRESERVATION = "INV_8_STAGE1_PRESERVATION"


@dataclass(frozen=True)
class InvariantViolation:
    """Detailed record of a single invariant violation."""

    rule: InvariantRule
    entity_type: str
    entity_id: str
    message: str
    expected: Any = None
    actual: Any = None


@dataclass(frozen=True)
class MachineUtilizationMetrics:
    """Independently computed capacity utilization metrics for a single machine."""

    machine_id: str
    workload_minutes: int
    downtime_minutes: int
    idle_minutes: int
    net_utilization_pct: float
    gross_utilization_pct: float


@dataclass(frozen=True)
class RecomputedMetrics:
    """Independently calculated schedule performance indicators."""

    makespan_minutes: int
    total_weighted_tardiness: int
    late_order_count: int
    on_time_rate: float
    machine_utilizations: dict[str, MachineUtilizationMetrics] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationReport:
    """Immutable audit report produced by ScheduleVerifier."""

    status: VerificationStatus
    is_valid: bool
    passed_rules: list[InvariantRule]
    failed_rules: list[InvariantRule]
    violations: list[InvariantViolation]
    recomputed_metrics: RecomputedMetrics | None = None
    candidate_metrics_match: bool = False
