"""CP-SAT objective builders for makespan, weighted tardiness, and lexicographic clamping.

Governed by SOLVER_MODEL.md Section 4.1, 4.2, and Section 5.1.
"""

from ortools.sat.python import cp_model

from opwise.domain.entities import ProductionOrder
from opwise.solver.solver_types import OperationVarBundle


def configure_makespan_objective(
    model: cp_model.CpModel,
    orders: list[ProductionOrder],
    var_bundles: dict[str, OperationVarBundle],
    horizon: int,
) -> cp_model.IntVar:
    """Formulate min C_max objective: lower-bounded by the completion of all order final operations."""
    makespan_var = model.NewIntVar(0, horizon, "makespan")

    for order in orders:
        if not order.operations:
            continue
        last_op = max(order.operations, key=lambda o: o.sequence_number)
        bundle = var_bundles.get(last_op.id)
        if bundle:
            model.Add(makespan_var >= bundle.end_var)

    model.Minimize(makespan_var)
    return makespan_var


def configure_weighted_tardiness_objective(
    model: cp_model.CpModel,
    orders: list[ProductionOrder],
    var_bundles: dict[str, OperationVarBundle],
    horizon: int,
) -> cp_model.IntVar:
    """Formulate min sum(w_j * T_j) objective with T_j = max(0, C_j - d_j)."""
    tardiness_vars: list[cp_model.IntVar] = []
    weights: list[int] = []

    for order in orders:
        if not order.operations:
            continue
        last_op = max(order.operations, key=lambda o: o.sequence_number)
        bundle = var_bundles.get(last_op.id)
        if not bundle:
            continue

        tardiness_var = model.NewIntVar(0, horizon, f"tardiness_{order.id}")
        model.Add(tardiness_var >= bundle.end_var - order.due_date_minutes)
        model.Add(tardiness_var >= 0)
        tardiness_vars.append(tardiness_var)
        weights.append(order.tardiness_weight)

    if not tardiness_vars:
        zero_var = model.NewIntVar(0, 0, "zero_tardiness")
        model.Minimize(zero_var)
        return zero_var

    max_tardiness_bound = max(1, horizon * max(1, sum(weights)))
    total_weighted_tardiness = model.NewIntVar(0, max_tardiness_bound, "total_weighted_tardiness")
    model.Add(total_weighted_tardiness == cp_model.LinearExpr.WeightedSum(tardiness_vars, weights))
    model.Minimize(total_weighted_tardiness)
    return total_weighted_tardiness


def add_tardiness_bound_constraint(
    model: cp_model.CpModel,
    orders: list[ProductionOrder],
    var_bundles: dict[str, OperationVarBundle],
    horizon: int,
    max_weighted_tardiness: int,
) -> None:
    """Clamp Stage 2 solve with proven Stage 1 optimal bound: sum(w_j * T_j) <= Z_1*."""
    tardiness_vars: list[cp_model.IntVar] = []
    weights: list[int] = []

    for order in orders:
        if not order.operations:
            continue
        last_op = max(order.operations, key=lambda o: o.sequence_number)
        bundle = var_bundles.get(last_op.id)
        if not bundle:
            continue

        tardiness_var = model.NewIntVar(0, horizon, f"tardiness_bound_{order.id}")
        model.Add(tardiness_var >= bundle.end_var - order.due_date_minutes)
        model.Add(tardiness_var >= 0)
        tardiness_vars.append(tardiness_var)
        weights.append(order.tardiness_weight)

    if tardiness_vars:
        model.Add(cp_model.LinearExpr.WeightedSum(tardiness_vars, weights) <= max_weighted_tardiness)
