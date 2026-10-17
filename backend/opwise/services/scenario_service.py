"""Service orchestrating disruption scenario simulation, reoptimization, and comparison.

Governed by SPECIFICATION.md Section 6, DATA_AND_API.md Section 1.1 (Tables 8 & 9), and ADR-005.
"""

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from opwise.api.schemas.scenario import (
    DisruptionDelta,
    DowntimeDisruptionItem,
    OperationDivergence,
    OrderDisruptionItem,
    ScenarioCompareRequest,
    ScenarioComparisonResponse,
    ScenarioCreateRequest,
    ScenarioReoptimizeRequest,
    ScenarioResponse,
)
from opwise.domain.entities import (
    Factory,
    ObjectiveMode,
    Schedule,
    ScheduleKPIs,
    ScheduleStatus,
)
from opwise.domain.exceptions import (
    DomainError,
    ResourceNotFoundError,
)
from opwise.persistence.models import (
    ScenarioComparisonModel,
    ScenarioModel,
    ScheduleModel,
)
from opwise.persistence.repository import ScheduleRepository, WorkspaceRepository
from opwise.persistence.scenario_repository import ScenarioRepository
from opwise.services.scenario_math import (
    UNLIKE_WARNING_TEXT,
    compute_operation_divergences,
    synthesize_disrupted_factory,
    validate_disruption,
)
from opwise.services.snapshot import (
    reconstruct_factory_from_snapshot,
    serialize_factory_snapshot,
)
from opwise.solver.engine import CPSATScheduler
from opwise.solver.solver_types import SolverConfig, SolverResult
from opwise.verifier.independent_verifier import ScheduleVerifier


def _parse_disruption_delta(json_str: str | None) -> DisruptionDelta:
    delta_dict = json.loads(json_str) if json_str else {}
    return DisruptionDelta(
        added_downtimes=[DowntimeDisruptionItem(**dt) for dt in delta_dict.get("added_downtimes", [])],
        added_orders=[OrderDisruptionItem(**o) for o in delta_dict.get("added_orders", [])],
    )


def _compute_schedule_deltas(
    base: ScheduleModel, comp: ScheduleModel
) -> tuple[int, int, int, float, bool, bool, bool, str | None]:
    delta_ms = comp.makespan_minutes - base.makespan_minutes
    delta_wt = comp.weighted_tardiness - base.weighted_tardiness
    delta_late = comp.late_order_count - base.late_order_count
    delta_otr = round(comp.on_time_rate - base.on_time_rate, 2)
    obj_diff = base.objective_type != comp.objective_type
    status_diff = base.solver_status != comp.solver_status
    order_diff = {op.order_id for op in base.scheduled_operations} != {
        op.order_id for op in comp.scheduled_operations
    }
    unlike = UNLIKE_WARNING_TEXT if (obj_diff or status_diff or order_diff) else None
    return delta_ms, delta_wt, delta_late, delta_otr, obj_diff, status_diff, order_diff, unlike


