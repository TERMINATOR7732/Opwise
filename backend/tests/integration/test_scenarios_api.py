"""Integration tests for Disruption Scenarios & Recovery Analysis.

Governed by SPECIFICATION.md Section 6, DATA_AND_API.md Section 3.2, and ADR-005.
"""

import os
import tempfile
import uuid
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
    """Create test application instance connected to a temporary SQLite database."""
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


async def _setup_workspace_and_baseline(
    client: httpx.AsyncClient, name: str | None = None
) -> tuple[str, str]:
    """Helper to create a populated factory workspace and generate a baseline schedule."""
    ws_name = name or f"Factory WS {uuid.uuid4().hex[:8]}"
    ws_res = await client.post("/api/v1/workspaces", json={"name": ws_name})
    ws_id = ws_res.json()["data"]["id"]

    factory_payload = {
        "machines": [
            {"external_id": "M1", "name": "Milling Center"},
            {"external_id": "M2", "name": "Lathe Station"},
        ],
        "downtimes": [],
        "orders": [
            {
                "external_id": "ORD-1",
                "name": "Order 1",
                "release_minute": 0,
                "due_minute": 100,
                "tardiness_weight": 2,
                "operations": [
                    {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 30},
                    {"sequence_index": 2, "machine_id": "M2", "processing_minutes": 20},
                ],
            }
        ],
    }
    await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)

    opt_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/optimize",
        json={"name": "Baseline Schedule", "objective_type": "PURE_MAKESPAN"},
    )
    assert opt_res.status_code == 200
    baseline_id = opt_res.json()["data"]["schedule_id"]
    return ws_id, baseline_id


@pytest.mark.asyncio
async def test_scenario_crud_lifecycle(app_with_db: FastAPI) -> None:
    """Test full CRUD lifecycle of an isolated disruption scenario."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_id, baseline_id = await _setup_workspace_and_baseline(client)

        factory_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
        m1_id = factory_res.json()["data"]["machines"][0]["id"]

        create_payload = {
            "name": "Outage Scenario",
            "baseline_schedule_id": baseline_id,
            "disruption_type": "MACHINE_DOWNTIME",
            "disruption_delta": {
                "added_downtimes": [
                    {"machine_id": m1_id, "start_minute": 10, "end_minute": 25, "reason": "Emergency maintenance"}
                ]
            },
        }
        res = await client.post(f"/api/v1/workspaces/{ws_id}/scenarios", json=create_payload)
        assert res.status_code == 201
        scen_data = res.json()["data"]
        scen_id = scen_data["id"]
        assert scen_data["name"] == "Outage Scenario"
        assert scen_data["baseline_schedule_id"] == baseline_id
        assert scen_data["reoptimized_schedule_id"] is None

        list_res = await client.get(f"/api/v1/workspaces/{ws_id}/scenarios")
        assert list_res.status_code == 200
        assert len(list_res.json()["data"]) == 1

        get_res = await client.get(f"/api/v1/workspaces/{ws_id}/scenarios/{scen_id}")
        assert get_res.status_code == 200
        assert get_res.json()["data"]["id"] == scen_id

        del_res = await client.delete(f"/api/v1/workspaces/{ws_id}/scenarios/{scen_id}")
        assert del_res.status_code == 200
        assert del_res.json()["data"]["deleted"] is True

        list_after = await client.get(f"/api/v1/workspaces/{ws_id}/scenarios")
        assert len(list_after.json()["data"]) == 0


@pytest.mark.asyncio
async def test_scenario_validation_referential_integrity(app_with_db: FastAPI) -> None:
    """Ensure invalid machines or inverted downtime windows are rejected."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_id, baseline_id = await _setup_workspace_and_baseline(client)

        invalid_m_payload = {
            "name": "Invalid Machine Scenario",
            "baseline_schedule_id": baseline_id,
            "disruption_type": "MACHINE_DOWNTIME",
            "disruption_delta": {
                "added_downtimes": [{"machine_id": "non-existent-m", "start_minute": 10, "end_minute": 30}]
            },
        }
        res = await client.post(f"/api/v1/workspaces/{ws_id}/scenarios", json=invalid_m_payload)
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "REFERENTIAL_INTEGRITY_VIOLATION"

        factory_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
        m1_id = factory_res.json()["data"]["machines"][0]["id"]
        inverted_payload = {
            "name": "Inverted Downtime Scenario",
            "baseline_schedule_id": baseline_id,
            "disruption_type": "MACHINE_DOWNTIME",
            "disruption_delta": {
                "added_downtimes": [{"machine_id": m1_id, "start_minute": 50, "end_minute": 20}]
            },
        }
        res2 = await client.post(f"/api/v1/workspaces/{ws_id}/scenarios", json=inverted_payload)
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_scenario_reoptimization_and_baseline_immutability(app_with_db: FastAPI) -> None:
    """Ensure baseline schedule remains strictly immutable while reoptimization runs from t=0."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_id, baseline_id = await _setup_workspace_and_baseline(client)

        base_res_before = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{baseline_id}")
        base_data_before = base_res_before.json()["data"]
        base_makespan = base_data_before["metrics"]["makespan_minutes"]
        base_ops = base_data_before["scheduled_operations"]

        factory_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
        m1_id = factory_res.json()["data"]["machines"][0]["id"]

        scen_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/scenarios",
            json={
                "name": "M1 Outage",
                "baseline_schedule_id": baseline_id,
                "disruption_type": "MACHINE_DOWNTIME",
                "disruption_delta": {
                    "added_downtimes": [{"machine_id": m1_id, "start_minute": 0, "end_minute": 20}]
                },
            },
        )
        scen_id = scen_res.json()["data"]["id"]

        reopt_res = await client.post(f"/api/v1/workspaces/{ws_id}/scenarios/{scen_id}/reoptimize")
        assert reopt_res.status_code == 200
        comp_data = reopt_res.json()["data"]

        assert comp_data["delta_makespan"] >= 20
        assert comp_data["objective_diff_detected"] is False

        base_res_after = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{baseline_id}")
        base_data_after = base_res_after.json()["data"]
        assert base_data_after["metrics"]["makespan_minutes"] == base_makespan
        assert base_data_after["scheduled_operations"] == base_ops


@pytest.mark.asyncio
async def test_scenario_urgent_order_unlike_warning(app_with_db: FastAPI) -> None:
    """Ensure injecting an urgent rush order detects order-set difference and displays unlike warning."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_id, baseline_id = await _setup_workspace_and_baseline(client)

        factory_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
        m1_id = factory_res.json()["data"]["machines"][0]["id"]

        rush_payload = {
            "name": "Rush Order Injection",
            "baseline_schedule_id": baseline_id,
            "disruption_type": "URGENT_ORDER",
            "disruption_delta": {
                "added_orders": [
                    {
                        "order_code": "RUSH-99",
                        "release_time_minutes": 0,
                        "due_date_minutes": 25,
                        "tardiness_weight": 10,
                        "operations": [
                            {"sequence_index": 1, "machine_id": m1_id, "processing_minutes": 15}
                        ],
                    }
                ]
            },
        }
        scen_res = await client.post(f"/api/v1/workspaces/{ws_id}/scenarios", json=rush_payload)
        scen_id = scen_res.json()["data"]["id"]

        reopt_res = await client.post(f"/api/v1/workspaces/{ws_id}/scenarios/{scen_id}/reoptimize")
        assert reopt_res.status_code == 200
        comp_data = reopt_res.json()["data"]

        assert comp_data["order_set_diff_detected"] is True
        assert comp_data["unlike_comparison_warning"] is not None
        assert "Baseline and Scenario differ" in comp_data["unlike_comparison_warning"]

        new_ops = [d for d in comp_data["diverged_operations"] if d["status"] == "NEW_RUSH_OPERATION"]
        assert len(new_ops) == 1
        assert new_ops[0]["machine_id"] == m1_id


