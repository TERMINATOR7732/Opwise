"""Integration tests for Reports, Analytics & Data Export (Milestone 11).

Governed by SPECIFICATION.md Section 5.1, Section 8.1, and DATA_AND_API.md Section 4.
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
from opwise.services.export_service import sanitize_csv_cell


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


def test_formula_injection_sanitization() -> None:
    """Verify all formula injection triggers are escaped with single quote prefix."""
    # Attack vectors
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("-2+3+cmd|' /C calc'!A0") == "'-2+3+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_csv_cell("\tTAB_INJECT") == "'\tTAB_INJECT"
    assert sanitize_csv_cell("\rRETURN_INJECT") == "'\rRETURN_INJECT"

    # Safe primitives and text
    assert sanitize_csv_cell("Safe Order Name") == "Safe Order Name"
    assert sanitize_csv_cell(100) == 100
    assert sanitize_csv_cell(99.5) == 99.5
    assert sanitize_csv_cell(None) == ""
    assert sanitize_csv_cell("") == ""


async def _setup_workspace_and_schedule(
    client: httpx.AsyncClient, malicious_order_name: str | None = None
) -> tuple[str, str]:
    """Helper to set up a populated workspace and solve a verified schedule."""
    ws_res = await client.post("/api/v1/workspaces", json={"name": "Reports Test WS"})
    ws_id = ws_res.json()["data"]["id"]

    order_name = malicious_order_name or "Standard Bracket"
    factory_payload = {
        "machines": [
            {"external_id": "M1", "name": "Milling Station 1"},
            {"external_id": "M2", "name": "Drill Station 2"},
        ],
        "downtimes": [
            {
                "machine_id": "M1",
                "start_minute": 20,
                "end_minute": 40,
                "reason": "Tooling Calibration",
            }
        ],
        "orders": [
            {
                "external_id": "ORD-1",
                "name": order_name,
                "release_minute": 0,
                "due_minute": 100,
                "tardiness_weight": 5,
                "operations": [
                    {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 30},
                    {"sequence_index": 2, "machine_id": "M2", "processing_minutes": 20},
                ],
            },
            {
                "external_id": "ORD-2",
                "name": "Rush Housing",
                "release_minute": 10,
                "due_minute": 50,
                "tardiness_weight": 10,
                "operations": [
                    {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 25},
                ],
            },
        ],
    }

    put_res = await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)
    assert put_res.status_code == 200

    opt_res = await client.post(
        f"/api/v1/workspaces/{ws_id}/optimize",
        json={
            "name": "Production Schedule #1",
            "objective_type": "HIERARCHICAL",
            "parameters": {
                "primary_objective": "WEIGHTED_TARDINESS",
                "secondary_objective": "MAKESPAN",
                "primary_time_budget_seconds": 5.0,
                "secondary_time_budget_seconds": 5.0,
            },
        },
    )
    assert opt_res.status_code == 200
    schedule_id = opt_res.json()["data"]["schedule_id"]
    return ws_id, schedule_id


@pytest.mark.asyncio
async def test_get_schedule_report(app_with_db: FastAPI) -> None:
    """Test comprehensive schedule analytical report endpoint."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_with_db), base_url="http://test") as client:
        ws_id, sched_id = await _setup_workspace_and_schedule(client)

        res = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{sched_id}/report")
        assert res.status_code == 200
        data = res.json()["data"]

        # Validate top-level contract
        assert data["workspace_id"] == ws_id
        assert data["schedule_id"] == sched_id
        assert data["solver_status"] in ("OPTIMAL", "FEASIBLE")

        # Validate Summary KPIs
        summary = data["summary"]
        assert summary["makespan_minutes"] > 0
        assert summary["total_order_count"] == 2
        assert 0.0 <= summary["on_time_rate_pct"] <= 100.0

        # Validate Machine Utilization breakdown
        util = data["machine_utilization"]
        assert len(util) == 2
        m1 = next(m for m in util if m["machine_name"] == "Milling Station 1")
        assert m1["downtime_minutes"] == 20
        assert m1["net_utilization_pct"] > 0.0

        # Validate Order Performance breakdown
        orders = data["order_performance"]
        assert len(orders) == 2
        ord1 = next(o for o in orders if o["order_code"] == "ORD-1")
        assert ord1["due_date_minute"] == 100
        assert ord1["operation_count"] == 2

        # Validate Bottleneck diagnosis & verification audit
        assert data["bottleneck"]["highest_workload_minutes"] > 0
        assert "disclaimer" in data["bottleneck"]
        assert data["verification_audit"]["is_valid"] is True
        assert data["verification_audit"]["checks_passed"] >= 8


