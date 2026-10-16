"""Integration tests for optimization endpoint, independent verification, and schedule inspection.

Governed by DATA_AND_API.md Section 3.3, TEST_AND_RELEASE_PLAN.md TM-05, and PROJECT_RULES.md.
"""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI

from alembic import command
from alembic.config import Config
from opwise.config import Settings
from opwise.domain.entities import ObjectiveMode, ScheduleStatus
from opwise.main import create_app
from opwise.persistence.database import create_database_engine, create_session_factory
from opwise.solver.solver_types import SolverResult


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
async def test_optimize_empty_workspace_error(app_with_db: FastAPI) -> None:
    """Case 1: Optimizing an empty workspace returns HTTP 422 EMPTY_WORKSPACE."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Empty WS"})
        ws_id = ws_res.json()["data"]["id"]

        resp = await client.post(f"/api/v1/workspaces/{ws_id}/optimize", json={"name": "Run on Empty"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "EMPTY_WORKSPACE"


@pytest.mark.asyncio
async def test_optimize_no_work_state_returns_200(app_with_db: FastAPI) -> None:
    """Case 2: Workspace with machines but 0 orders yields HTTP 200 NO_WORK_STATE."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "No Work WS"})
        ws_id = ws_res.json()["data"]["id"]

        # Setup 2 machines but 0 orders
        await client.put(
            f"/api/v1/workspaces/{ws_id}/factory",
            json={"machines": [{"external_id": "M1", "name": "Mill 1"}], "downtimes": [], "orders": []},
        )

        resp = await client.post(f"/api/v1/workspaces/{ws_id}/optimize", json={"name": "No Work Solve"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["solver_status"] == "NO_WORK_STATE"
        assert data["verification_status"] == "VERIFIED"
        assert data["metrics"]["makespan_minutes"] == 0
        assert data["metrics"]["on_time_rate"] == 100.0


@pytest.mark.asyncio
async def test_optimize_valid_factory_and_schedule_lifecycle(app_with_db: FastAPI) -> None:
    """Case 5: Valid factory optimizes to OPTIMAL, verifies cleanly, and persists."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Production WS"})
        ws_id = ws_res.json()["data"]["id"]

        # Setup standard 2-machine shop with 2 orders
        factory_payload = {
            "machines": [
                {"external_id": "M1", "name": "Milling Center"},
                {"external_id": "M2", "name": "Lathe Station"},
            ],
            "downtimes": [
                {"machine_id": "M1", "start_minute": 30, "end_minute": 50, "reason": "Maintenance"}
            ],
            "orders": [
                {
                    "external_id": "J1",
                    "name": "Order 1",
                    "release_minute": 0,
                    "due_minute": 100,
                    "tardiness_weight": 2,
                    "operations": [
                        {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 25},
                        {"sequence_index": 2, "machine_id": "M2", "processing_minutes": 30},
                    ],
                },
                {
                    "external_id": "J2",
                    "name": "Order 2",
                    "release_minute": 10,
                    "due_minute": 120,
                    "tardiness_weight": 1,
                    "operations": [
                        {"sequence_index": 1, "machine_id": "M2", "processing_minutes": 20},
                    ],
                },
            ],
        }
        await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)

        # 1. Trigger optimize solve
        opt_resp = await client.post(
            f"/api/v1/workspaces/{ws_id}/optimize",
            json={"name": "Optimal Batch", "objective_type": "PURE_MAKESPAN"},
        )
        assert opt_resp.status_code == 200
        opt_data = opt_resp.json()["data"]
        assert opt_data["solver_status"] == "OPTIMAL"
        assert opt_data["verification_status"] == "VERIFIED"
        assert opt_data["metrics"]["makespan_minutes"] > 0
        assert opt_data["verification_report"]["is_valid"] is True
        assert opt_data["verification_report"]["checks_passed"] == 8
        schedule_id = opt_data["schedule_id"]

        # 2. Inspect schedule in list
        list_resp = await client.get(f"/api/v1/workspaces/{ws_id}/schedules")
        assert list_resp.status_code == 200
        assert len(list_resp.json()["data"]) == 1

        # 3. Get schedule detail
        detail_resp = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{schedule_id}")
        assert detail_resp.status_code == 200
        assert len(detail_resp.json()["data"]["scheduled_operations"]) == 3

        # 4. Trigger on-demand independent verification
        verif_resp = await client.post(f"/api/v1/workspaces/{ws_id}/schedules/{schedule_id}/verify")
        assert verif_resp.status_code == 200
        assert verif_resp.json()["data"]["is_valid"] is True
        assert verif_resp.json()["data"]["checks_passed"] == 8


@pytest.mark.asyncio
async def test_optimize_infeasible_schedule(app_with_db: FastAPI) -> None:
    """TM-05.1 & Case 6: 100% downtime infeasible instance yields INFEASIBLE and SKIPPED verification."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Infeasible WS"})
        ws_id = ws_res.json()["data"]["id"]

        factory_payload = {
            "machines": [
                {"external_id": "M1", "name": "Mill 1"},
                {"external_id": "M2", "name": "Lathe 1"},
            ],
            "downtimes": [{"machine_id": "M1", "start_minute": 150, "end_minute": 250, "reason": "Maintenance"}],
            "orders": [
                {
                    "external_id": "ORD-1",
                    "name": "Tight Window Job",
                    "release_minute": 0,
                    "due_minute": 300,
                    "tardiness_weight": 1,
                    "operations": [
                        {"sequence_index": 1, "machine_id": "M2", "processing_minutes": 100},
                        {"sequence_index": 2, "machine_id": "M1", "processing_minutes": 100},
                    ],
                }
            ],
        }
        await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)

        resp = await client.post(
            f"/api/v1/workspaces/{ws_id}/optimize",
            json={"name": "Infeasible Run", "objective_type": "HIERARCHICAL"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["solver_status"] == "INFEASIBLE"
        assert data["verification_status"] == "SKIPPED"
        assert data["scheduled_operations"] == []


@pytest.mark.asyncio
async def test_cross_workspace_schedule_isolation(app_with_db: FastAPI) -> None:
    """Verify schedules are strictly isolated to their originating workspace."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Create Workspace A and Workspace B
        ws_a = (await client.post("/api/v1/workspaces", json={"name": "WS A"})).json()["data"]["id"]
        ws_b = (await client.post("/api/v1/workspaces", json={"name": "WS B"})).json()["data"]["id"]

        # Setup and optimize in Workspace A
        factory_a = {
            "machines": [{"external_id": "M1", "name": "Mill A"}],
            "downtimes": [],
            "orders": [
                {
                    "external_id": "ORD-A",
                    "name": "Job A",
                    "release_minute": 0,
                    "due_minute": 60,
                    "tardiness_weight": 1,
                    "operations": [{"sequence_index": 1, "machine_id": "M1", "processing_minutes": 20}],
                }
            ],
        }
        await client.put(f"/api/v1/workspaces/{ws_a}/factory", json=factory_a)
        opt_res = await client.post(f"/api/v1/workspaces/{ws_a}/optimize", json={"name": "Plan A"})
        sched_a_id = opt_res.json()["data"]["schedule_id"]

        # Attempt to access or verify Schedule A through Workspace B
        get_res = await client.get(f"/api/v1/workspaces/{ws_b}/schedules/{sched_a_id}")
        assert get_res.status_code == 404
        assert get_res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

        verif_res = await client.post(f"/api/v1/workspaces/{ws_b}/schedules/{sched_a_id}/verify")
        assert verif_res.status_code == 404
        assert verif_res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_hierarchical_stage_telemetry_persisted_and_returned(app_with_db: FastAPI) -> None:
    """Verify hierarchical lexicographic stage telemetry is populated in response and stored."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_id = (await client.post("/api/v1/workspaces", json={"name": "Lex WS"})).json()["data"]["id"]
        factory_payload = {
            "machines": [{"external_id": "M1", "name": "Mill 1"}],
            "downtimes": [],
            "orders": [
                {
                    "external_id": "O1",
                    "name": "Job 1",
                    "release_minute": 0,
                    "due_minute": 50,
                    "tardiness_weight": 2,
                    "operations": [{"sequence_index": 1, "machine_id": "M1", "processing_minutes": 25}],
                }
            ],
        }
        await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)
        opt_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/optimize",
            json={"name": "Lex Run", "objective_type": "HIERARCHICAL"},
        )
        assert opt_res.status_code == 200
        data = opt_res.json()["data"]
        assert data["stage1_telemetry"] is not None
        assert data["stage1_telemetry"]["status"] in ("OPTIMAL", "FEASIBLE")
        assert data["stage2_telemetry"] is not None

        sched_id = data["schedule_id"]
        detail_res = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{sched_id}")
        assert detail_res.status_code == 200
        detail_data = detail_res.json()["data"]
        assert detail_data["stage1_telemetry"] is not None
        assert detail_data["stage2_telemetry"] is not None