@pytest.mark.asyncio
async def test_scenarios_compare_direct_endpoint(app_with_db: FastAPI) -> None:
    """Test POST /workspaces/{id}/scenarios/compare between two schedules."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_id, baseline_id = await _setup_workspace_and_baseline(client)

        factory_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
        m1_id = factory_res.json()["data"]["machines"][0]["id"]

        scen_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/scenarios",
            json={
                "name": "Comparison Test",
                "baseline_schedule_id": baseline_id,
                "disruption_type": "MACHINE_DOWNTIME",
                "disruption_delta": {
                    "added_downtimes": [{"machine_id": m1_id, "start_minute": 0, "end_minute": 15}]
                },
            },
        )
        scen_id = scen_res.json()["data"]["id"]

        reopt_res = await client.post(f"/api/v1/workspaces/{ws_id}/scenarios/{scen_id}/reoptimize")
        assert reopt_res.status_code == 200
        scen_detail = (await client.get(f"/api/v1/workspaces/{ws_id}/scenarios/{scen_id}")).json()["data"]
        recovery_id = scen_detail["reoptimized_schedule_id"]
        assert recovery_id is not None

        compare_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/scenarios/compare",
            json={"baseline_schedule_id": baseline_id, "compared_schedule_id": recovery_id},
        )
        assert compare_res.status_code == 200
        comp = compare_res.json()["data"]
        assert comp["baseline_schedule_id"] == baseline_id
        assert comp["compared_schedule_id"] == recovery_id
        assert comp["delta_makespan"] >= 15


@pytest.mark.asyncio
async def test_scenarios_compare_cross_workspace_isolation(app_with_db: FastAPI) -> None:
    """Verify comparing schedules rejects scenario_id belonging to a different workspace."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_a, base_a = await _setup_workspace_and_baseline(client)
        ws_b, base_b = await _setup_workspace_and_baseline(client)

        factory_b = (await client.get(f"/api/v1/workspaces/{ws_b}/factory")).json()["data"]
        m1_b = factory_b["machines"][0]["id"]

        scen_b = await client.post(
            f"/api/v1/workspaces/{ws_b}/scenarios",
            json={
                "name": "Scenario B",
                "baseline_schedule_id": base_b,
                "disruption_type": "MACHINE_DOWNTIME",
                "disruption_delta": {
                    "added_downtimes": [{"machine_id": m1_b, "start_minute": 0, "end_minute": 10}]
                },
            },
        )
        scen_b_id = scen_b.json()["data"]["id"]

        # Attempt to attach comparison in Workspace A using Workspace B's scenario_id
        compare_res = await client.post(
            f"/api/v1/workspaces/{ws_a}/scenarios/compare",
            json={
                "baseline_schedule_id": base_a,
                "compared_schedule_id": base_a,
                "scenario_id": scen_b_id,
            },
        )
        assert compare_res.status_code == 404
        assert "not found" in compare_res.json()["error"]["message"].lower()
