"""Unit tests for Opwise CP-SAT scheduler engine, status mapping, and objective reconciliation.

Governed by SOLVER_MODEL.md Section 5 and TEST_AND_RELEASE_PLAN.md Milestone 04.
"""

import copy
from dataclasses import replace

import pytest
from ortools.sat.python import cp_model

from opwise.domain.entities import (
    Factory,
    Machine,
    MachineDowntime,
    ObjectiveMode,
    Operation,
    ProductionOrder,
    ScheduleStatus,
)
from opwise.domain.exceptions import (
    EmptyWorkspaceError,
    OrderWithoutOperationsError,
    ReferentialIntegrityError,
)
from opwise.solver.engine import CPSATScheduler
from opwise.solver.solver_types import SolverConfig, SolverResult
from opwise.solver.status_mapper import map_cp_sat_status
from opwise.verifier.independent_verifier import (
    InvariantRule,
    ScheduleVerifier,
    VerificationStatus,
)


def test_timeout_status_handling() -> None:
    """Case 8: Microscopic time limit triggers honest TIMEOUT status without fabrication."""
    orders = [
        ProductionOrder(
            id=f"O{i}", order_code=f"J{i}", release_time_minutes=0, due_date_minutes=100, tardiness_weight=1,
            operations=[
                Operation(id=f"OP_{i}_1", order_id=f"O{i}", sequence_number=1, machine_id="M1", processing_duration_minutes=10),
                Operation(id=f"OP_{i}_2", order_id=f"O{i}", sequence_number=2, machine_id="M1", processing_duration_minutes=10),
            ],
        )
        for i in range(10)
    ]
    factory = Factory(workspace_id="WS-TEST-8", machines=[Machine(id="M1", name="M1")], downtimes=[], orders=orders)
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN, config=SolverConfig(time_limit_seconds=0.000001))

    assert result.status == ScheduleStatus.TIMEOUT
    assert result.schedule is None


def test_extraction_and_independent_verification(sample_factory: Factory) -> None:
    """Case 9 & 10: Solved candidate schedule passes clean-room independent verifier with verified=True."""
    scheduler = CPSATScheduler()
    result = scheduler.solve(sample_factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True
    assert result.verification_report is not None
    assert result.verification_report.is_valid is True
    assert len(result.verification_report.failed_rules) == 0


def test_weighted_tardiness_and_lexicographic_objectives(sample_factory: Factory) -> None:
    """Case 11: Single-objective tardiness and two-stage lexicographic optimization."""
    scheduler = CPSATScheduler()

    # 1. Pure Weighted Tardiness solve
    res_tardiness = scheduler.solve(sample_factory, ObjectiveMode.PURE_WEIGHTED_TARDINESS)
    assert res_tardiness.status == ScheduleStatus.OPTIMAL
    assert res_tardiness.schedule is not None
    assert res_tardiness.objective_value == res_tardiness.schedule.kpis.total_weighted_tardiness

    # 2. Hierarchical Lexicographic solve
    res_lex = scheduler.solve(sample_factory, ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC)
    assert res_lex.status == ScheduleStatus.OPTIMAL
    assert res_lex.schedule is not None
    assert res_lex.schedule.verified is True
    assert res_lex.stage1_status == ScheduleStatus.OPTIMAL
    assert res_lex.stage2_status == ScheduleStatus.OPTIMAL
    assert res_lex.schedule.objective_mode == ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC


def test_input_immutability_and_validation_guard(sample_factory: Factory) -> None:
    """Case 12: Factory is untouched during solve, and malformed inputs are caught at domain boundary."""
    scheduler = CPSATScheduler()
    factory_copy = copy.deepcopy(sample_factory)

    result = scheduler.solve(sample_factory, ObjectiveMode.PURE_MAKESPAN)
    assert result.status == ScheduleStatus.OPTIMAL
    assert sample_factory == factory_copy

    # Domain boundary rejects empty workspace
    with pytest.raises(EmptyWorkspaceError):
        scheduler.solve(Factory("WS-BAD", machines=[], downtimes=[], orders=[]))

    # Domain boundary rejects order with zero operations
    bad_order_factory = Factory(
        "WS-BAD-2", [Machine("M1", "M1")], [], [ProductionOrder("ORD-NO-OPS", "J1", 0, 100, 1, [])]
    )
    with pytest.raises(OrderWithoutOperationsError):
        scheduler.solve(bad_order_factory)

    # Domain boundary rejects referential integrity breach
    bad_ref_factory = Factory(
        "WS-BAD-3", [Machine("M1", "M1")], [],
        [ProductionOrder("ORD-1", "J1", 0, 100, 1, [Operation("OP-1", "ORD-1", 1, "M999", 10)])],
    )
    with pytest.raises(ReferentialIntegrityError):
        scheduler.solve(bad_ref_factory)


def test_no_work_state_deterministic_resolution() -> None:
    """Case 13: Factory with machines but 0 orders resolves immediately without running solver."""
    factory = Factory(
        workspace_id="WS-NO-WORK",
        machines=[Machine(id="M1", name="M1")],
        downtimes=[],
        orders=[],
    )
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.NO_WORK_STATE
    assert result.schedule is not None
    assert result.schedule.verified is True
    assert result.schedule.kpis.makespan_minutes == 0
    assert result.schedule.kpis.on_time_rate == 100.0
    assert result.wall_clock_seconds == 0.0


def test_status_mapper_comprehensive() -> None:
    """Test honest mapping across all CP-SAT raw status codes."""
    assert map_cp_sat_status(cp_model.OPTIMAL) == ScheduleStatus.OPTIMAL
    assert map_cp_sat_status(cp_model.FEASIBLE) == ScheduleStatus.FEASIBLE
    assert map_cp_sat_status(cp_model.INFEASIBLE) == ScheduleStatus.INFEASIBLE
    assert map_cp_sat_status(cp_model.MODEL_INVALID) == ScheduleStatus.MODEL_INVALID
    assert map_cp_sat_status(cp_model.UNKNOWN) == ScheduleStatus.TIMEOUT
    assert map_cp_sat_status(999) == ScheduleStatus.MODEL_INVALID


def test_downtime_beyond_horizon_and_clamping() -> None:
    """Test downtime starting at or beyond H is excluded per SOLVER_MODEL.md Section 3.3."""
    from opwise.domain.entities import MachineDowntime
    from opwise.solver.cp_sat_model import build_cp_sat_model

    factory = Factory(
        workspace_id="WS-HORIZON",
        machines=[Machine("M1", "M1")],
        downtimes=[
            MachineDowntime("DT-BEYOND", "M1", 500, 600),
            MachineDowntime("DT-INSIDE", "M1", 0, 10),
        ],
        orders=[
            ProductionOrder("O1", "J1", 0, 100, 1, [Operation("OP1", "O1", 1, "M1", 20)])
        ],
    )
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)
    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True

    # Direct model builder check
    m1 = build_cp_sat_model(factory, ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC, stage1_bound=None)
    assert m1.stage1_bound is None
    m2 = build_cp_sat_model(factory, ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC, stage1_bound=10)
    assert m2.stage1_bound == 10