@pytest.mark.asyncio
async def test_solver_timeout_unsuccessful_outcome(app_with_db: FastAPI) -> None:
    """Verify solver timeout with 0 solutions returns HTTP 200 with SKIPPED verification."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_id = (await client.post("/api/v1/workspaces", json={"name": "Timeout WS"})).json()["data"]["id"]
        factory_payload = {
            "machines": [{"external_id": "M1", "name": "Mill 1"}],
            "downtimes": [],
            "orders": [
                {
                    "external_id": "O1",
                    "name": "Job 1",
                    "release_minute": 0,
                    "due_minute": 50,
                    "tardiness_weight": 1,
                    "operations": [{"sequence_index": 1, "machine_id": "M1", "processing_minutes": 25}],
                }
            ],
        }
        await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)

        mock_timeout_result = SolverResult(
            status=ScheduleStatus.TIMEOUT,
            schedule=None,
            objective_mode=ObjectiveMode.PURE_MAKESPAN,
            wall_clock_seconds=30.0,
            best_bound=45.0,
            deterministic_time=1.23,
        )

        with patch("opwise.services.optimization_service.CPSATScheduler.solve", return_value=mock_timeout_result):
            resp = await client.post(
                f"/api/v1/workspaces/{ws_id}/optimize",
                json={"name": "Timeout Solve", "objective_type": "PURE_MAKESPAN"},
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["solver_status"] == "TIMEOUT"
            assert data["verification_status"] == "SKIPPED"
            assert data["scheduled_operations"] == []
            assert data["metrics"]["makespan_minutes"] == 0
            assert data["metrics"]["best_objective_bound"] == 45
            assert data["solver_telemetry"]["wall_clock_time_seconds"] == 30.0

