"""Deterministic CP-SAT scheduling engine and lexicographic optimization orchestrator.

Governed by SOLVER_MODEL.md Section 4 and Section 5.
"""

import time
import uuid
from dataclasses import replace

from ortools.sat.python import cp_model

from opwise.domain.entities import (
    Factory,
    InputClassification,
    ObjectiveMode,
    OperationStatus,
    Schedule,
    ScheduledOperation,
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

        all_ops = [op for order in factory.orders for op in order.operations]
        if all_ops and all(op.status == OperationStatus.COMPLETED for op in all_ops):
            return self._handle_all_completed_state(factory, objective_mode)

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
            current_time_minute=factory.current_time_minute,
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

    def _handle_all_completed_state(
        self,
        factory: Factory,
        objective_mode: ObjectiveMode,
    ) -> SolverResult:
        """Construct an optimal verified schedule when all operations are already completed."""
        scheduled_ops: list[ScheduledOperation] = []
        for order in factory.orders:
            sorted_ops = sorted(order.operations, key=lambda o: o.sequence_number)
            n_ops = len(sorted_ops)
            for i, op in enumerate(sorted_ops):
                s = op.actual_start_minute if op.actual_start_minute is not None else 0
                e = op.actual_end_minute if op.actual_end_minute is not None else s
                if i < n_ops - 1:
                    next_start_val = sorted_ops[i + 1].actual_start_minute
                    next_s: int = next_start_val if next_start_val is not None else e
                    slack = max(0, next_s - e)
                else:
                    slack = max(0, order.due_date_minutes - e)
                scheduled_ops.append(
                    ScheduledOperation(
                        operation_id=op.id,
                        order_id=order.id,
                        machine_id=op.machine_id,
                        sequence_number=op.sequence_number,
                        start_minute=s,
                        end_minute=e,
                        processing_duration_minutes=e - s,
                        slack_minutes=slack,
                        status=OperationStatus.COMPLETED,
                    )
                )

        verifier = ScheduleVerifier()
        temp_sched = Schedule(
            id="TEMP-RECOMPUTE",
            workspace_id=factory.workspace_id,
            status=ScheduleStatus.OPTIMAL,
            objective_mode=objective_mode,
            kpis=ScheduleKPIs(0, 0, 0, 100.0),
            scheduled_operations=scheduled_ops,
            current_time_minute=factory.current_time_minute,
        )
        recomputed = verifier.recompute_metrics(factory, temp_sched)
        kpis = ScheduleKPIs(
            makespan_minutes=recomputed.makespan_minutes,
            total_weighted_tardiness=recomputed.total_weighted_tardiness,
            late_order_count=recomputed.late_order_count,
            on_time_rate=recomputed.on_time_rate,
        )
        schedule = Schedule(
            id=f"SCHED-{uuid.uuid4().hex[:12].upper()}",
            workspace_id=factory.workspace_id,
            status=ScheduleStatus.OPTIMAL,
            objective_mode=objective_mode,
            kpis=kpis,
            scheduled_operations=scheduled_ops,
            verified=False,
            current_time_minute=factory.current_time_minute,
        )
        report = verifier.verify(factory, schedule)
        schedule.verified = report.is_valid

        obj_val = (
            float(kpis.makespan_minutes)
            if objective_mode == ObjectiveMode.PURE_MAKESPAN
            else float(kpis.total_weighted_tardiness)
        )
        st1_stat = (
            ScheduleStatus.OPTIMAL
            if objective_mode == ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC
            else None
        )
        st1_obj = (
            float(kpis.total_weighted_tardiness)
            if objective_mode == ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC
            else None
        )
        st2_stat = (
            ScheduleStatus.OPTIMAL
            if objective_mode == ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC
            else None
        )
        st2_obj = (
            float(kpis.makespan_minutes)
            if objective_mode == ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC
            else None
        )

        return SolverResult(
            status=ScheduleStatus.OPTIMAL,
            schedule=schedule,
            objective_mode=objective_mode,
            wall_clock_seconds=0.001,
            objective_value=obj_val,
            best_bound=obj_val,
            verification_report=report,
            stage1_status=st1_stat,
            stage1_objective=st1_obj,
            stage2_status=st2_stat,
            stage2_objective=st2_obj,
        )