def test_lexicographic_stage1_infeasible_skips_stage2() -> None:
    """If Stage 1 is proven INFEASIBLE, Stage 2 is skipped immediately."""
    from opwise.domain.entities import MachineDowntime

    factory = Factory(
        workspace_id="WS-LEX-INF",
        machines=[Machine("M1", "M1"), Machine("M2", "M2")],
        downtimes=[MachineDowntime("DT-1", "M1", 150, 250)],
        orders=[
            ProductionOrder(
                "ORD-1", "J1", 0, 300, 1,
                operations=[
                    Operation("OP-1", "ORD-1", 1, "M2", 100),
                    Operation("OP-2", "ORD-1", 2, "M1", 100),
                ],
            )
        ],
    )
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC)

    assert result.status == ScheduleStatus.INFEASIBLE
    assert result.schedule is None
    assert result.stage1_status == ScheduleStatus.INFEASIBLE


def test_lexicographic_reconciliation_stage1_feasible_never_optimal(sample_factory: Factory) -> None:
    """Case: If Stage 1 times out with FEASIBLE, overall status is strictly FEASIBLE, never OPTIMAL."""
    scheduler = CPSATScheduler()
    base_res = scheduler.solve(sample_factory, ObjectiveMode.PURE_MAKESPAN)
    assert base_res.schedule is not None

    s1 = SolverResult(
        status=ScheduleStatus.FEASIBLE,
        schedule=copy.deepcopy(base_res.schedule),
        objective_mode=ObjectiveMode.PURE_WEIGHTED_TARDINESS,
        wall_clock_seconds=1.0,
        objective_value=15.0,
    )
    s2 = SolverResult(
        status=ScheduleStatus.OPTIMAL,
        schedule=copy.deepcopy(base_res.schedule),
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        wall_clock_seconds=1.0,
        objective_value=165.0,
    )

    reconciled = scheduler._reconcile_lexicographic_outcomes(s1, s2)
    assert reconciled.status == ScheduleStatus.FEASIBLE
    assert reconciled.stage1_status == ScheduleStatus.FEASIBLE
    assert reconciled.stage2_status == ScheduleStatus.OPTIMAL
    assert reconciled.schedule is not None
    assert reconciled.schedule.status == ScheduleStatus.FEASIBLE


