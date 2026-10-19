"""Data types, configuration models, and variable containers for the CP-SAT solver engine.

Governed by SOLVER_MODEL.md Section 4 and 5, and PROJECT_RULES.md Section 4.3.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from opwise.domain.entities import (
    ObjectiveMode,
    Operation,
    Schedule,
    ScheduleStatus,
)
from opwise.verifier.verification_types import VerificationReport

if TYPE_CHECKING:
    from ortools.sat.python import cp_model


@dataclass(frozen=True)
class SolverConfig:
    """Execution parameters controlling deterministic CP-SAT solving."""

    time_limit_seconds: float = 30.0
    worker_threads: int = 1
    random_seed: int = 42
    log_search_progress: bool = False


@dataclass(frozen=True)
class OperationVarBundle:
    """Bundle of CP-SAT variable handles for a single operation."""

    operation: Operation
    start_var: "cp_model.IntVar"
    end_var: "cp_model.IntVar"
    interval_var: "cp_model.IntervalVar | None" = None


@dataclass(frozen=True)
class SolverResult:
    """Complete diagnostic outcome of a CP-SAT optimization attempt."""

    status: ScheduleStatus
    schedule: Schedule | None
    objective_mode: ObjectiveMode
    wall_clock_seconds: float
    objective_value: float | None = None
    best_bound: float | None = None
    deterministic_time: float = 0.0
    verification_report: VerificationReport | None = None
    stage1_status: ScheduleStatus | None = None
    stage1_objective: float | None = None
    stage2_status: ScheduleStatus | None = None
    stage2_objective: float | None = None
