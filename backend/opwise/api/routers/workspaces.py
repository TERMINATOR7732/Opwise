"""Workspace management endpoints.

Governed by DATA_AND_API.md Section 3.2.
"""

from fastapi import APIRouter, HTTPException, Response, status

from opwise.api.dependencies import WorkspaceRepoDep
from opwise.api.schemas.common import SuccessEnvelope
from opwise.api.schemas.workspace import WorkspaceCreateRequest, WorkspaceResponse
from opwise.domain.exceptions import ResourceNotFoundError

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=SuccessEnvelope[list[WorkspaceResponse]])
async def list_workspaces(
    repo: WorkspaceRepoDep,
) -> SuccessEnvelope[list[WorkspaceResponse]]:
    """List all local workspaces."""
    models = await repo.list_all()
    data = [
        WorkspaceResponse(
            id=m.id,
            name=m.name,
            description=m.description,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in models
    ]
    return SuccessEnvelope(data=data)


@router.post("", response_model=SuccessEnvelope[WorkspaceResponse], status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreateRequest,
    repo: WorkspaceRepoDep,
) -> SuccessEnvelope[WorkspaceResponse]:
    """Create a new planning workspace."""
    existing = await repo.get_by_name(payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workspace with name '{payload.name}' already exists.",
        )
    created = await repo.create(name=payload.name, description=payload.description)
    await repo.session.commit()
    data = WorkspaceResponse(
        id=created.id,
        name=created.name,
        description=created.description,
        created_at=created.created_at,
        updated_at=created.updated_at,
    )
    return SuccessEnvelope(data=data)


@router.get("/{workspace_id}", response_model=SuccessEnvelope[WorkspaceResponse])
async def get_workspace(
    workspace_id: str,
    repo: WorkspaceRepoDep,
) -> SuccessEnvelope[WorkspaceResponse]:
    """Get metadata for a specific workspace."""
    ws = await repo.get_by_id(workspace_id)
    if ws is None:
        raise ResourceNotFoundError("Workspace", workspace_id)
    data = WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        description=ws.description,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )
    return SuccessEnvelope(data=data)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: str,
    repo: WorkspaceRepoDep,
) -> Response:
    """Delete a workspace and cascade-delete all associated factory data and schedules."""
    deleted = await repo.delete(workspace_id)
    if not deleted:
        raise ResourceNotFoundError("Workspace", workspace_id)
    await repo.session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
