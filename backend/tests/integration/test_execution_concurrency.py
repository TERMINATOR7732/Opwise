"""Concurrency and transaction rollback tests for SQLite shop-floor execution dispatching.

Governed by Section 6 of Milestone 15D requirements.
Tests verify:
1. Competing concurrent requests cannot silently overwrite one another.
2. Concurrent advance requests with same initial expected clock yield exactly one 200 and one 409 STALE_EXECUTION_STATE.
3. Total transaction rollback on error leaves zero partial changes in database (clock unchanged, durations unreduced).
4. Competing concurrent operation start requests on the same machine allow only one to succeed.
"""

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator
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
def test_db_path() -> str:
    """Provide a temporary SQLite database initialized with all migrations to head."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        db_path = f.name
    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(ini_path.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(cfg, "head")
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def app_with_db(test_db_path: str) -> FastAPI:
    """Create a test FastAPI application bound to the migrated test SQLite database."""
    settings = Settings(db_url=f"sqlite+aiosqlite:///{test_db_path}")
    app = create_app(settings)
    engine = create_database_engine(settings)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    return app


@pytest.fixture
async def client(app_with_db: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an async HTTP test client."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_concurrent_clock_advancement_test_and_set(client: httpx.AsyncClient) -> None:
    """Test two concurrent clock advancement requests with the same expected clock."""
    # 1. Create workspace
    res = await client.post("/api/v1/workspaces", json={"name": "WS-Concurrent-Clock"})
    assert res.status_code == 201
    ws_id = res.json()["data"]["id"]

    factory_payload = {
        "machines": [{"external_id": "M1", "name": "M1"}],
        "downtimes": [],
        "orders": [
            {
                "external_id": "O1",
                "name": "O1",
                "release_minute": 0,
                "due_minute": 100,
                "tardiness_weight": 1,
                "operations": [
                    {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 50, "status": "PLANNED"}
                ],
            }
        ],
        "current_time_minute": 10,
    }
    await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)

    # 2. Fire two concurrent advance requests both expecting clock 10
    # Worker A wants to advance to 20; Worker B wants to advance to 30
    req_a = client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance",
        json={"target_time_minute": 20, "expected_current_time_minute": 10},
    )
    req_b = client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance",
        json={"target_time_minute": 30, "expected_current_time_minute": 10},
    )

    res_a, res_b = await asyncio.gather(req_a, req_b)
    status_codes = sorted([res_a.status_code, res_b.status_code])

    # Exactly one must succeed (200) and one must be rejected (409 STALE_EXECUTION_STATE)
    assert status_codes == [200, 409]

    # Verify error envelope on the failed request
    failed_res = res_a if res_a.status_code == 409 else res_b
    assert failed_res.json()["error"]["code"] == "STALE_EXECUTION_STATE"

    # Verify final clock is either 20 or 30 (never corrupt or reverted)
    status = await client.get(f"/api/v1/workspaces/{ws_id}/execution/status")
    final_clock = status.json()["data"]["current_time_minute"]
    assert final_clock in (20, 30)


@pytest.mark.asyncio
async def test_atomic_rollback_on_error(client: httpx.AsyncClient) -> None:
    """Test that if an advance fails validation, no changes persist in the database."""
    res = await client.post("/api/v1/workspaces", json={"name": "WS-Rollback"})
    assert res.status_code == 201
    ws_id = res.json()["data"]["id"]

    factory_payload = {
        "machines": [{"external_id": "M1", "name": "M1"}],
        "downtimes": [{"machine_id": "M1", "start_minute": 40, "end_minute": 60, "reason": "Test DT"}],
        "orders": [
            {
                "external_id": "O1",
                "name": "O1",
                "release_minute": 0,
                "due_minute": 100,
                "tardiness_weight": 1,
                "operations": [
                    {
                        "sequence_index": 1,
                        "machine_id": "M1",
                        "processing_minutes": 50,
                        "status": "IN_PROGRESS",
                        "actual_start_minute": 10,
                        "remaining_duration_minutes": 40,
                    }
                ],
            }
        ],
        "current_time_minute": 10,
    }
    await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)

    # Attempt advance to 45 (collides with downtime [40, 60))
    fail_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance",
        json={"target_time_minute": 45},
    )
    assert fail_res.status_code == 422
    assert fail_res.json()["error"]["code"] == "HISTORICAL_DOWNTIME_CONFLICT"

    # Verify clock and operation state remain completely unmutated
    status = await client.get(f"/api/v1/workspaces/{ws_id}/execution/status")
    assert status.json()["data"]["current_time_minute"] == 10
    active_op = status.json()["data"]["active_operations"][0]
    assert active_op["remaining_duration_minutes"] == 40
    assert active_op["actual_start_minute"] == 10


@pytest.mark.asyncio
async def test_concurrent_start_same_machine(client: httpx.AsyncClient) -> None:
    """Test two concurrent start operations on the same machine; only one can win."""
    res = await client.post("/api/v1/workspaces", json={"name": "WS-Concurrent-Start"})
    assert res.status_code == 201
    ws_id = res.json()["data"]["id"]

    factory_payload = {
        "machines": [{"external_id": "M1", "name": "M1"}],
        "downtimes": [],
        "orders": [
            {
                "external_id": "O1",
                "name": "O1",
                "release_minute": 0,
                "due_minute": 100,
                "tardiness_weight": 1,
                "operations": [
                    {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 20, "status": "PLANNED"}
                ],
            },
            {
                "external_id": "O2",
                "name": "O2",
                "release_minute": 0,
                "due_minute": 100,
                "tardiness_weight": 1,
                "operations": [
                    {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 20, "status": "PLANNED"}
                ],
            },
        ],
        "current_time_minute": 0,
    }
    put_res = await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)
    op1_id = put_res.json()["data"]["orders"][0]["operations"][0]["id"]
    op2_id = put_res.json()["data"]["orders"][1]["operations"][0]["id"]

    # Fire both start requests concurrently
    req1 = client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})
    req2 = client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op2_id}/start", json={})

    res1, res2 = await asyncio.gather(req1, req2)
    codes = sorted([res1.status_code, res2.status_code])

    # One succeeds (200) and the other fails (422 MACHINE_OCCUPIED or 409 STALE_EXECUTION_STATE)
    assert codes[0] == 200
    assert codes[1] in (409, 422)

    # Machine must have exactly one active operation
    status = await client.get(f"/api/v1/workspaces/{ws_id}/execution/status")
    assert len(status.json()["data"]["active_operations"]) == 1
