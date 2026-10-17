"""API routers package."""

from fastapi import APIRouter

from opwise.api.routers.factory import router as factory_router
from opwise.api.routers.health import router as health_router
from opwise.api.routers.optimization import router as optimization_router
from opwise.api.routers.scenarios import router as scenarios_router
from opwise.api.routers.schedules import router as schedules_router
from opwise.api.routers.workspaces import router as workspaces_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(workspaces_router)
api_v1_router.include_router(factory_router)
api_v1_router.include_router(optimization_router)
api_v1_router.include_router(schedules_router)
api_v1_router.include_router(scenarios_router)

__all__ = ["api_v1_router"]
