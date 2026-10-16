"""Optimization service orchestrating CP-SAT solving, verification, and persistence.

Governed by DATA_AND_API.md Section 3.3, ADR-002, ADR-003, and PROJECT_RULES.md.
Preserves existing solver, verifier, and deterministic metrics engine contracts.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from opwise.api.schemas.schedule import (
    OptimizeRequest,
    OptimizeResponseData,
    ScheduledOperationResponse,
    ScheduleMetricsResponse,
    ScheduleTelemetryResponse,
    StageTelemetryResponse,
    VerificationReportResponse,
)
from opwise.domain.entities import (
    Factory,
    ObjectiveMode,
    Schedule,
    ScheduleKPIs,
    ScheduleStatus,
)
from opwise.domain.exceptions import (
    EmptyWorkspaceError,
    ResourceNotFoundError,
)
from opwise.domain.metrics import calculate_schedule_metrics
from opwise.domain.metrics_types import ProductionScheduleMetrics
from opwise.persistence.models import ScheduleModel
from opwise.persistence.repository import FactoryRepository, ScheduleRepository, WorkspaceRepository
from opwise.services.snapshot import reconstruct_factory_from_snapshot, serialize_factory_snapshot
from opwise.solver.engine import CPSATScheduler
from opwise.solver.solver_types import SolverConfig, SolverResult
from opwise.verifier.independent_verifier import ScheduleVerifier
from opwise.verifier.verification_types import VerificationReport


class OptimizationService:
    """Service coordinating solver execution, clean-room verification, and schedule persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workspace_repo = WorkspaceRepository(session)
        self.factory_repo = FactoryRepository(session)
        self.schedule_repo = ScheduleRepository(session)

    def _map_objective_mode(self, mode_str: str) -> ObjectiveMode:
        """Translate API objective string to domain ObjectiveMode enum."""
        mapping = {
            "PURE_MAKESPAN": ObjectiveMode.PURE_MAKESPAN,
            "PURE_WEIGHTED_TARDINESS": ObjectiveMode.PURE_WEIGHTED_TARDINESS,
            "HIERARCHICAL": ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC,
            "HIERARCHICAL_LEXICOGRAPHIC": ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC,
        }
        return mapping.get(mode_str.upper(), ObjectiveMode.PURE_MAKESPAN)

    def _extract_stage_telemetry(self, result: SolverResult) -> dict[str, Any] | None:
        """Extract stage telemetry dictionaries for hierarchical lexicographic solves."""
        if result.stage1_status is None and result.stage2_status is None:
            return None
        st1: dict[str, Any] = {}
        if result.stage1_status is not None:
            st1["status"] = result.stage1_status.value
            st1["objective_value"] = int(result.stage1_objective) if result.stage1_objective is not None else None
        st2: dict[str, Any] = {}
        if result.stage2_status is not None:
            st2["status"] = result.stage2_status.value
            st2["objective_value"] = int(result.stage2_objective) if result.stage2_objective is not None else None
        return {"stage1": st1, "stage2": st2}

    def _build_stage_telemetry_responses(
        self, result: SolverResult
    ) -> tuple[StageTelemetryResponse | None, StageTelemetryResponse | None]:
        """Build API stage telemetry response objects for stage1 and stage2."""
        st1 = (
            StageTelemetryResponse(
                status=result.stage1_status.value,
                objective_value=int(result.stage1_objective) if result.stage1_objective is not None else None,
            )
            if result.stage1_status
            else None
        )
        st2 = (
            StageTelemetryResponse(
                status=result.stage2_status.value,
                objective_value=int(result.stage2_objective) if result.stage2_objective is not None else None,
            )
            if result.stage2_status
            else None
        )
        return st1, st2

    def _build_unsuccessful_response(
        self, schedule_id: str, name: str, req: OptimizeRequest, result: SolverResult
    ) -> OptimizeResponseData:
        """Format response for an unsuccessful model outcome (infeasible, timeout, etc)."""
        term_reason = (
            "MODEL_PROVEN_INFEASIBLE"
            if result.status == ScheduleStatus.INFEASIBLE
            else f"SOLVER_STATUS_{result.status.value}"
        )
        st1, st2 = self._build_stage_telemetry_responses(result)
        return OptimizeResponseData(
            schedule_id=schedule_id,
            name=name,
            objective_type=req.objective_type,
            solver_status=result.status.value,
            verification_status="SKIPPED",
            stage1_telemetry=st1,
            stage2_telemetry=st2,
            metrics=ScheduleMetricsResponse(
                makespan_minutes=0,
                weighted_tardiness=0,
                late_order_count=0,
                on_time_rate=0.0,
                objective_value=int(result.objective_value) if result.objective_value is not None else None,
                best_objective_bound=int(result.best_bound) if result.best_bound is not None else None,
            ),
            solver_telemetry=ScheduleTelemetryResponse(
                wall_clock_time_seconds=result.wall_clock_seconds,
                deterministic_time=result.deterministic_time,
                termination_reason=term_reason,
            ),
            verification_report=None,
            scheduled_operations=[],
        )

    async def optimize(self, workspace_id: str, request: OptimizeRequest) -> OptimizeResponseData:
        """Execute CP-SAT solver, run independent verifier, and persist schedule atomically."""
        ws = await self.workspace_repo.get_by_id(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        factory = await self.factory_repo.get_factory(workspace_id)
        if factory is None:
            raise EmptyWorkspaceError()

        mode = self._map_objective_mode(request.objective_type)
        cfg = SolverConfig(
            time_limit_seconds=request.parameters.primary_time_budget_seconds,
            worker_threads=request.parameters.num_workers,
            random_seed=request.parameters.random_seed,
        )

        scheduler = CPSATScheduler()
        result = scheduler.solve(factory, objective_mode=mode, config=cfg)

        if result.schedule is None:
            return await self._handle_unsuccessful_solve(workspace_id, factory, request, mode, result)

        sched = result.schedule
        metrics = calculate_schedule_metrics(factory, sched)
        v_rep = result.verification_report
        snapshot_json = serialize_factory_snapshot(factory)
        stage_telem = self._extract_stage_telemetry(result)
        opt_gap = 0.0 if result.status == ScheduleStatus.OPTIMAL else None
        verif_status = "VERIFIED" if (v_rep and v_rep.is_valid) else "VERIFICATION_FAILED"

        saved_model = await self.schedule_repo.save_schedule(
            workspace_id=workspace_id,
            schedule=sched,
            name=request.name,
            wall_clock_seconds=result.wall_clock_seconds,
            deterministic_time=result.deterministic_time,
            input_snapshot_json=snapshot_json,
            stage_telemetry=stage_telem,
            objective_value=int(result.objective_value) if result.objective_value is not None else None,
            best_objective_bound=int(result.best_bound) if result.best_bound is not None else None,
            optimality_gap=opt_gap,
            verification_status=verif_status,
        )
        return self._build_optimization_response(saved_model, sched, metrics, result, v_rep)

    async def _handle_unsuccessful_solve(
        self,
        workspace_id: str,
        factory: Factory,
        request: OptimizeRequest,
        mode: ObjectiveMode,
        result: SolverResult,
    ) -> OptimizeResponseData:
        """Handle persistence and response formatting for unsuccessful solver outcomes."""
        unsuccessful_id = str(uuid.uuid4())
        empty_sched = Schedule(
            id=unsuccessful_id,
            workspace_id=workspace_id,
            status=result.status,
            objective_mode=mode,
            kpis=ScheduleKPIs(0, 0, 0, 0.0),
            scheduled_operations=[],
            verified=False,
        )
        stage_telem = self._extract_stage_telemetry(result)
        await self.schedule_repo.save_schedule(
            workspace_id=workspace_id,
            schedule=empty_sched,
            name=request.name,
            wall_clock_seconds=result.wall_clock_seconds,
            deterministic_time=result.deterministic_time,
            input_snapshot_json=serialize_factory_snapshot(factory),
            stage_telemetry=stage_telem,
            objective_value=int(result.objective_value) if result.objective_value is not None else None,
            best_objective_bound=int(result.best_bound) if result.best_bound is not None else None,
            optimality_gap=None,
            verification_status="SKIPPED",
        )
        return self._build_unsuccessful_response(unsuccessful_id, request.name, request, result)

    def _build_metrics_response(
        self, metrics: ProductionScheduleMetrics, result: SolverResult
    ) -> ScheduleMetricsResponse:
        """Construct ScheduleMetricsResponse from computed metrics and solver result."""
        return ScheduleMetricsResponse(
            makespan_minutes=metrics.makespan_minutes,
            weighted_tardiness=metrics.total_weighted_tardiness,
            late_order_count=metrics.late_order_count,
            on_time_rate=metrics.on_time_rate_pct,
            objective_value=int(result.objective_value) if result.objective_value is not None else None,
            best_objective_bound=int(result.best_bound) if result.best_bound is not None else None,
            optimality_gap=0.0 if result.status == ScheduleStatus.OPTIMAL else None,
        )

    def _build_optimization_response(
        self,
        saved_model: ScheduleModel,
        sched: Schedule,
        metrics: ProductionScheduleMetrics,
        result: SolverResult,
        v_rep: VerificationReport | None,
    ) -> OptimizeResponseData:
        """Format successful optimization result, telemetry, and metrics into response envelope."""
        ops_resp = [
            ScheduledOperationResponse(
                operation_id=op.operation_id,
                order_id=op.order_id,
                sequence_index=op.sequence_number,
                machine_id=op.machine_id,
                start_minute=op.start_minute,
                end_minute=op.end_minute,
                duration=op.processing_duration_minutes,
                slack_minutes=op.slack_minutes,
            )
            for op in sched.scheduled_operations
        ]
        metrics_resp = self._build_metrics_response(metrics, result)
        telem_resp = ScheduleTelemetryResponse(
            wall_clock_time_seconds=result.wall_clock_seconds,
            deterministic_time=result.deterministic_time,
            termination_reason=f"SOLVER_STATUS_{result.status.value}",
        )
        verif_resp = (
            VerificationReportResponse(
                is_valid=v_rep.is_valid,
                checks_run=len(v_rep.passed_rules) + len(v_rep.failed_rules),
                checks_passed=len(v_rep.passed_rules),
                violations=[v.message for v in v_rep.violations],
            )
            if v_rep
            else None
        )
        st1, st2 = self._build_stage_telemetry_responses(result)
        return OptimizeResponseData(
            schedule_id=saved_model.id,
            name=saved_model.name,
            objective_type=saved_model.objective_type,
            solver_status=saved_model.solver_status,
            verification_status=saved_model.verification_status,
            stage1_telemetry=st1,
            stage2_telemetry=st2,
            metrics=metrics_resp,
            solver_telemetry=telem_resp,
            verification_report=verif_resp,
            scheduled_operations=ops_resp,
        )

    async def verify_schedule(self, workspace_id: str, schedule_id: str) -> VerificationReportResponse:
        """Run on-demand clean-room verification against a stored schedule."""
        ws = await self.workspace_repo.get_by_id(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        sched_model = await self.schedule_repo.get_by_id(workspace_id, schedule_id)
        if sched_model is None:
            raise ResourceNotFoundError("Schedule", schedule_id)

        factory: Factory | None = None
        if sched_model.input_snapshot_json:
            factory = reconstruct_factory_from_snapshot(workspace_id, sched_model.input_snapshot_json)
        if factory is None:
            factory = await self.factory_repo.get_factory(workspace_id)
        if factory is None:
            raise ResourceNotFoundError("Factory", workspace_id)

        domain_schedule = self.schedule_repo.to_domain_schedule(sched_model)
        verifier = ScheduleVerifier()
        report = verifier.verify(factory, domain_schedule)

        return VerificationReportResponse(
            is_valid=report.is_valid,
            checks_run=len(report.passed_rules) + len(report.failed_rules),
            checks_passed=len(report.passed_rules),
            violations=[v.message for v in report.violations],
        )
