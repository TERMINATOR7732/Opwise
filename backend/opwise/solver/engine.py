"""Deterministic CP-SAT scheduling engine and lexicographic optimization orchestrator.

Governed by SOLVER_MODEL.md Section 4 and Section 5.
"""

import time
from dataclasses import replace

from ortools.sat.python import cp_model

from opwise.domain.entities import (
    Factory,
    InputClassification,
    ObjectiveMode,
    Schedule,
    ScheduleKPIs,
    ScheduleStatus,
)
from opwise.domain.validators import validate_factory_for_optimization
from opwise.solver.cp_sat_model import build_cp_sat_model
from opwise.solver.schedule_extractor import extract_and_verify_schedule
from opwise.solver.solver_types import SolverConfig, SolverResult
from opwise.solver.status_mapper import map_cp_sat_status
from opwise.verifier.independent_verifier import ScheduleVerifier


class CPSATScheduler:
    """Production scheduling engine coordinating CP-SAT optimization and independent verification."""

    def solve(
        self,
        factory: Factory,
        objective_mode: ObjectiveMode = ObjectiveMode.PURE_MAKESPAN,
        config: SolverConfig | None = None,
    ) -> SolverResult:
        """Execute production scheduling under requested objective mode and configuration."""
        active_config = config or SolverConfig()

        # Step 1: Formal input classification & numerical domain validation
        validation = validate_factory_for_optimization(factory)
        if validation.classification == InputClassification.NO_WORK_STATE:
            return self._handle_no_work_state(factory, objective_mode)

        # Step 2: Route according to single-objective vs hierarchical lexicographic mode
        if objective_mode in {ObjectiveMode.PURE_MAKESPAN, ObjectiveMode.PURE_WEIGHTED_TARDINESS}:
            return self._solve_single_stage(
                factory=factory,
                objective_mode=objective_mode,
                config=active_config,
                stage1_bound=None,
            )

        return self._solve_lexicographic(factory, active_config)

    def _solve_single_stage(
        self,
        factory: Factory,
        objective_mode: ObjectiveMode,
        config: SolverConfig,
        stage1_bound: int | None = None,
    ) -> SolverResult:
        """Build and execute a single-stage CP-SAT model."""
        cp_model_bundle = build_cp_sat_model(factory, objective_mode, stage1_bound)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = config.time_limit_seconds
        solver.parameters.num_search_workers = config.worker_threads
        solver.parameters.random_seed = config.random_seed
        solver.parameters.log_search_progress = config.log_search_progress

        start_time = time.perf_counter()
        raw_status = solver.Solve(cp_model_bundle.model)
        wall_clock = time.perf_counter() - start_time

        solver_status = map_cp_sat_status(raw_status)

        if solver_status in {ScheduleStatus.OPTIMAL, ScheduleStatus.FEASIBLE}:
            schedule, report = extract_and_verify_schedule(
                factory=factory,
                solver=solver,
                var_bundles=cp_model_bundle.var_bundles,
                objective_mode=objective_mode,
                solver_status=solver_status,
                stage1_bound=stage1_bound,
            )
            return SolverResult(
                status=solver_status,
                schedule=schedule,
                objective_mode=objective_mode,
                wall_clock_seconds=wall_clock,
                objective_value=solver.ObjectiveValue(),
                best_bound=solver.BestObjectiveBound(),
                deterministic_time=float(solver.UserTime()),
                verification_report=report,
            )

        # Infeasible, Timeout, or Model Invalid: 0 operations returned
        return SolverResult(
            status=solver_status,
            schedule=None,
            objective_mode=objective_mode,
            wall_clock_seconds=wall_clock,
            objective_value=None,
            best_bound=None,
            deterministic_time=float(solver.UserTime()),
            verification_report=None,
        )

    def _solve_lexicographic(
        self,
        factory: Factory,
        config: SolverConfig,
    ) -> SolverResult:
        """Two-stage lexicographic solve with strict optimality gating (SOLVER_MODEL.md 5.1)."""
        t1 = max(0.5, config.time_limit_seconds / 2.0)
        stage1_cfg = replace(config, time_limit_seconds=t1)

        # Stage 1: Minimize weighted tardiness
        s1_res = self._solve_single_stage(
            factory=factory,
            objective_mode=ObjectiveMode.PURE_WEIGHTED_TARDINESS,
            config=stage1_cfg,
        )

        # If Stage 1 is unfeasible or timed out without solution, skip Stage 2
        if s1_res.status not in {ScheduleStatus.OPTIMAL, ScheduleStatus.FEASIBLE} or s1_res.schedule is None:
            return SolverResult(
                status=s1_res.status,
                schedule=None,
                objective_mode=ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC,
                wall_clock_seconds=s1_res.wall_clock_seconds,
                stage1_status=s1_res.status,
                stage1_objective=s1_res.objective_value,
            )

        z1_bound = int(round(s1_res.objective_value or 0))
        t2 = max(0.5, config.time_limit_seconds - s1_res.wall_clock_seconds)
        stage2_cfg = replace(config, time_limit_seconds=t2)

        # Stage 2: Minimize makespan subject to tardiness <= z1_bound
        s2_res = self._solve_single_stage(
            factory=factory,
            objective_mode=ObjectiveMode.PURE_MAKESPAN,
            config=stage2_cfg,
            stage1_bound=z1_bound,
        )

        return self._reconcile_lexicographic_outcomes(s1_res, s2_res)

    def _reconcile_lexicographic_outcomes(
        self,
        s1: SolverResult,
        s2: SolverResult,
    ) -> SolverResult:
        """Map Stage 1 and Stage 2 outcomes according to the formal state transition matrix."""
        total_wall_clock = s1.wall_clock_seconds + s2.wall_clock_seconds

        # Condition 1: Both Stage 1 and Stage 2 proven optimal
        if s1.status == ScheduleStatus.OPTIMAL and s2.status == ScheduleStatus.OPTIMAL:
            assert s2.schedule is not None
            s2.schedule.objective_mode = ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC
            return SolverResult(
                status=ScheduleStatus.OPTIMAL,
                schedule=s2.schedule,
                objective_mode=ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC,
                wall_clock_seconds=total_wall_clock,
                objective_value=s2.objective_value,
                best_bound=s2.best_bound,
                deterministic_time=s1.deterministic_time + s2.deterministic_time,
                verification_report=s2.verification_report,
                stage1_status=s1.status,
                stage1_objective=s1.objective_value,
                stage2_status=s2.status,
                stage2_objective=s2.objective_value,
            )

        # Condition 2: Stage 2 produced a feasible schedule (suboptimal or timeout)
        chosen_schedule = s2.schedule if s2.schedule is not None else s1.schedule
        assert chosen_schedule is not None
        chosen_schedule.status = ScheduleStatus.FEASIBLE
        chosen_schedule.objective_mode = ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC

        return SolverResult(
            status=ScheduleStatus.FEASIBLE,
            schedule=chosen_schedule,
            objective_mode=ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC,
            wall_clock_seconds=total_wall_clock,
            objective_value=s2.objective_value if s2.schedule is not None else s1.objective_value,
            best_bound=s2.best_bound if s2.schedule is not None else s1.best_bound,
            deterministic_time=s1.deterministic_time + s2.deterministic_time,
            verification_report=s2.verification_report if s2.schedule is not None else s1.verification_report,
            stage1_status=s1.status,
            stage1_objective=s1.objective_value,
            stage2_status=s2.status,
            stage2_objective=s2.objective_value,
        )

    def _handle_no_work_state(
        self,
        factory: Factory,
        objective_mode: ObjectiveMode,
    ) -> SolverResult:
        """Construct a verified zero-makespan schedule for Case 2 (No-Work State)."""
        schedule = Schedule(
            id="SCHED-NO-WORK",
            workspace_id=factory.workspace_id,
            status=ScheduleStatus.NO_WORK_STATE,
            objective_mode=objective_mode,
            kpis=ScheduleKPIs(
                makespan_minutes=0,
                total_weighted_tardiness=0,
                late_order_count=0,
                on_time_rate=100.0,
            ),
            scheduled_operations=[],
            verified=False,
        )
        report = ScheduleVerifier().verify(factory, schedule)
        schedule.verified = report.is_valid

        return SolverResult(
            status=ScheduleStatus.NO_WORK_STATE,
            schedule=schedule,
            objective_mode=objective_mode,
            wall_clock_seconds=0.0,
            objective_value=0.0,
            best_bound=0.0,
            verification_report=report,
        )
