"""Application entrypoint and FastAPI application factory.

Governed by ARCHITECTURE.md, ADR-001, and PROJECT_RULES.md.
"""

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.exceptions import HTTPException as StarletteHTTPException

from opwise.api.error_handlers import (
    database_error_handler,
    generic_exception_handler,
    http_exception_handler,
    opwise_error_handler,
    validation_error_handler,
)
from opwise.api.routers import api_v1_router
from opwise.config import Settings, get_settings
from opwise.domain.exceptions import OpwiseError
from opwise.persistence.database import create_database_engine, create_session_factory

EXPECTED_ALEMBIC_REVISION = "004_add_workspace_clock"


async def verify_database_schema(
    engine: AsyncEngine, expected_revision: str = EXPECTED_ALEMBIC_REVISION
) -> None:
    """Verify that the database schema is initialized and matches expected revision (TM-07.3)."""
    async with engine.connect() as conn:
        try:
            result = await conn.execute(text("SELECT version_num FROM alembic_version;"))
            row = result.scalar_one_or_none()
            if row != expected_revision:
                raise RuntimeError(
                    f"Database schema mismatch: current revision '{row}' != expected '{expected_revision}'. "
                    "Run 'alembic upgrade head' before starting the application."
                )
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError(
                f"Database schema uninitialized or missing 'alembic_version' table. "
                f"Expected revision '{expected_revision}'. Run 'alembic upgrade head' before starting."
            ) from exc


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application resource lifecycle including database engine disposal."""
    settings: Settings = getattr(app.state, "settings", get_settings())
    engine = getattr(app.state, "engine", None)
    if engine is None:
        engine = create_database_engine(settings)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
    await verify_database_schema(engine)
    yield
    if hasattr(app.state, "engine") and app.state.engine:
        await app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """FastAPI application factory configuring routes, error handlers, and middleware."""
    cfg = settings or get_settings()

    app = FastAPI(
        title="Opwise Production Scheduling API",
        description="Local-first deterministic production planning and optimization platform.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = cfg

    # Configure CORS for local frontend development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register standardized error handlers
    app.add_exception_handler(OpwiseError, opwise_error_handler)
    app.add_exception_handler(SQLAlchemyOperationalError, database_error_handler)
    app.add_exception_handler(sqlite3.OperationalError, database_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Register versioned API router
    app.include_router(api_v1_router, prefix=cfg.api_prefix)

    return app


app = create_app()