@pytest.mark.asyncio
async def test_export_schedule_csv_and_json(app_with_db: FastAPI) -> None:
    """Test CSV and JSON export downloads for a schedule."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_with_db), base_url="http://test") as client:
        ws_id, sched_id = await _setup_workspace_and_schedule(client)

        # 1. Test CSV export
        csv_res = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{sched_id}/export?format=csv")
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers["content-type"]
        assert f'filename="schedule_{sched_id}_report.csv"' in csv_res.headers["content-disposition"]
        csv_text = csv_res.text
        assert "# 1. SCHEDULE SUMMARY" in csv_text
        assert "# 2. MACHINE UTILIZATION" in csv_text
        assert "# 3. ORDER PERFORMANCE" in csv_text
        assert "# 4. SCHEDULED OPERATIONS" in csv_text
        assert "# 5. BOTTLENECK ANALYSIS" in csv_text
        assert "# 6. INDEPENDENT VERIFICATION AUDIT" in csv_text

        # 2. Test JSON export
        json_res = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{sched_id}/export?format=json")
        assert json_res.status_code == 200
        assert "application/json" in json_res.headers["content-type"]
        assert f'filename="schedule_{sched_id}_report.json"' in json_res.headers["content-disposition"]
        json_data = json_res.json()
        assert json_data["schedule_id"] == sched_id
        assert len(json_data["scheduled_operations"]) >= 3


@pytest.mark.asyncio
async def test_formula_injection_defense_in_csv_export(app_with_db: FastAPI) -> None:
    """Ensure malicious formula characters in order names are escaped in CSV export."""
    malicious = "=cmd|' /C calc'!A0"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_with_db), base_url="http://test") as client:
        # Use malicious code directly as order code
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Injection WS"})
        ws_id = ws_res.json()["data"]["id"]

        payload = {
            "machines": [{"external_id": "M1", "name": "Milling Station 1"}],
            "downtimes": [],
            "orders": [
                {
                    "external_id": malicious,
                    "name": "Standard Housing",
                    "release_minute": 0,
                    "due_minute": 100,
                    "tardiness_weight": 1,
                    "operations": [
                        {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 20},
                    ],
                }
            ],
        }
        await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=payload)
        opt_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/optimize",
            json={"name": "Inj Schedule", "objective_type": "PURE_MAKESPAN"},
        )
        sched_id = opt_res.json()["data"]["schedule_id"]

        csv_res = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{sched_id}/export?format=csv")
        assert csv_res.status_code == 200
        # The malicious formula must be safely prefixed with single quote
        assert f"'{malicious}" in csv_res.text


@pytest.mark.asyncio
async def test_export_scenario_csv_and_json(app_with_db: FastAPI) -> None:
    """Test scenario disruption export with delta metrics."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_with_db), base_url="http://test") as client:
        ws_id, sched_id = await _setup_workspace_and_schedule(client)

        factory_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
        m1_id = factory_res.json()["data"]["machines"][0]["id"]

        # Create scenario with extra downtime
        scen_create_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/scenarios",
            json={
                "name": "Machine Breakdown Lab",
                "baseline_schedule_id": sched_id,
                "disruption_type": "MACHINE_DOWNTIME",
                "disruption_delta": {
                    "added_downtimes": [
                        {"machine_id": m1_id, "start_minute": 20, "end_minute": 50, "reason": "Failure"}
                    ],
                    "added_orders": [],
                },
            },
        )
        assert scen_create_res.status_code == 201
        scen_id = scen_create_res.json()["data"]["id"]

        # Reoptimize scenario
        reopt_res = await client.post(f"/api/v1/workspaces/{ws_id}/scenarios/{scen_id}/reoptimize")
        assert reopt_res.status_code == 200

        # Export scenario CSV
        csv_res = await client.get(f"/api/v1/workspaces/{ws_id}/scenarios/{scen_id}/export?format=csv")
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers["content-type"]
        assert "# 1. SCENARIO CONFIGURATION" in csv_res.text
        assert "# 2. COMPARISON METRICS DELTA" in csv_res.text

        # Export scenario JSON
        json_res = await client.get(f"/api/v1/workspaces/{ws_id}/scenarios/{scen_id}/export?format=json")
        assert json_res.status_code == 200
        assert "application/json" in json_res.headers["content-type"]
        data = json_res.json()
        assert data["scenario"]["id"] == scen_id
        assert data["comparison"]["delta_makespan"] is not None


@pytest.mark.asyncio
async def test_workspace_export_and_404_handling(app_with_db: FastAPI) -> None:
    """Test workspace export and 404 error handling for non-existent entities."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_with_db), base_url="http://test") as client:
        ws_id, sched_id = await _setup_workspace_and_schedule(client)

        # Workspace CSV export
        ws_csv = await client.get(f"/api/v1/workspaces/{ws_id}/export/csv")
        assert ws_csv.status_code == 200
        assert "text/csv" in ws_csv.headers["content-type"]

        # 404 for invalid schedule
        missing_sched_res = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/non-existent-id/report")
        assert missing_sched_res.status_code == 404

        # 404 for invalid workspace
        missing_ws_res = await client.get("/api/v1/workspaces/non-existent-id/schedules/sched-1/report")
        assert missing_ws_res.status_code == 404