def test_lexicographic_reconciliation_stage2_timeout_with_incumbent(sample_factory: Factory) -> None:
    """Case: Stage 1 is OPTIMAL, Stage 2 times out with FEASIBLE incumbent; returns Stage 2 schedule."""
    scheduler = CPSATScheduler()
    base_res = scheduler.solve(sample_factory, ObjectiveMode.PURE_MAKESPAN)
    assert base_res.schedule is not None

    sched2 = copy.deepcopy(base_res.schedule)
    s1 = SolverResult(
        status=ScheduleStatus.OPTIMAL,
        schedule=copy.deepcopy(base_res.schedule),
        objective_mode=ObjectiveMode.PURE_WEIGHTED_TARDINESS,
        wall_clock_seconds=0.5,
        objective_value=15.0,
    )
    s2 = SolverResult(
        status=ScheduleStatus.FEASIBLE,
        schedule=sched2,
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        wall_clock_seconds=2.0,
        objective_value=170.0,
    )

    reconciled = scheduler._reconcile_lexicographic_outcomes(s1, s2)
    assert reconciled.status == ScheduleStatus.FEASIBLE
    assert reconciled.schedule is sched2
    assert reconciled.schedule.status == ScheduleStatus.FEASIBLE
    assert reconciled.stage1_status == ScheduleStatus.OPTIMAL
    assert reconciled.stage2_status == ScheduleStatus.FEASIBLE


def test_lexicographic_reconciliation_stage2_failure_fallback_to_stage1(sample_factory: Factory) -> None:
    """Case: Stage 1 is OPTIMAL, Stage 2 fails/times out with 0 solutions; falls back to Stage 1 schedule."""
    scheduler = CPSATScheduler()
    base_res = scheduler.solve(sample_factory, ObjectiveMode.PURE_MAKESPAN)
    assert base_res.schedule is not None

    sched1 = copy.deepcopy(base_res.schedule)
    s1 = SolverResult(
        status=ScheduleStatus.OPTIMAL,
        schedule=sched1,
        objective_mode=ObjectiveMode.PURE_WEIGHTED_TARDINESS,
        wall_clock_seconds=0.5,
        objective_value=15.0,
        verification_report=base_res.verification_report,
    )
    s2 = SolverResult(
        status=ScheduleStatus.TIMEOUT,
        schedule=None,
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        wall_clock_seconds=2.0,
    )

    reconciled = scheduler._reconcile_lexicographic_outcomes(s1, s2)
    assert reconciled.status == ScheduleStatus.FEASIBLE
    assert reconciled.schedule is sched1
    assert reconciled.schedule.status == ScheduleStatus.FEASIBLE


def test_multiple_downtimes_on_single_machine_non_collision() -> None:
    """Case: Machine with multiple disjoint downtimes serializes operations without collisions."""
    factory = Factory(
        workspace_id="WS-MULTI-DT",
        machines=[Machine(id="M1", name="Mill 1")],
        downtimes=[
            MachineDowntime(id="DT-1", machine_id="M1", start_minute=10, end_minute=20),
            MachineDowntime(id="DT-2", machine_id="M1", start_minute=30, end_minute=40),
        ],
        orders=[
            ProductionOrder("O1", "J1", 0, 100, 1, [Operation("OP1", "O1", 1, "M1", 10)]),
            ProductionOrder("O2", "J2", 0, 100, 1, [Operation("OP2", "O2", 1, "M1", 10)]),
            ProductionOrder("O3", "J3", 0, 100, 1, [Operation("OP3", "O3", 1, "M1", 10)]),
        ],
    )
    scheduler = CPSATScheduler()
    result = scheduler.solve(factory, ObjectiveMode.PURE_MAKESPAN)

    assert result.status == ScheduleStatus.OPTIMAL
    assert result.schedule is not None
    assert result.schedule.verified is True
    assert result.schedule.kpis.makespan_minutes == 50

    ops = sorted(result.schedule.scheduled_operations, key=lambda o: o.start_minute)
    assert [(o.start_minute, o.end_minute) for o in ops] == [(0, 10), (20, 30), (40, 50)]


def test_corrupted_schedule_rejected_by_verifier(sample_factory: Factory) -> None:
    """Case: Perturbing a solved candidate schedule triggers verifier rejection."""
    scheduler = CPSATScheduler()
    result = scheduler.solve(sample_factory, ObjectiveMode.PURE_MAKESPAN)
    assert result.schedule is not None
    assert result.schedule.verified is True

    # Mutate one operation to violate duration
    bad_op = replace(result.schedule.scheduled_operations[0], end_minute=80)
    corrupted = copy.deepcopy(result.schedule)
    corrupted.scheduled_operations[0] = bad_op
    verifier = ScheduleVerifier()
    report = verifier.verify(sample_factory, corrupted)

    assert report.is_valid is False
    assert report.status == VerificationStatus.VERIFICATION_FAILED
    assert InvariantRule.INV_2_DURATION_MACHINE in report.failed_rules


def test_pure_objective_modes_skip_stage1_preservation_rule(sample_factory: Factory) -> None:
    """Case: Pure objective modes do not enforce Stage 1 preservation bound."""
    scheduler = CPSATScheduler()
    for mode in [ObjectiveMode.PURE_MAKESPAN, ObjectiveMode.PURE_WEIGHTED_TARDINESS]:
        result = scheduler.solve(sample_factory, mode)
        assert result.status == ScheduleStatus.OPTIMAL
        assert result.verification_report is not None
        assert InvariantRule.INV_8_STAGE1_PRESERVATION not in result.verification_report.failed_rules


