"""Formal data models and types for Opwise metrics and explanations.

Governed by SPECIFICATION.md Section 5.1 and TEST_AND_RELEASE_PLAN.md Milestone 06.
Pure Python dataclasses with zero external dependencies.
"""

from dataclasses import dataclass

BOTTLENECK_DISCLAIMER: str = (
    "Note: High machine utilization indicates high capacity demand, but does not alone prove "
    "that this machine throttled overall throughput. Bottlenecks in job shops can also be "
    "induced by transfer delays, order release timing, or upstream starvation."
)


@dataclass(frozen=True)
class OrderMetrics:
    """Calculated timeline and tardiness metrics for an individual order."""

    order_id: str
    order_code: str
    completion_minute: int
    due_date_minute: int
    tardiness_minutes: int
    tardiness_weight: int
    weighted_tardiness: int
    is_late: bool
    slack_minutes: int
    operation_count: int
    total_processing_minutes: int


@dataclass(frozen=True)
class MachineMetrics:
    """Capacity, workload, downtime, and utilization metrics for a single workstation."""

    machine_id: str
    workload_minutes: int
    downtime_minutes: int
    idle_minutes: int
    available_capacity_minutes: int
    net_utilization_pct: float
    gross_utilization_pct: float
    assigned_operation_count: int


@dataclass(frozen=True)
class BottleneckAnalysis:
    """Deterministic machine load ranking and candidate bottleneck identification."""

    primary_bottleneck_machine_id: str | None
    ranked_machines: list[str]
    highest_workload_minutes: int
    highest_net_utilization_pct: float
    disclaimer: str = BOTTLENECK_DISCLAIMER


@dataclass(frozen=True)
class ScheduleExplanation:
    """Traceable, evidence-backed explanation for a calculated schedule property."""

    category: str
    entity_type: str
    entity_id: str
    summary: str
    measured_value: str | int | float
    threshold_or_target: str | int | float | None
    mathematical_formula: str
    reason: str


@dataclass(frozen=True)
class ProductionScheduleMetrics:
    """Complete analytical schedule performance indicators, breakdowns, and explanations."""

    makespan_minutes: int
    total_weighted_tardiness: int
    late_order_count: int
    on_time_order_count: int
    total_order_count: int
    on_time_rate_pct: float
    order_metrics: dict[str, OrderMetrics]
    machine_metrics: dict[str, MachineMetrics]
    bottleneck: BottleneckAnalysis
    explanations: list[ScheduleExplanation]
