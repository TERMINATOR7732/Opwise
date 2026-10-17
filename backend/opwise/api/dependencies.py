"""FastAPI dependency injection providers.

Governed by ARCHITECTURE.md and DATA_AND_API.md.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from opwise.persistence.repository import (
    FactoryRepository,
    ScheduleRepository,
    WorkspaceRepository,
)
from opwise.services.export_service import ExportService
from opwise.services.factory_service import FactoryService
from opwise.services.import_service import ImportService
from opwise.services.optimization_service import OptimizationService
from opwise.services.report_service import ReportService
from opwise.services.scenario_service import ScenarioService


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Dependency yielding a scoped async database session from the application sessionmaker."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_workspace_repository(session: DbSessionDep) -> WorkspaceRepository:
    """Dependency providing WorkspaceRepository."""
    return WorkspaceRepository(session)


def get_factory_repository(session: DbSessionDep) -> FactoryRepository:
    """Dependency providing FactoryRepository."""
    return FactoryRepository(session)


def get_schedule_repository(session: DbSessionDep) -> ScheduleRepository:
    """Dependency providing ScheduleRepository."""
    return ScheduleRepository(session)


def get_factory_service(session: DbSessionDep) -> FactoryService:
    """Dependency providing FactoryService."""
    return FactoryService(session)


def get_optimization_service(session: DbSessionDep) -> OptimizationService:
    """Dependency providing OptimizationService."""
    return OptimizationService(session)


def get_scenario_service(session: DbSessionDep) -> ScenarioService:
    """Dependency providing ScenarioService."""
    return ScenarioService(session)


def get_report_service(session: DbSessionDep) -> ReportService:
    """Dependency providing ReportService."""
    return ReportService(session)


def get_export_service() -> ExportService:
    """Dependency providing ExportService."""
    return ExportService()


def get_import_service(session: DbSessionDep) -> ImportService:
    """Dependency providing ImportService."""
    return ImportService(session)


WorkspaceRepoDep = Annotated[WorkspaceRepository, Depends(get_workspace_repository)]
FactoryRepoDep = Annotated[FactoryRepository, Depends(get_factory_repository)]
ScheduleRepoDep = Annotated[ScheduleRepository, Depends(get_schedule_repository)]
FactoryServiceDep = Annotated[FactoryService, Depends(get_factory_service)]
OptimizationServiceDep = Annotated[OptimizationService, Depends(get_optimization_service)]
ScenarioServiceDep = Annotated[ScenarioService, Depends(get_scenario_service)]
ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
ExportServiceDep = Annotated[ExportService, Depends(get_export_service)]
ImportServiceDep = Annotated[ImportService, Depends(get_import_service)]

