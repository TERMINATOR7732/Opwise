"""Integration tests for Factory plant clock persistence, updates, defaults, and schedule-history isolation.

Governed by Milestone 15A.1 specification (AC-CLOCK-01 resolution).
Tests verify:
- Group A: Factory API persistence (PUT 45 -> response 45 -> GET 45 -> fresh session reload 45)
- Group B: Clock update (PUT 45 -> PUT 120 -> response/GET 120 with all entities intact)
- Group C: Default and validation (omission retention/default, legacy 0, negative rejection in API and DB check constraint, no masking)
- Group D: Schedule-history isolation (schedule clock 45 preserved when factory clock changes to 120, snapshot preserved)
"""

import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError

from alembic import command
from alembic.config import Config
from opwise.config import Settings
from opwise.main import create_app
from opwise.persistence.database import create_database_engine, create_session_factory
from opwise.persistence.models import WorkspaceModel
from opwise.persistence.repository import FactoryRepository


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
async def test_group_a_factory_api_persistence(client: httpx.AsyncClient, test_db_path: str) -> None:
    """Group A: PUT factory with current_time_minute=45 -> response 45 -> GET 45 -> fresh session reload 45."""
    # 1. Create workspace
    create_ws = await client.post("/api/v1/workspaces", json={"name": "WS-Clock-A"})
    assert create_ws.status_code == 201
    ws_id = create_ws.json()["data"]["id"]

    factory_payload = {
        "current_time_minute": 45,
        "machines": [{"external_id": "M1", "name": "Machine 1"}],
        "downtimes": [{"machine_id": "M1", "start_minute": 50, "end_minute": 60, "reason": "Maintenance"}],
        "orders": [
            {
                "external_id": "ORD-1",
                "name": "Order 1",
                "release_minute": 0,
                "due_minute": 100,
                "tardiness_weight": 1,
                "operations": [
                    {
                        "sequence_index": 1,
                        "machine_id": "M1",
                        "processing_minutes": 20,
                        "status": "COMPLETED",
                        "actual_start_minute": 0,
                        "actual_end_minute": 20,
                    },
                    {
                        "sequence_index": 2,
                        "machine_id": "M1",
                        "processing_minutes": 25,
                        "status": "IN_PROGRESS",
                        "actual_start_minute": 20,
                        "remaining_duration_minutes": 15,
                    },
                ],
            }
        ],
    }

    # 2. PUT factory configuration with current_time_minute = 45
    put_res = await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)
    assert put_res.status_code == 200
    put_data = put_res.json()["data"]
    # 3. Assert PUT response returns 45
    assert put_data["current_time_minute"] == 45
    assert len(put_data["machines"]) == 1
    assert len(put_data["orders"]) == 1

    # 4. GET factory configuration and assert response returns 45
    get_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
    assert get_res.status_code == 200
    get_data = get_res.json()["data"]
    assert get_data["current_time_minute"] == 45

    # 5. Force a completely fresh database engine & session reload
    settings = Settings(db_url=f"sqlite+aiosqlite:///{test_db_path}")
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        repo = FactoryRepository(session)
        loaded_factory = await repo.get_factory(ws_id)
        # 6. Assert reloaded response returns 45
        assert loaded_factory is not None
        assert loaded_factory.current_time_minute == 45

        ws_model = await session.get(WorkspaceModel, ws_id)
        assert ws_model is not None
        assert ws_model.current_time_minute == 45
    await engine.dispose()