class ScenarioService:
    """Coordinates disruption simulation, reoptimization from t=0, and schedule comparisons."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workspace_repo = WorkspaceRepository(session)
        self.schedule_repo = ScheduleRepository(session)
        self.scenario_repo = ScenarioRepository(session)

    def _map_objective_mode(self, mode_str: str) -> ObjectiveMode:
        mapping = {
            "PURE_MAKESPAN": ObjectiveMode.PURE_MAKESPAN,
            "PURE_WEIGHTED_TARDINESS": ObjectiveMode.PURE_WEIGHTED_TARDINESS,
            "HIERARCHICAL": ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC,
            "HIERARCHICAL_LEXICOGRAPHIC": ObjectiveMode.HIERARCHICAL_LEXICOGRAPHIC,
        }
        return mapping.get(mode_str.upper(), ObjectiveMode.PURE_MAKESPAN)

    def _to_scenario_response(
        self, model: ScenarioModel, comparison: ScenarioComparisonResponse | None = None
    ) -> ScenarioResponse:
        return ScenarioResponse(
            id=model.id,
            workspace_id=model.workspace_id,
            baseline_schedule_id=model.baseline_schedule_id,
            reoptimized_schedule_id=model.reoptimized_schedule_id,
            name=model.name,
            description=model.description,
            disruption_type=model.disruption_type,
            disruption_delta=_parse_disruption_delta(model.disruption_delta_json),
            created_at=model.created_at,
            comparison=comparison,
        )

    def _to_comparison_response(self, comp: ScenarioComparisonModel) -> ScenarioComparisonResponse:
        div_data = json.loads(comp.critical_path_divergence_json) if comp.critical_path_divergence_json else []
        divergences = [OperationDivergence(**d) for d in div_data]
        return ScenarioComparisonResponse(
            id=comp.id,
            scenario_id=comp.scenario_id,
            baseline_schedule_id=comp.baseline_schedule_id,
            compared_schedule_id=comp.compared_schedule_id,
            delta_makespan=comp.delta_makespan,
            delta_weighted_tardiness=comp.delta_weighted_tardiness,
            delta_late_order_count=comp.delta_late_order_count,
            delta_on_time_rate=0.0,
            objective_diff_detected=comp.objective_diff_detected,
            order_set_diff_detected=comp.order_set_diff_detected,
            status_diff_detected=comp.status_diff_detected,
            time_limit_diff_detected=comp.time_limit_diff_detected,
            unlike_comparison_warning=comp.unlike_comparison_warning,
            diverged_operations=divergences,
            created_at=comp.created_at,
        )

    async def create_scenario(self, workspace_id: str, req: ScenarioCreateRequest) -> ScenarioResponse:
        ws = await self.workspace_repo.get_by_id(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        base_sched = await self.schedule_repo.get_by_id(workspace_id, req.baseline_schedule_id)
        if base_sched is None:
            raise ResourceNotFoundError("Schedule", req.baseline_schedule_id)

        base_factory = reconstruct_factory_from_snapshot(workspace_id, base_sched.input_snapshot_json)
        if base_factory is None:
            raise DomainError("Failed to reconstruct baseline factory snapshot.")

        validate_disruption(base_factory, req.disruption_type, req.disruption_delta)

        saved = await self.scenario_repo.create_scenario(
            workspace_id=workspace_id,
            baseline_schedule_id=req.baseline_schedule_id,
            name=req.name,
            disruption_type=req.disruption_type,
            disruption_delta_json=req.disruption_delta.model_dump_json(),
            description=req.description,
        )
        return self._to_scenario_response(saved)

    async def list_scenarios(self, workspace_id: str) -> list[ScenarioResponse]:
        ws = await self.workspace_repo.get_by_id(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)
        scenarios = await self.scenario_repo.list_by_workspace(workspace_id)
        return [self._to_scenario_response(s) for s in scenarios]

    async def get_scenario(self, workspace_id: str, scenario_id: str) -> ScenarioResponse:
        scenario = await self.scenario_repo.get_by_id(workspace_id, scenario_id)
        if scenario is None:
            raise ResourceNotFoundError("Scenario", scenario_id)
        comp_model = await self.scenario_repo.get_comparison_by_scenario(scenario.id)
        comp_resp = self._to_comparison_response(comp_model) if comp_model else None
        return self._to_scenario_response(scenario, comparison=comp_resp)

    async def delete_scenario(self, workspace_id: str, scenario_id: str) -> bool:
        deleted = await self.scenario_repo.delete_scenario(workspace_id, scenario_id)
        if not deleted:
            raise ResourceNotFoundError("Scenario", scenario_id)
        return True

    async def _handle_unsuccessful_reopt(
        self,
        workspace_id: str,
        scenario: ScenarioModel,
        base_sched: ScheduleModel,
        disrupted_factory: Factory,
        result: SolverResult,
    ) -> ScheduleModel:
        mode = self._map_objective_mode(base_sched.objective_type)
        empty_id = str(uuid.uuid4())
        empty_sched = Schedule(
            id=empty_id,
            workspace_id=workspace_id,
            status=result.status,
            objective_mode=mode,
            kpis=ScheduleKPIs(0, 0, 0, 0.0),
            scheduled_operations=[],
            verified=False,
        )
        return await self.schedule_repo.save_schedule(
            workspace_id=workspace_id,
            schedule=empty_sched,
            name=f"{scenario.name} (Recovery)",
            wall_clock_seconds=result.wall_clock_seconds,
            deterministic_time=result.deterministic_time,
            input_snapshot_json=serialize_factory_snapshot(disrupted_factory),
            verification_status="SKIPPED",
        )

    async def _save_reopt_schedule(
        self,
        workspace_id: str,
        scenario: ScenarioModel,
        disrupted_factory: Factory,
        result: SolverResult,
    ) -> ScheduleModel:
        sched = result.schedule
        assert sched is not None
        v_rep = ScheduleVerifier().verify(disrupted_factory, sched)
        v_stat = "VERIFIED" if v_rep.is_valid else "VERIFICATION_FAILED"
        return await self.schedule_repo.save_schedule(
            workspace_id=workspace_id,
            schedule=sched,
            name=f"{scenario.name} (Recovery)",
            wall_clock_seconds=result.wall_clock_seconds,
            deterministic_time=result.deterministic_time,
            input_snapshot_json=serialize_factory_snapshot(disrupted_factory),
            objective_value=int(result.objective_value) if result.objective_value is not None else None,
            best_objective_bound=int(result.best_bound) if result.best_bound is not None else None,
            optimality_gap=0.0 if result.status == ScheduleStatus.OPTIMAL else None,
            verification_status=v_stat,
        )

    async def reoptimize_scenario(
        self,
        workspace_id: str,
        scenario_id: str,
        params: ScenarioReoptimizeRequest | None = None,
    ) -> ScenarioComparisonResponse:
        scenario = await self.scenario_repo.get_by_id(workspace_id, scenario_id)
        if scenario is None:
            raise ResourceNotFoundError("Scenario", scenario_id)
        base_sched = await self.schedule_repo.get_by_id(workspace_id, scenario.baseline_schedule_id)
        if base_sched is None:
            raise ResourceNotFoundError("Schedule", scenario.baseline_schedule_id)

        base_factory = reconstruct_factory_from_snapshot(workspace_id, base_sched.input_snapshot_json)
        if base_factory is None:
            raise DomainError("Failed to reconstruct baseline factory snapshot.")

        delta = _parse_disruption_delta(scenario.disruption_delta_json)
        disrupted_factory = synthesize_disrupted_factory(workspace_id, base_factory, delta)

        p = params or ScenarioReoptimizeRequest()
        mode = self._map_objective_mode(base_sched.objective_type)
        cfg = SolverConfig(
            time_limit_seconds=p.primary_time_budget_seconds,
            worker_threads=p.num_workers,
            random_seed=p.random_seed,
        )
        result = CPSATScheduler().solve(disrupted_factory, objective_mode=mode, config=cfg)

        if result.schedule is None:
            saved_sched = await self._handle_unsuccessful_reopt(
                workspace_id, scenario, base_sched, disrupted_factory, result
            )
        else:
            saved_sched = await self._save_reopt_schedule(
                workspace_id, scenario, disrupted_factory, result
            )

        await self.scenario_repo.update_reoptimized_schedule(workspace_id, scenario_id, saved_sched.id)
        return await self.compare_schedules(
            workspace_id,
            ScenarioCompareRequest(
                baseline_schedule_id=scenario.baseline_schedule_id,
                compared_schedule_id=saved_sched.id,
                scenario_id=scenario.id,
            ),
        )

    async def _persist_comparison(
        self,
        workspace_id: str,
        scenario_id: str,
        req: ScenarioCompareRequest,
        deltas: tuple[int, int, int, float, bool, bool, bool, str | None],
        div_json: str,
    ) -> ScenarioComparisonResponse:
        scenario = await self.scenario_repo.get_by_id(workspace_id, scenario_id)
        if scenario is None:
            raise ResourceNotFoundError("Scenario", scenario_id)
        saved = await self.scenario_repo.save_comparison(
            scenario_id=scenario_id,
            baseline_schedule_id=req.baseline_schedule_id,
            compared_schedule_id=req.compared_schedule_id,
            delta_makespan=deltas[0],
            delta_weighted_tardiness=deltas[1],
            delta_late_order_count=deltas[2],
            objective_diff_detected=deltas[4],
            order_set_diff_detected=deltas[6],
            status_diff_detected=deltas[5],
            time_limit_diff_detected=False,
            critical_path_divergence_json=div_json,
            unlike_comparison_warning=deltas[7],
        )
        resp = self._to_comparison_response(saved)
        resp.delta_on_time_rate = deltas[3]
        return resp

    async def compare_schedules(
        self, workspace_id: str, req: ScenarioCompareRequest
    ) -> ScenarioComparisonResponse:
        base = await self.schedule_repo.get_by_id(workspace_id, req.baseline_schedule_id)
        if base is None:
            raise ResourceNotFoundError("Schedule", req.baseline_schedule_id)
        comp = await self.schedule_repo.get_by_id(workspace_id, req.compared_schedule_id)
        if comp is None:
            raise ResourceNotFoundError("Schedule", req.compared_schedule_id)

        deltas = _compute_schedule_deltas(base, comp)
        divergences = compute_operation_divergences(base.scheduled_operations, comp.scheduled_operations)
        div_json = json.dumps([d.model_dump() for d in divergences])

        if req.scenario_id:
            return await self._persist_comparison(
                workspace_id, req.scenario_id, req, deltas, div_json
            )

        return ScenarioComparisonResponse(
            id=str(uuid.uuid4()),
            scenario_id=None,
            baseline_schedule_id=req.baseline_schedule_id,
            compared_schedule_id=req.compared_schedule_id,
            delta_makespan=deltas[0],
            delta_weighted_tardiness=deltas[1],
            delta_late_order_count=deltas[2],
            delta_on_time_rate=deltas[3],
            objective_diff_detected=deltas[4],
            order_set_diff_detected=deltas[6],
            status_diff_detected=deltas[5],
            time_limit_diff_detected=False,
            unlike_comparison_warning=deltas[7],
            diverged_operations=divergences,
            created_at=comp.created_at,
        )
