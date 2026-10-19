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

        # 3. Get schedule detail (including Gantt machine & downtime snapshots)
        detail_resp = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{schedule_id}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()["data"]
        assert len(detail_data["scheduled_operations"]) == 3
        assert len(detail_data["machines"]) == 2
        assert len(detail_data["downtimes"]) == 1
        assert detail_data["downtimes"][0]["start_minute"] == 30
        assert detail_data["downtimes"][0]["end_minute"] == 50


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


@pytest.mark.asyncio
async def test_optimize_execution_aware_with_plant_clock_and_lifecycle(app_with_db: FastAPI) -> None:
    """Milestone 15B end-to-end integration test: factory with clock and mixed lifecycle operations."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_id = (await client.post("/api/v1/workspaces", json={"name": "Execution-Aware WS"})).json()["data"]["id"]

        clock = 40
        factory_payload = {
            "current_time_minute": clock,
            "machines": [
                {"external_id": "M1", "name": "Mill 1"},
                {"external_id": "M2", "name": "Lathe 1"},
            ],
            "downtimes": [],
            "orders": [
                {
                    "external_id": "ORD1",
                    "name": "Job 1",
                    "release_minute": 0,
                    "due_minute": 100,
                    "tardiness_weight": 1,
                    "operations": [
                        {
                            "sequence_index": 1,
                            "machine_id": "M1",
                            "processing_minutes": 25,
                            "status": "COMPLETED",
                            "actual_start_minute": 0,
                            "actual_end_minute": 25,
                        },
                        {
                            "sequence_index": 2,
                            "machine_id": "M2",
                            "processing_minutes": 35,
                            "status": "IN_PROGRESS",
                            "actual_start_minute": 25,
                            "remaining_duration_minutes": 20,
                        },
                    ],
                },
                {
                    "external_id": "ORD2",
                    "name": "Job 2",
                    "release_minute": 10,
                    "due_minute": 120,
                    "tardiness_weight": 1,
                    "operations": [
                        {
                            "sequence_index": 1,
                            "machine_id": "M1",
                            "processing_minutes": 30,
                            "status": "PLANNED",
                        }
                    ],
                },
            ],
        }
        put_res = await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)
        assert put_res.status_code == 200
        assert put_res.json()["data"]["current_time_minute"] == clock

        # Optimize via API
        opt_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/optimize",
            json={"name": "Lifecycle Run", "objective_type": "PURE_MAKESPAN"},
        )
        assert opt_res.status_code == 200
        opt_data = opt_res.json()["data"]
        assert opt_data["solver_status"] == "OPTIMAL"
        assert opt_data["verification_status"] == "VERIFIED"
        assert opt_data["current_time_minute"] == clock

        sched_id = opt_data["schedule_id"]
        sched_ops = {op["operation_id"]: op for op in opt_data["scheduled_operations"]}
        assert len(sched_ops) == 3

        # Resolve generated machine IDs
        factory_data = put_res.json()["data"]
        m1_id = next(m["id"] for m in factory_data["machines"] if m["external_id"] == "M1")
        m2_id = next(m["id"] for m in factory_data["machines"] if m["external_id"] == "M2")

        # Find op by order and sequence
        op_list = opt_data["scheduled_operations"]
        op1 = next(op for op in op_list if op["sequence_index"] == 1 and op["machine_id"] == m1_id and op["status"] == "COMPLETED")
        assert op1["start_minute"] == 0
        assert op1["end_minute"] == 25
        assert op1["status"] == "COMPLETED"

        op2 = next(op for op in op_list if op["sequence_index"] == 2 and op["machine_id"] == m2_id)
        assert op2["status"] == "IN_PROGRESS"
        assert op2["start_minute"] == 25
        assert op2["end_minute"] == clock + 20  # 60

        op3 = next(op for op in op_list if op["sequence_index"] == 1 and op["status"] == "PLANNED")
        assert op3["status"] == "PLANNED"
        assert op3["machine_id"] == m1_id
        assert op3["start_minute"] >= clock  # >= 40
        assert op3["end_minute"] == op3["start_minute"] + 30

        # Retrieve schedule details
        detail_res = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{sched_id}")
        assert detail_res.status_code == 200
        detail_data = detail_res.json()["data"]
        assert detail_data["current_time_minute"] == clock
        assert len(detail_data["scheduled_operations"]) == 3
        assert any(op["status"] == "COMPLETED" for op in detail_data["scheduled_operations"])
        assert any(op["status"] == "IN_PROGRESS" for op in detail_data["scheduled_operations"])
        assert any(op["status"] == "PLANNED" for op in detail_data["scheduled_operations"])

        # Run on-demand verification
        verif_res = await client.post(f"/api/v1/workspaces/{ws_id}/schedules/{sched_id}/verify")
        assert verif_res.status_code == 200
        verif_data = verif_res.json()["data"]
        assert verif_data["is_valid"] is True
        assert verif_data["violations"] == []


@pytest.mark.asyncio
async def test_optimize_with_explicit_clock_override(app_with_db: FastAPI) -> None:
    """Explicit request.current_time_minute overrides workspace factory plant clock."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Clock Override WS"})
        ws_id = ws_res.json()["data"]["id"]

        # Factory has current_time_minute = 20
        factory_payload = {
            "current_time_minute": 20,
            "machines": [{"external_id": "M1", "name": "Workstation 1"}],
            "downtimes": [],
            "orders": [
                {
                    "external_id": "J1",
                    "name": "Job 1",
                    "release_minute": 0,
                    "due_minute": 100,
                    "tardiness_weight": 1,
                    "operations": [
                        {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 25, "status": "PLANNED"}
                    ],
                }
            ],
        }
        await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)

        # Optimize with explicit clock override = 50
        opt_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/optimize",
            json={
                "name": "Overridden Clock Solve",
                "objective_type": "PURE_MAKESPAN",
                "current_time_minute": 50,
            },
        )
        assert opt_res.status_code == 200
        data = opt_res.json()["data"]
        assert data["solver_status"] == "OPTIMAL"
        assert data["current_time_minute"] == 50
        sched_op = data["scheduled_operations"][0]
        assert sched_op["start_minute"] == 50
        assert sched_op["end_minute"] == 75


