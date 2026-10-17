"""Reports and data export endpoints for schedules, scenarios, and workspaces.

Governed by DATA_AND_API.md Section 3.2, Section 4.4, and SPECIFICATION.md Section 8.1.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Response

from opwise.api.dependencies import (
    ExportServiceDep,
    FactoryRepoDep,
    ReportServiceDep,
    ScenarioServiceDep,
    ScheduleRepoDep,
    WorkspaceRepoDep,
)
from opwise.api.schemas.common import SuccessEnvelope
from opwise.api.schemas.report import ScheduleReportResponse
from opwise.domain.exceptions import ResourceNotFoundError

router = APIRouter(tags=["reports"])


@router.get(
    "/workspaces/{workspace_id}/schedules/{schedule_id}/report",
    response_model=SuccessEnvelope[ScheduleReportResponse],
)
async def get_schedule_report(
    workspace_id: str,
    schedule_id: str,
    report_service: ReportServiceDep,
) -> SuccessEnvelope[ScheduleReportResponse]:
    """Retrieve multi-dimensional analytical breakdown, machine metrics, and order audits for a schedule."""
    report = await report_service.generate_schedule_report(workspace_id, schedule_id)
    return SuccessEnvelope(data=report)


@router.get("/workspaces/{workspace_id}/schedules/{schedule_id}/export")
async def export_schedule(
    workspace_id: str,
    schedule_id: str,
    format: Annotated[str, Query(pattern="^(csv|json)$")] = "csv",
    report_service: ReportServiceDep = None,  # type: ignore[assignment]
    export_service: ExportServiceDep = None,  # type: ignore[assignment]
    schedule_repo: ScheduleRepoDep = None,  # type: ignore[assignment]
    ws_repo: WorkspaceRepoDep = None,  # type: ignore[assignment]
) -> Response:
    """Download sanitized schedule performance report in CSV or JSON format."""
    ws = await ws_repo.get_by_id(workspace_id)
    if ws is None:
        raise ResourceNotFoundError("Workspace", workspace_id)

    schedule_model = await schedule_repo.get_by_id(workspace_id, schedule_id)
    if schedule_model is None:
        raise ResourceNotFoundError("Schedule", schedule_id)

    report = await report_service.generate_schedule_report(workspace_id, schedule_id)

    if format == "json":
        json_content = export_service.generate_schedule_json(report, schedule_model)
        return Response(
            content=json_content,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="schedule_{schedule_id}_report.json"'},
        )

    csv_content = export_service.generate_schedule_csv(report, schedule_model)
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="schedule_{schedule_id}_report.csv"'},
    )


@router.get("/workspaces/{workspace_id}/scenarios/{scenario_id}/export")
async def export_scenario(
    workspace_id: str,
    scenario_id: str,
    format: Annotated[str, Query(pattern="^(csv|json)$")] = "csv",
    scenario_service: ScenarioServiceDep = None,  # type: ignore[assignment]
    export_service: ExportServiceDep = None,  # type: ignore[assignment]
) -> Response:
    """Download disruption scenario configuration and comparison deltas in CSV or JSON format."""
    scenario = await scenario_service.get_scenario(workspace_id, scenario_id)

    comparison = None
    if scenario.comparison is not None:
        comparison = scenario.comparison

    if format == "json":
        json_content = export_service.generate_scenario_json(scenario, comparison)
        return Response(
            content=json_content,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="scenario_{scenario_id}_export.json"'},
        )

    csv_content = export_service.generate_scenario_csv(scenario, comparison)
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="scenario_{scenario_id}_export.csv"'},
    )


@router.get("/workspaces/{workspace_id}/export/{format}")
async def export_workspace(
    workspace_id: str,
    format: str,
    ws_repo: WorkspaceRepoDep,
    factory_repo: FactoryRepoDep,
    schedule_repo: ScheduleRepoDep,
    report_service: ReportServiceDep,
    export_service: ExportServiceDep,
) -> Response:
    """Export complete workspace factory configuration and latest schedule."""
    if format not in ("csv", "json"):
        raise ResourceNotFoundError("Format", format)

    ws = await ws_repo.get_by_id(workspace_id)
    if ws is None:
        raise ResourceNotFoundError("Workspace", workspace_id)

    schedules = await schedule_repo.list_by_workspace(workspace_id)
    if schedules:
        latest = schedules[0]
        schedule_model = await schedule_repo.get_by_id(workspace_id, latest.id)
        if schedule_model is not None:
            report = await report_service.generate_schedule_report(workspace_id, latest.id)
            if format == "json":
                json_content = export_service.generate_schedule_json(report, schedule_model)
                return Response(
                    content=json_content,
                    media_type="application/json; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="workspace_{workspace_id}_export.json"'},
                )
            csv_content = export_service.generate_schedule_csv(report, schedule_model)
            return Response(
                content=csv_content,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="workspace_{workspace_id}_export.csv"'},
            )

    # Empty schedules fallback
    if format == "json":
        return Response(
            content='{"workspace_id": "' + workspace_id + '", "schedules": []}',
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="workspace_{workspace_id}_export.json"'},
        )
    return Response(
        content="# WORKSPACE EXPORT\nWorkspace ID," + workspace_id + "\nSchedules,0\n",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="workspace_{workspace_id}_export.csv"'},
    )