@pytest.mark.asyncio
async def test_group_b_clock_update(client: httpx.AsyncClient) -> None:
    """Group B: Update factory clock from 45 to 120 and verify existing entities remain intact."""
    create_ws = await client.post("/api/v1/workspaces", json={"name": "WS-Clock-B"})
    assert create_ws.status_code == 201
    ws_id = create_ws.json()["data"]["id"]

    base_payload = {
        "current_time_minute": 45,
        "machines": [{"external_id": "M1", "name": "Machine 1"}],
        "downtimes": [{"machine_id": "M1", "start_minute": 130, "end_minute": 150, "reason": "Future Check"}],
        "orders": [
            {
                "external_id": "ORD-1",
                "name": "Order 1",
                "release_minute": 0,
                "due_minute": 200,
                "tardiness_weight": 2,
                "operations": [
                    {
                        "sequence_index": 1,
                        "machine_id": "M1",
                        "processing_minutes": 30,
                        "status": "COMPLETED",
                        "actual_start_minute": 0,
                        "actual_end_minute": 30,
                    }
                ],
            }
        ],
    }

    # 1. Save factory at clock 45
    put1 = await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=base_payload)
    assert put1.status_code == 200
    assert put1.json()["data"]["current_time_minute"] == 45

    # 2. Update factory clock to 120 without changing machines, orders, or downtimes
    updated_payload = dict(base_payload)
    updated_payload["current_time_minute"] = 120
    put2 = await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=updated_payload)
    assert put2.status_code == 200
    # 3. Assert response returns 120
    assert put2.json()["data"]["current_time_minute"] == 120

    # Fresh GET returns 120
    get2 = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
    assert get2.status_code == 200
    get2_data = get2.json()["data"]
    assert get2_data["current_time_minute"] == 120

    # 4. Assert machines, orders, operations, and downtimes remain intact
    assert len(get2_data["machines"]) == 1
    assert get2_data["machines"][0]["external_id"] == "M1"
    assert len(get2_data["downtimes"]) == 1
    assert get2_data["downtimes"][0]["start_minute"] == 130
    assert len(get2_data["orders"]) == 1
    assert get2_data["orders"][0]["external_id"] == "ORD-1"
    assert len(get2_data["orders"][0]["operations"]) == 1
    assert get2_data["orders"][0]["operations"][0]["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_group_c_default_retention_and_validation(client: httpx.AsyncClient, test_db_path: str) -> None:
    """Group C: Clock omission retains existing clock, legacy defaults to 0, negative rejected in API and DB."""
    create_ws = await client.post("/api/v1/workspaces", json={"name": "WS-Clock-C"})
    ws_id = create_ws.json()["data"]["id"]

    # 1. New workspace initial factory GET returns clock 0
    init_get = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
    assert init_get.status_code == 200
    assert init_get.json()["data"]["current_time_minute"] == 0

    # 2. PUT with explicit clock 60
    put_res = await client.put(
        f"/api/v1/workspaces/{ws_id}/factory",
        json={"current_time_minute": 60, "machines": [{"external_id": "M1", "name": "M1"}], "downtimes": [], "orders": []},
    )
    assert put_res.status_code == 200
    assert put_res.json()["data"]["current_time_minute"] == 60

    # 3. PUT omitting current_time_minute retains existing clock (60)
    put_omit = await client.put(
        f"/api/v1/workspaces/{ws_id}/factory",
        json={"machines": [{"external_id": "M1", "name": "M1 Modified"}], "downtimes": [], "orders": []},
    )
    assert put_omit.status_code == 200
    assert put_omit.json()["data"]["current_time_minute"] == 60

    # 4. Negative clocks rejected by API schema with 422
    bad_put = await client.put(
        f"/api/v1/workspaces/{ws_id}/factory",
        json={"current_time_minute": -10, "machines": [], "downtimes": [], "orders": []},
    )
    assert bad_put.status_code == 422

    # 5. Direct database write of negative clock violates check constraint
    settings = Settings(db_url=f"sqlite+aiosqlite:///{test_db_path}")
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        bad_ws = WorkspaceModel(name="Bad-Clock-WS", current_time_minute=-1)
        session.add(bad_ws)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_group_d_schedule_history_isolation(client: httpx.AsyncClient) -> None:
    """Group D: Changing factory clock to 120 does NOT alter previously persisted schedule clock 45."""
    create_ws = await client.post("/api/v1/workspaces", json={"name": "WS-Clock-D"})
    ws_id = create_ws.json()["data"]["id"]

    factory_payload = {
        "current_time_minute": 45,
        "machines": [{"external_id": "M1", "name": "Machine 1"}],
        "downtimes": [],
        "orders": [
            {
                "external_id": "ORD-1",
                "name": "Order 1",
                "release_minute": 0,
                "due_minute": 100,
                "tardiness_weight": 1,
                "operations": [
                    {
                        "sequence_index": 1,
                        "machine_id": "M1",
                        "processing_minutes": 20,
                        "status": "COMPLETED",
                        "actual_start_minute": 0,
                        "actual_end_minute": 20,
                    }
                ],
            }
        ],
    }
    await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)

    # 1. Optimize using the factory clock (45) by omitting current_time_minute in OptimizeRequest
    opt_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/optimize",
        json={"name": "Run-Clock-45", "objective_type": "PURE_MAKESPAN"},
    )
    assert opt_res.status_code == 200
    sched_id = opt_res.json()["data"]["schedule_id"]
    assert opt_res.json()["data"]["current_time_minute"] == 45

    # 2. Change factory clock to 120
    factory_payload["current_time_minute"] = 120
    put_update = await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)
    assert put_update.status_code == 200
    assert put_update.json()["data"]["current_time_minute"] == 120

    # 3. Fetch old schedule and assert its recorded clock remains 45
    sched_get = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{sched_id}")
    assert sched_get.status_code == 200
    assert sched_get.json()["data"]["current_time_minute"] == 45, "Historical schedule clock must not mutate"

    # 4. Create a new schedule without specifying clock; it should record new factory clock (120)
    opt_res_2 = await client.post(
        f"/api/v1/workspaces/{ws_id}/optimize",
        json={"name": "Run-Clock-120", "objective_type": "PURE_MAKESPAN"},
    )
    assert opt_res_2.status_code == 200
    sched_id_2 = opt_res_2.json()["data"]["schedule_id"]
    assert opt_res_2.json()["data"]["current_time_minute"] == 120

    # Verify both schedules retain their respective clocks
    s1 = (await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{sched_id}")).json()["data"]
    s2 = (await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{sched_id_2}")).json()["data"]
    assert s1["current_time_minute"] == 45
    assert s2["current_time_minute"] == 120