@pytest.mark.asyncio
async def test_persisted_schedule_immutable_after_factory_clock_change(app_with_db: FastAPI) -> None:
    """A persisted schedule re-verified on-demand uses its immutable snapshot regardless of factory clock advance."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Immutable Snapshot WS"})
        ws_id = ws_res.json()["data"]["id"]

        factory_payload = {
            "current_time_minute": 30,
            "machines": [{"external_id": "M1", "name": "Workstation 1"}],
            "downtimes": [],
            "orders": [
                {
                    "external_id": "J1",
                    "name": "Job 1",
                    "release_minute": 0,
                    "due_minute": 100,
                    "tardiness_weight": 1,
                    "operations": [
                        {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 20, "status": "PLANNED"}
                    ],
                }
            ],
        }
        await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)

        opt_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/optimize",
            json={"name": "Initial Solve", "objective_type": "PURE_MAKESPAN"},
        )
        sched_id = opt_res.json()["data"]["schedule_id"]
        assert opt_res.json()["data"]["current_time_minute"] == 30

        # Now advance factory plant clock to 100
        factory_payload["current_time_minute"] = 100
        await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)

        # On-demand verify old schedule: snapshot reconstructs factory at clock 30, schedule clock is 30 -> PASSES
        verif_res = await client.post(f"/api/v1/workspaces/{ws_id}/schedules/{sched_id}/verify")
        assert verif_res.status_code == 200
        assert verif_res.json()["data"]["is_valid"] is True


@pytest.mark.asyncio
async def test_optimize_infeasible_constraints_serializes_cleanly(app_with_db: FastAPI) -> None:
    """An infeasible model serializes solver_status=INFEASIBLE and verification_status=SKIPPED cleanly."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Infeasible WS"})
        ws_id = ws_res.json()["data"]["id"]

        # In-progress op on M1 has lock [30, 70). Future downtime on M1 is [40, 60).
        factory_payload = {
            "current_time_minute": 30,
            "machines": [{"external_id": "M1", "name": "Workstation 1"}],
            "downtimes": [
                {"external_id": "DT1", "machine_id": "M1", "start_minute": 40, "end_minute": 60, "reason": "Conflict"}
            ],
            "orders": [
                {
                    "external_id": "J1",
                    "name": "Job 1",
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
        }
        await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)

        opt_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/optimize",
            json={"name": "Infeasible Run", "objective_type": "PURE_MAKESPAN"},
        )
        assert opt_res.status_code == 200
        data = opt_res.json()["data"]
        assert data["solver_status"] == "INFEASIBLE"
        assert data["verification_status"] == "SKIPPED"
        assert data["scheduled_operations"] == []
        assert data["current_time_minute"] == 30




