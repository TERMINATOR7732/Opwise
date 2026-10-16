"""Health check and system status router.

Governed by DATA_AND_API.md Section 3.2.
"""

from fastapi import APIRouter
from sqlalchemy import text

from opwise.api.dependencies import DbSessionDep
from opwise.api.schemas.common import SuccessEnvelope

router = APIRouter(tags=["health"])


@router.get("/health", response_model=SuccessEnvelope[dict[str, str]])
async def check_health(session: DbSessionDep) -> SuccessEnvelope[dict[str, str]]:
    """Verify application liveness and database connectivity."""
    db_status = "ok"
    try:
        await session.execute(text("SELECT 1;"))
    except Exception:
        db_status = "error"

    data = {
        "status": "healthy" if db_status == "ok" else "degraded",
        "database": db_status,
        "version": "0.1.0",
        "platform": "opwise-local",
    }
    return SuccessEnvelope(data=data)
