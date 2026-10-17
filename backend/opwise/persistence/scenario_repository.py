"""Repository managing Scenario and ScenarioComparison persistence.

Governed by DATA_AND_API.md Section 1.1 (Tables 8 & 9) and ADR-005.
All operations execute within caller-managed AsyncSessions.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from opwise.persistence.models import ScenarioComparisonModel, ScenarioModel


class ScenarioRepository:
    """Repository handling CRUD operations for disruption scenarios and comparisons."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, workspace_id: str, scenario_id: str) -> ScenarioModel | None:
        """Fetch a scenario by ID scoped strictly to workspace."""
        stmt = select(ScenarioModel).where(
            ScenarioModel.id == scenario_id,
            ScenarioModel.workspace_id == workspace_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_workspace(self, workspace_id: str) -> list[ScenarioModel]:
        """List all scenarios for a workspace ordered by creation date."""
        stmt = (
            select(ScenarioModel)
            .where(ScenarioModel.workspace_id == workspace_id)
            .order_by(ScenarioModel.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_scenario(
        self,
        workspace_id: str,
        baseline_schedule_id: str,
        name: str,
        disruption_type: str,
        disruption_delta_json: str,
        description: str | None = None,
    ) -> ScenarioModel:
        """Persist a new disruption scenario record."""
        scenario = ScenarioModel(
            workspace_id=workspace_id,
            baseline_schedule_id=baseline_schedule_id,
            name=name,
            description=description,
            disruption_type=disruption_type,
            disruption_delta_json=disruption_delta_json,
        )
        self.session.add(scenario)
        await self.session.flush()
        return scenario

    async def update_reoptimized_schedule(
        self, workspace_id: str, scenario_id: str, reoptimized_schedule_id: str
    ) -> ScenarioModel | None:
        """Attach reoptimized recovery schedule ID to scenario."""
        scenario = await self.get_by_id(workspace_id, scenario_id)
        if scenario is None:
            return None
        scenario.reoptimized_schedule_id = reoptimized_schedule_id
        await self.session.flush()
        return scenario

    async def delete_scenario(self, workspace_id: str, scenario_id: str) -> bool:
        """Delete a scenario and cascade comparison records."""
        scenario = await self.get_by_id(workspace_id, scenario_id)
        if scenario is None:
            return False
        await self.session.delete(scenario)
        await self.session.flush()
        return True

    async def save_comparison(
        self,
        scenario_id: str,
        baseline_schedule_id: str,
        compared_schedule_id: str,
        delta_makespan: int,
        delta_weighted_tardiness: int,
        delta_late_order_count: int,
        objective_diff_detected: bool,
        order_set_diff_detected: bool,
        status_diff_detected: bool,
        time_limit_diff_detected: bool,
        critical_path_divergence_json: str,
        unlike_comparison_warning: str | None = None,
    ) -> ScenarioComparisonModel:
        """Persist or update comparison record between baseline and compared schedules."""
        # Clean up existing comparison for this scenario if present
        stmt = delete(ScenarioComparisonModel).where(
            ScenarioComparisonModel.scenario_id == scenario_id
        )
        await self.session.execute(stmt)

        comparison = ScenarioComparisonModel(
            scenario_id=scenario_id,
            baseline_schedule_id=baseline_schedule_id,
            compared_schedule_id=compared_schedule_id,
            delta_makespan=delta_makespan,
            delta_weighted_tardiness=delta_weighted_tardiness,
            delta_late_order_count=delta_late_order_count,
            objective_diff_detected=objective_diff_detected,
            order_set_diff_detected=order_set_diff_detected,
            status_diff_detected=status_diff_detected,
            time_limit_diff_detected=time_limit_diff_detected,
            unlike_comparison_warning=unlike_comparison_warning,
            critical_path_divergence_json=critical_path_divergence_json,
        )
        self.session.add(comparison)
        await self.session.flush()
        return comparison

    async def get_comparison_by_scenario(self, scenario_id: str) -> ScenarioComparisonModel | None:
        """Fetch existing comparison record by scenario ID."""
        stmt = select(ScenarioComparisonModel).where(
            ScenarioComparisonModel.scenario_id == scenario_id
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
