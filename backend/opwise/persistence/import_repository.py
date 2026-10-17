"""Repository managing ImportJob persistence and staging state.

Governed by DATA_AND_API.md Section 1.1 (Table 10) and Section 4.3.
All operations execute within caller-managed AsyncSessions with workspace isolation.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opwise.persistence.models import ImportJobModel


class ImportJobRepository:
    """Repository managing batch import jobs and two-phase staging state."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, workspace_id: str, job_id: str) -> ImportJobModel | None:
        """Fetch an import job by ID scoped strictly to workspace."""
        stmt = select(ImportJobModel).where(
            ImportJobModel.id == job_id,
            ImportJobModel.workspace_id == workspace_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_workspace(self, workspace_id: str) -> list[ImportJobModel]:
        """List all import jobs for a workspace ordered by creation date."""
        stmt = (
            select(ImportJobModel)
            .where(ImportJobModel.workspace_id == workspace_id)
            .order_by(ImportJobModel.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_job(
        self,
        workspace_id: str,
        filename: str,
        status: str,
        staged_data_json: str,
        error_report_json: str | None = None,
    ) -> ImportJobModel:
        """Persist a new import job tracking staged data."""
        job = ImportJobModel(
            workspace_id=workspace_id,
            filename=filename,
            status=status,
            staged_data_json=staged_data_json,
            error_report_json=error_report_json,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def update_status(
        self,
        workspace_id: str,
        job_id: str,
        status: str,
    ) -> ImportJobModel | None:
        """Update import job status with workspace isolation."""
        job = await self.get_by_id(workspace_id, job_id)
        if job is None:
            return None
        job.status = status
        await self.session.flush()
        return job
