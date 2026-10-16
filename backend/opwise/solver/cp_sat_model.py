"""Model builder translating shop floor domain data into Google OR-Tools CP-SAT formulation.

Governed by SOLVER_MODEL.md Section 3 and Section 4.
"""

from dataclasses import dataclass

from ortools.sat.python import cp_model

from opwise.domain.downtime import (
    calculate_effective_horizon,
    normalize_machine_downtimes,
)
from opwise.domain.entities import (
    Factory,
    ObjectiveMode,
)
from opwise.solver.constraints import (
    add_machine_exclusivity_and_downtime,
    add_precedence_constraints,
    add_release_time_constraints,
    build_operation_intervals,
)
from opwise.solver.objectives import (
    add_tardiness_bound_constraint,
    configure_makespan_objective,
    configure_weighted_tardiness_objective,
)
from opwise.solver.solver_types import OperationVarBundle


@dataclass(frozen=True)
class CPSATModel:
    """Configured CP-SAT optimization model and variable lookup tables."""

    model: cp_model.CpModel
    var_bundles: dict[str, OperationVarBundle]
    horizon: int
    objective_mode: ObjectiveMode
    stage1_bound: int | None = None


def build_cp_sat_model(
    factory: Factory,
    objective_mode: ObjectiveMode,
    stage1_bound: int | None = None,
) -> CPSATModel:
    """Construct an integer CP-SAT model from validated factory parameters and chosen objective."""
    norm = normalize_machine_downtimes(factory.downtimes)
    horizon = calculate_effective_horizon(factory.orders, norm.merged_downtimes)

    model = cp_model.CpModel()
    var_bundles = build_operation_intervals(model, factory.orders, horizon)

    add_release_time_constraints(model, factory.orders, var_bundles)
    add_precedence_constraints(model, factory.orders, var_bundles)
    add_machine_exclusivity_and_downtime(
        model,
        factory.machines,
        norm.merged_downtimes,
        var_bundles,
        horizon,
    )

    if objective_mode == ObjectiveMode.PURE_MAKESPAN:
        configure_makespan_objective(model, factory.orders, var_bundles, horizon)
        if stage1_bound is not None:
            add_tardiness_bound_constraint(
                model,
                factory.orders,
                var_bundles,
                horizon,
                stage1_bound,
            )
    elif objective_mode == ObjectiveMode.PURE_WEIGHTED_TARDINESS:
        configure_weighted_tardiness_objective(model, factory.orders, var_bundles, horizon)
    elif objective_mode == ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC:
        # Hierarchical Stage 1: minimize weighted tardiness; Stage 2 handled by orchestrator engine
        if stage1_bound is None:
            configure_weighted_tardiness_objective(model, factory.orders, var_bundles, horizon)
        else:
            configure_makespan_objective(model, factory.orders, var_bundles, horizon)
            add_tardiness_bound_constraint(
                model,
                factory.orders,
                var_bundles,
                horizon,
                stage1_bound,
            )

    return CPSATModel(
        model=model,
        var_bundles=var_bundles,
        horizon=horizon,
        objective_mode=objective_mode,
        stage1_bound=stage1_bound,
    )
