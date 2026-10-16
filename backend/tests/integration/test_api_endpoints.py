"""Integration tests for FastAPI endpoints, envelopes, and workspace/factory CRUD.

Governed by DATA_AND_API.md Section 3 and TEST_AND_RELEASE_PLAN.md TM-06.
"""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from alembic import command
from alembic.config import Config
from opwise.config import Settings
from opwise.main import create_app
from opwise.persistence.database import create_database_engine, create_session_factory


@pytest.fixture
def app_with_db() -> Generator[FastAPI, None, None]:
    """Create a test application instance connected to a temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        db_path = f.name
    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(ini_path.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(cfg, "head")

    settings = Settings(db_url=f"sqlite+aiosqlite:///{db_path}")
    app = create_app(settings)
    engine = create_database_engine(settings)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)

    yield app

    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_health_check_endpoint(app_with_db: FastAPI) -> None:
    """Verify GET /api/v1/health returns standard success envelope with database status."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "healthy"
        assert body["data"]["database"] == "ok"
        assert "timestamp" in body["metadata"]
        assert "request_id" in body["metadata"]


@pytest.mark.asyncio
async def test_workspace_crud_lifecycle(app_with_db: FastAPI) -> None:
    """Verify workspace creation, retrieval, listing, duplicate rejection, and deletion."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Create workspace
        post_resp = await client.post("/api/v1/workspaces", json={"name": "Plant 1", "description": "Primary Plant"})
        assert post_resp.status_code == 201
        ws_id = post_resp.json()["data"]["id"]

        # 2. Reject duplicate workspace name
        dup_resp = await client.post("/api/v1/workspaces", json={"name": "Plant 1"})
        assert dup_resp.status_code == 400

        # 3. List workspaces
        list_resp = await client.get("/api/v1/workspaces")
        assert list_resp.status_code == 200
        assert len(list_resp.json()["data"]) == 1

        # 4. Get by ID
        get_resp = await client.get(f"/api/v1/workspaces/{ws_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["name"] == "Plant 1"

        # 5. Delete workspace
        del_resp = await client.delete(f"/api/v1/workspaces/{ws_id}")
        assert del_resp.status_code == 204

        # 6. Verify 404 after deletion
        not_found_resp = await client.get(f"/api/v1/workspaces/{ws_id}")
        assert not_found_resp.status_code == 404
        assert not_found_resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_factory_crud_and_dry_run_validation(app_with_db: FastAPI) -> None:
    """Verify factory replacement, retrieval, and dry-run validation endpoints."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Machining Shop"})
        ws_id = ws_res.json()["data"]["id"]

        factory_payload = {
            "machines": [
                {"external_id": "M1", "name": "5-Axis Mill"},
                {"external_id": "M2", "name": "Lathe Station"},
            ],
            "downtimes": [
                {"machine_id": "M1", "start_minute": 60, "end_minute": 90, "reason": "Tool Change"}
            ],
            "orders": [
                {
                    "external_id": "ORD-1",
                    "name": "Impeller Job",
                    "release_minute": 0,
                    "due_minute": 150,
                    "tardiness_weight": 2,
                    "operations": [
                        {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 45},
                        {"sequence_index": 2, "machine_id": "M2", "processing_minutes": 30},
                    ],
                }
            ],
        }

        # 1. Dry-run validate
        val_resp = await client.post(f"/api/v1/workspaces/{ws_id}/factory/validate", json=factory_payload)
        assert val_resp.status_code == 200
        assert val_resp.json()["data"]["is_valid"] is True

        # 2. Put factory
        put_resp = await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)
        assert put_resp.status_code == 200
        put_data = put_resp.json()["data"]
        assert len(put_data["machines"]) == 2
        assert len(put_data["downtimes"]) == 1
        assert len(put_data["orders"]) == 1

        # 3. Get factory
        get_resp = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
        assert get_resp.status_code == 200
        assert len(get_resp.json()["data"]["machines"]) == 2


@pytest.mark.asyncio
async def test_validation_error_envelope_formatting(app_with_db: FastAPI) -> None:
    """TM-06.1: Verify HTTP 422 validation errors conform to structured ErrorEnvelope."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Submit payload missing required field 'name'
        resp = await client.post("/api/v1/workspaces", json={})
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_FAILED"
        assert isinstance(body["error"]["details"], list)
        assert "timestamp" in body["metadata"]
