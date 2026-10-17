"""Disruption scenario and comparison API router.

Governed by DATA_AND_API.md Section 3.2, SPECIFICATION.md Section 6, and ADR-005.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Body, status

from opwise.api.dependencies import ScenarioServiceDep
from opwise.api.schemas.common import SuccessEnvelope
from opwise.api.schemas.scenario import (
    ScenarioCompareRequest,
    ScenarioComparisonResponse,
    ScenarioCreateRequest,
    ScenarioReoptimizeRequest,
    ScenarioResponse,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/scenarios", tags=["scenarios"])


@router.get("", response_model=SuccessEnvelope[list[ScenarioResponse]])
async def list_scenarios(
    workspace_id: str,
    scenario_service: ScenarioServiceDep,
) -> SuccessEnvelope[list[ScenarioResponse]]:
    """List all disruption scenarios branched in this workspace."""
    scenarios = await scenario_service.list_scenarios(workspace_id)
    return SuccessEnvelope(data=scenarios)


@router.post("", response_model=SuccessEnvelope[ScenarioResponse], status_code=status.HTTP_201_CREATED)
async def create_scenario(
    workspace_id: str,
    request: ScenarioCreateRequest,
    scenario_service: ScenarioServiceDep,
) -> SuccessEnvelope[ScenarioResponse]:
    """Create a new isolated disruption scenario branched from a baseline schedule."""
    scenario = await scenario_service.create_scenario(workspace_id, request)
    await scenario_service.session.commit()
    return SuccessEnvelope(data=scenario)


@router.post("/compare", response_model=SuccessEnvelope[ScenarioComparisonResponse])
async def compare_schedules(
    workspace_id: str,
    request: ScenarioCompareRequest,
    scenario_service: ScenarioServiceDep,
) -> SuccessEnvelope[ScenarioComparisonResponse]:
    """Compare a baseline schedule with a scenario recovery schedule with unlike disclosures."""
    comparison = await scenario_service.compare_schedules(workspace_id, request)
    await scenario_service.session.commit()
    return SuccessEnvelope(data=comparison)


@router.get("/{scenario_id}", response_model=SuccessEnvelope[ScenarioResponse])
async def get_scenario(
    workspace_id: str,
    scenario_id: str,
    scenario_service: ScenarioServiceDep,
) -> SuccessEnvelope[ScenarioResponse]:
    """Get scenario details, disruption parameters, and attached comparison results."""
    scenario = await scenario_service.get_scenario(workspace_id, scenario_id)
    return SuccessEnvelope(data=scenario)


@router.delete("/{scenario_id}", response_model=SuccessEnvelope[dict[str, Any]])
async def delete_scenario(
    workspace_id: str,
    scenario_id: str,
    scenario_service: ScenarioServiceDep,
) -> SuccessEnvelope[dict[str, Any]]:
    """Delete a scenario and its associated comparison records."""
    await scenario_service.delete_scenario(workspace_id, scenario_id)
    await scenario_service.session.commit()
    return SuccessEnvelope(data={"deleted": True, "scenario_id": scenario_id})


@router.post("/{scenario_id}/reoptimize", response_model=SuccessEnvelope[ScenarioComparisonResponse])
async def reoptimize_scenario(
    workspace_id: str,
    scenario_id: str,
    scenario_service: ScenarioServiceDep,
    request: Annotated[ScenarioReoptimizeRequest | None, Body()] = None,
) -> SuccessEnvelope[ScenarioComparisonResponse]:
    """Reoptimize factory schedule from t=0 under injected disruption constraints."""
    comparison = await scenario_service.reoptimize_scenario(workspace_id, scenario_id, request)
    await scenario_service.session.commit()
    return SuccessEnvelope(data=comparison)
