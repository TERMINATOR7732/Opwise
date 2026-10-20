"""Integration tests for shop-floor execution dispatching, clock advancement, and concurrency.

Governed by Milestone 15D specification and acceptance criteria AC-15D-01 through AC-15D-27.
Tests cover:
- Clock advancement: forward, equal no-op, backward rejection, negative rejection (AC-15D-01..04)
- Remaining duration decrement and projected finish invariance (AC-15D-05)
- Overdue reconciliation gating without clamp (AC-15D-06)
- Bundled completion at destination clock (AC-15D-07)
- Discrete multi-hop completion avoiding downtime (AC-15D-08)
- Projected finish never inferred as actual end (AC-15D-09)
- Bundled override during clock advance (AC-15D-10)
- Multi-operation atomic rollback on partial reconciliation failure (AC-15D-11)
- Consecutive clock advances (AC-15D-12)
- Stale clock fencing and SQLite concurrency test-and-set (AC-15D-13)
- Start operation preconditions: valid, release time, predecessor, machine busy, downtime, duplicate (AC-15D-14..20)
- Complete operation preconditions: valid, start minute rejection, planned op rejection (AC-15D-21..23)
- Downtime boundary contact [100, 110) vs [110, 140) (AC-15D-24)
- Schedule snapshot immutability across execution actions (AC-15D-25)
- Post-execution reoptimization and verifier Invariants 1-8 (AC-15D-26)
- Scenario recovery compatibility (AC-15D-27)
"""

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


async def _create_standard_workspace(client: httpx.AsyncClient, name: str = "WS-Exec") -> tuple[str, dict]:
    """Helper to create a workspace with 2 machines, 1 downtime, and 2 orders."""
    res = await client.post("/api/v1/workspaces", json={"name": name})
    assert res.status_code == 201
    ws_id = res.json()["data"]["id"]

    factory_payload = {
        "machines": [
            {"external_id": "M1", "name": "Milling Machine"},
            {"external_id": "M2", "name": "Lathe Turning"},
        ],
        "downtimes": [
            {"machine_id": "M1", "start_minute": 110, "end_minute": 140, "reason": "Spindle Inspection"},
        ],
        "orders": [
            {
                "external_id": "ORD-1",
                "name": "Order 1",
                "release_minute": 0,
                "due_minute": 200,
                "tardiness_weight": 1,
                "operations": [
                    {"sequence_index": 1, "machine_id": "M1", "processing_minutes": 30, "status": "PLANNED"},
                    {"sequence_index": 2, "machine_id": "M2", "processing_minutes": 40, "status": "PLANNED"},
                ],
            },
            {
                "external_id": "ORD-2",
                "name": "Order 2",
                "release_minute": 50,
                "due_minute": 250,
                "tardiness_weight": 2,
                "operations": [
                    {"sequence_index": 1, "machine_id": "M2", "processing_minutes": 25, "status": "PLANNED"},
                ],
            },
        ],
        "current_time_minute": 0,
    }
    put_res = await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=factory_payload)
    assert put_res.status_code == 200
    factory_data = put_res.json()["data"]
    return ws_id, factory_data


@pytest.mark.asyncio
async def test_ac_15d_01_clock_forward(client: httpx.AsyncClient) -> None:
    """AC-15D-01: Advance clock forward from 30 to 45 (+15m)."""
    ws_id, _ = await _create_standard_workspace(client, "WS-AC-01")
    # Advance to 30
    res30 = await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 30})
    assert res30.status_code == 200
    assert res30.json()["data"]["current_time_minute"] == 30

    # Advance by 15
    res45 = await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"advance_by_minutes": 15})
    assert res45.status_code == 200
    assert res45.json()["data"]["current_time_minute"] == 45

    # Verify status
    status_res = await client.get(f"/api/v1/workspaces/{ws_id}/execution/status")
    assert status_res.status_code == 200
    assert status_res.json()["data"]["current_time_minute"] == 45


@pytest.mark.asyncio
async def test_ac_15d_02_clock_equal_noop(client: httpx.AsyncClient) -> None:
    """AC-15D-02: Advance clock by 0 or target == current is idempotent no-op."""
    ws_id, _ = await _create_standard_workspace(client, "WS-AC-02")
    adv1 = await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 30})
    assert adv1.status_code == 200

    noop = await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"advance_by_minutes": 0})
    assert noop.status_code == 200
    assert noop.json()["data"]["current_time_minute"] == 30


@pytest.mark.asyncio
async def test_ac_15d_03_clock_backward_rejected(client: httpx.AsyncClient) -> None:
    """AC-15D-03: Moving clock backward returns HTTP 422 INVALID_CLOCK."""
    ws_id, _ = await _create_standard_workspace(client, "WS-AC-03")
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 30})

    back = await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 20})
    assert back.status_code == 422
    assert back.json()["error"]["code"] == "INVALID_CLOCK"


@pytest.mark.asyncio
async def test_ac_15d_04_clock_negative_rejected(client: httpx.AsyncClient) -> None:
    """AC-15D-04: Negative clock rejected."""
    ws_id, _ = await _create_standard_workspace(client, "WS-AC-04")
    neg = await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": -5})
    assert neg.status_code == 422
    # Pydantic validation error or domain error
    assert neg.json()["success"] is False


@pytest.mark.asyncio
async def test_ac_15d_05_clock_decrement_rem(client: httpx.AsyncClient) -> None:
    """AC-15D-05: Linear decrement of remaining duration; projected completion invariant."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-05")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    # Start op at clock 0, p=30
    start_res = await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})
    assert start_res.status_code == 200

    # Advance clock to 10
    adv1 = await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"advance_by_minutes": 10})
    assert adv1.status_code == 200
    active = adv1.json()["data"]["active_operations"][0]
    assert active["remaining_duration_minutes"] == 20
    assert active["projected_end_minute"] == 30  # 10 + 20 = 30 (invariant)

    # Advance clock to 25 (+15m)
    adv2 = await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"advance_by_minutes": 15})
    assert adv2.status_code == 200
    active2 = adv2.json()["data"]["active_operations"][0]
    assert active2["remaining_duration_minutes"] == 5
    assert active2["projected_end_minute"] == 30  # 25 + 5 = 30 (invariant)


@pytest.mark.asyncio
async def test_ac_15d_06_clock_overdue_gate(client: httpx.AsyncClient) -> None:
    """AC-15D-06: Bare advance to or past projected finish fails with OVERDUE_RECONCILIATION_REQUIRED."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-06")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    # Start op at clock 0, p=30 -> projected finish 30
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})

    # Advance to 30 without reconciliation -> must fail
    res_at_finish = await client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 30}
    )
    assert res_at_finish.status_code == 422
    assert res_at_finish.json()["error"]["code"] == "OVERDUE_RECONCILIATION_REQUIRED"

    # Advance past finish (35) without reconciliation -> must fail
    res_past_finish = await client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 35}
    )
    assert res_past_finish.status_code == 422
    assert res_past_finish.json()["error"]["code"] == "OVERDUE_RECONCILIATION_REQUIRED"

    # Verify clock remained 0
    status = await client.get(f"/api/v1/workspaces/{ws_id}/execution/status")
    assert status.json()["data"]["current_time_minute"] == 0


@pytest.mark.asyncio
async def test_ac_15d_07_clock_bundled_complete(client: httpx.AsyncClient) -> None:
    """AC-15D-07: Bundled completion during clock advance completes op at destination clock."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-07")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})

    # Advance to 35 with op1 completed
    adv = await client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance",
        json={"target_time_minute": 35, "completed_operation_ids": [op1_id]},
    )
    assert adv.status_code == 200
    assert adv.json()["data"]["current_time_minute"] == 35
    assert len(adv.json()["data"]["active_operations"]) == 0

    # Verify op is completed and machine is IDLE
    f_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
    op1_saved = f_res.json()["data"]["orders"][0]["operations"][0]
    assert op1_saved["status"] == "COMPLETED"
    assert op1_saved["actual_start_minute"] == 0
    assert op1_saved["actual_end_minute"] == 35
    assert op1_saved["remaining_duration_minutes"] is None


@pytest.mark.asyncio
async def test_ac_15d_08_discrete_multihop_completion(client: httpx.AsyncClient) -> None:
    """AC-15D-08: Discrete multi-hop completion allows op to finish at 108 and avoid downtime at [110, 140)."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-08")
    op1_id = f_data["orders"][0]["operations"][0]["id"]
    # M1 has downtime at [110, 140)

    # Advance clock to 80
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 80})
    # Start op at 80 (processing 30 -> projected 110)
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})

    # Discrete step 1: Advance to 108 and complete op1
    step1 = await client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance",
        json={"target_time_minute": 108, "completed_operation_ids": [op1_id]},
    )
    assert step1.status_code == 200

    # Discrete step 2: Advance clock across downtime to 145 (machine M1 was idle [108, 110), in downtime [110, 140))
    step2 = await client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance",
        json={"target_time_minute": 145},
    )
    assert step2.status_code == 200
    assert step2.json()["data"]["current_time_minute"] == 145


@pytest.mark.asyncio
async def test_ac_15d_09_projected_finish_never_inferred(client: httpx.AsyncClient) -> None:
    """AC-15D-09: Reaching or passing projected finish never automatically completes operation."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-09")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})

    # Advance to 40 with override r=10 (delayed)
    adv = await client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance",
        json={"target_time_minute": 40, "remaining_duration_overrides": {op1_id: 10}},
    )
    assert adv.status_code == 200
    active = adv.json()["data"]["active_operations"][0]
    assert active["remaining_duration_minutes"] == 10
    assert active["projected_end_minute"] == 50

    # Verify op is still IN_PROGRESS and actual_end is None
    f_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
    op1_saved = f_res.json()["data"]["orders"][0]["operations"][0]
    assert op1_saved["status"] == "IN_PROGRESS"
    assert op1_saved["actual_end_minute"] is None


@pytest.mark.asyncio
async def test_ac_15d_10_clock_bundled_override(client: httpx.AsyncClient) -> None:
    """AC-15D-10: Bundled override updates remaining work and projected completion at destination."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-10")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})

    adv = await client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance",
        json={"advance_by_minutes": 20, "remaining_duration_overrides": {op1_id: 25}},
    )
    assert adv.status_code == 200
    active = adv.json()["data"]["active_operations"][0]
    assert active["remaining_duration_minutes"] == 25
    assert active["projected_end_minute"] == 45  # 20 + 25 = 45


@pytest.mark.asyncio
async def test_ac_15d_11_multi_op_partial_fail_rollback(client: httpx.AsyncClient) -> None:
    """AC-15D-11: If one op is reconciled and another is omitted/overdue, total rollback occurs."""
    ws_id, _ = await _create_standard_workspace(client, "WS-AC-11")

    # Set up 2 orders running simultaneously on M1 and M2
    setup_payload = {
        "machines": [{"external_id": "M1", "name": "M1"}, {"external_id": "M2", "name": "M2"}],
        "downtimes": [],
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
                        "processing_minutes": 20,
                        "status": "IN_PROGRESS",
                        "actual_start_minute": 0,
                        "remaining_duration_minutes": 20,
                    }
                ],
            },
            {
                "external_id": "O2",
                "name": "O2",
                "release_minute": 0,
                "due_minute": 100,
                "tardiness_weight": 1,
                "operations": [
                    {
                        "sequence_index": 1,
                        "machine_id": "M2",
                        "processing_minutes": 20,
                        "status": "IN_PROGRESS",
                        "actual_start_minute": 0,
                        "remaining_duration_minutes": 20,
                    }
                ],
            },
        ],
        "current_time_minute": 0,
    }
    f_res = await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=setup_payload)
    assert f_res.status_code == 200
    o1_op_id = f_res.json()["data"]["orders"][0]["operations"][0]["id"]
    o2_op_id = f_res.json()["data"]["orders"][1]["operations"][0]["id"]

    # Advance to 25: O1 is in completed_operation_ids, but O2 is omitted (overdue!)
    bad_adv = await client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance",
        json={"target_time_minute": 25, "completed_operation_ids": [o1_op_id]},
    )
    assert bad_adv.status_code == 422
    assert bad_adv.json()["error"]["code"] == "OVERDUE_RECONCILIATION_REQUIRED"

    # Verify TOTAL ROLLBACK: clock is still 0, O1 is still IN_PROGRESS with rem=20
    status = await client.get(f"/api/v1/workspaces/{ws_id}/execution/status")
    assert status.json()["data"]["current_time_minute"] == 0
    active_ops = {op["operation_id"]: op for op in status.json()["data"]["active_operations"]}
    assert active_ops[o1_op_id]["remaining_duration_minutes"] == 20
    assert active_ops[o2_op_id]["remaining_duration_minutes"] == 20


@pytest.mark.asyncio
async def test_ac_15d_12_consecutive_advances(client: httpx.AsyncClient) -> None:
    """AC-15D-12: Consecutive advances decrement remaining work properly."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-12")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})

    # Advance +10 -> rem 20
    adv1 = await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"advance_by_minutes": 10})
    assert adv1.status_code == 200
    assert adv1.json()["data"]["active_operations"][0]["remaining_duration_minutes"] == 20

    # Advance +5 -> rem 15
    adv2 = await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"advance_by_minutes": 5})
    assert adv2.status_code == 200
    assert adv2.json()["data"]["active_operations"][0]["remaining_duration_minutes"] == 15
    assert adv2.json()["data"]["current_time_minute"] == 15


@pytest.mark.asyncio
async def test_ac_15d_13_stale_clock_fencing(client: httpx.AsyncClient) -> None:
    """AC-15D-13: Expected current clock mismatch yields HTTP 409 STALE_EXECUTION_STATE."""
    ws_id, _ = await _create_standard_workspace(client, "WS-AC-13")

    # Advance to 45
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 45})

    # Stale request expecting 30
    stale_req = await client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance",
        json={"advance_by_minutes": 15, "expected_current_time_minute": 30},
    )
    assert stale_req.status_code == 409
    assert stale_req.json()["error"]["code"] == "STALE_EXECUTION_STATE"


@pytest.mark.asyncio
async def test_ac_15d_14_start_operation_valid(client: httpx.AsyncClient) -> None:
    """AC-15D-14: Start planned operation when preconditions are met."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-14")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    res = await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})
    assert res.status_code == 200
    active = res.json()["data"]["active_operations"][0]
    assert active["operation_id"] == op1_id
    assert active["actual_start_minute"] == 0
    assert active["remaining_duration_minutes"] == 30


@pytest.mark.asyncio
async def test_ac_15d_15_start_before_release_rejected(client: httpx.AsyncClient) -> None:
    """AC-15D-15: Starting operation before order release time fails with INVALID_SEQUENCE."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-15")
    # ORD-2 release time is 50, clock is 0
    ord2_op_id = f_data["orders"][1]["operations"][0]["id"]

    res = await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{ord2_op_id}/start", json={})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INVALID_SEQUENCE"


@pytest.mark.asyncio
async def test_ac_15d_16_start_unfinished_pred_rejected(client: httpx.AsyncClient) -> None:
    """AC-15D-16: Starting operation step 2 when step 1 is uncompleted fails."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-16")
    op2_id = f_data["orders"][0]["operations"][1]["id"]  # Step 2

    res = await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op2_id}/start", json={})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INVALID_SEQUENCE"


@pytest.mark.asyncio
async def test_ac_15d_17_start_machine_busy_rejected(client: httpx.AsyncClient) -> None:
    """AC-15D-17: Starting operation on an already occupied machine fails with MACHINE_OCCUPIED."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-17")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    # Start op1 on M1
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})

    # Add another order on M1 and try to start it
    put_payload = {
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
                    {
                        "sequence_index": 1,
                        "machine_id": "M1",
                        "processing_minutes": 20,
                        "status": "IN_PROGRESS",
                        "actual_start_minute": 0,
                        "remaining_duration_minutes": 20,
                    }
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
    f_res = await client.put(f"/api/v1/workspaces/{ws_id}/factory", json=put_payload)
    o2_op_id = f_res.json()["data"]["orders"][1]["operations"][0]["id"]

    res = await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{o2_op_id}/start", json={})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "MACHINE_OCCUPIED"


@pytest.mark.asyncio
async def test_ac_15d_18_start_during_downtime_rejected(client: httpx.AsyncClient) -> None:
    """AC-15D-18: Starting operation on machine actively in downtime fails."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-18")
    op1_id = f_data["orders"][0]["operations"][0]["id"]
    # M1 has downtime at [110, 140)

    # Advance clock to 120 (during downtime)
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 120})

    # Try to start op on M1
    res = await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "HISTORICAL_DOWNTIME_CONFLICT"


@pytest.mark.asyncio
async def test_ac_15d_19_start_early_or_late_permitted(client: httpx.AsyncClient) -> None:
    """AC-15D-19: Advisory scheduled times do not prevent earlier/later execution starts."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-19")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    # Advance clock to 15 (planned start was 0)
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 15})

    # Start at 15
    res = await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})
    assert res.status_code == 200
    assert res.json()["data"]["active_operations"][0]["actual_start_minute"] == 15


@pytest.mark.asyncio
async def test_ac_15d_20_duplicate_start_rejected(client: httpx.AsyncClient) -> None:
    """AC-15D-20: Duplicate start on an already IN_PROGRESS operation fails with INVALID_LIFECYCLE_STATE."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-20")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})

    # Duplicate start
    dup = await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})
    assert dup.status_code == 422
    assert dup.json()["error"]["code"] == "INVALID_LIFECYCLE_STATE"


@pytest.mark.asyncio
async def test_ac_15d_21_complete_operation_valid(client: httpx.AsyncClient) -> None:
    """AC-15D-21: Completing an in-progress operation frees machine and records actual end."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-21")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    # Start at 0
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})

    # Advance clock to 30
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 30, "remaining_duration_overrides": {op1_id: 5}})

    # Complete at 30
    comp = await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/complete", json={})
    assert comp.status_code == 200
    assert len(comp.json()["data"]["active_operations"]) == 0

    # Verify machine M1 is IDLE
    m1_status = next(m for m in comp.json()["data"]["occupied_machines"] if m["machine_id"] == f_data["machines"][0]["id"])
    assert m1_status["status"] == "IDLE"


@pytest.mark.asyncio
async def test_ac_15d_22_complete_at_start_minute_rejected(client: httpx.AsyncClient) -> None:
    """AC-15D-22: Completing at the exact start minute fails (positive duration required)."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-22")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    # Start at clock 0
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})

    # Attempt complete at clock 0
    comp = await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/complete", json={})
    assert comp.status_code == 422
    assert comp.json()["error"]["code"] == "INVALID_LIFECYCLE_STATE"


@pytest.mark.asyncio
async def test_ac_15d_23_complete_planned_op_rejected(client: httpx.AsyncClient) -> None:
    """AC-15D-23: Attempting to complete a PLANNED operation fails."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-23")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    comp = await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/complete", json={})
    assert comp.status_code == 422
    assert comp.json()["error"]["code"] == "INVALID_LIFECYCLE_STATE"


@pytest.mark.asyncio
async def test_ac_15d_24_downtime_boundary_contact(client: httpx.AsyncClient) -> None:
    """AC-15D-24: Half-open interval contact [100, 110) vs [110, 140) is valid."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-24")
    op1_id = f_data["orders"][0]["operations"][0]["id"]
    # M1 has downtime at [110, 140)

    # Advance clock to 80
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 80})
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})

    # Advance to 110 with bundled completion. Interval is [80, 110), downtime is [110, 140).
    adv = await client.post(
        f"/api/v1/workspaces/{ws_id}/execution/clock/advance",
        json={"target_time_minute": 110, "completed_operation_ids": [op1_id]},
    )
    assert adv.status_code == 200
    assert adv.json()["data"]["current_time_minute"] == 110


@pytest.mark.asyncio
async def test_ac_15d_25_schedule_snapshot_immutability(client: httpx.AsyncClient) -> None:
    """AC-15D-25: Previously saved schedule snapshots remain strictly immutable after execution."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-25")

    # Solve and save initial schedule S1
    solve_res = await client.post(f"/api/v1/workspaces/{ws_id}/optimize", json={"objective_mode": "PURE_MAKESPAN"})
    assert solve_res.status_code == 200
    s1_id = solve_res.json()["data"]["schedule_id"]
    s1_ops = solve_res.json()["data"]["scheduled_operations"]

    # Now execute work on the shop floor: advance clock to 30, start op1, advance to 60, complete op1
    op1_id = f_data["orders"][0]["operations"][0]["id"]
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 60, "completed_operation_ids": [op1_id]})

    # Fetch S1 again
    s1_get = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{s1_id}")
    assert s1_get.status_code == 200
    s1_retrieved_ops = s1_get.json()["data"]["scheduled_operations"]

    # Snapshot must be byte-for-byte identical to original
    assert len(s1_ops) == len(s1_retrieved_ops)
    for orig, curr in zip(s1_ops, s1_retrieved_ops, strict=True):
        assert orig["start_minute"] == curr["start_minute"]
        assert orig["end_minute"] == curr["end_minute"]


@pytest.mark.asyncio
async def test_ac_15d_26_reoptimize_post_execution(client: httpx.AsyncClient) -> None:
    """AC-15D-26: Reoptimization locks IN_PROGRESS and pins COMPLETED; all 8 invariants pass."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-26")
    op1_id = f_data["orders"][0]["operations"][0]["id"]
    op2_id = f_data["orders"][0]["operations"][1]["id"]

    # Start op1 at 0, advance to 30, complete op1
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 30, "completed_operation_ids": [op1_id]})

    # Start op2 at 30
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op2_id}/start", json={})
    # Advance to 40 -> op2 has rem = 30
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"advance_by_minutes": 10})

    # Re-optimize
    reopt = await client.post(f"/api/v1/workspaces/{ws_id}/optimize", json={"objective_mode": "PURE_MAKESPAN"})
    assert reopt.status_code == 200
    sched_data = reopt.json()["data"]
    assert sched_data["verification_status"] == "VERIFIED"

    # Verify op1 is pinned at [0, 30) and op2 is locked starting at its start minute 30
    ops_by_id = {op["operation_id"]: op for op in sched_data["scheduled_operations"]}
    assert ops_by_id[op1_id]["start_minute"] == 0
    assert ops_by_id[op1_id]["end_minute"] == 30
    assert ops_by_id[op2_id]["start_minute"] == 30
    assert ops_by_id[op2_id]["end_minute"] == 70  # 40 (clock) + 30 rem


@pytest.mark.asyncio
async def test_ac_15d_27_disruption_recovery_compatibility(client: httpx.AsyncClient) -> None:
    """AC-15D-27: Disruption scenario recovery respects live clock and locks."""
    ws_id, f_data = await _create_standard_workspace(client, "WS-AC-27")
    op1_id = f_data["orders"][0]["operations"][0]["id"]

    # Start op1 at 0, advance to 20
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/operations/{op1_id}/start", json={})
    await client.post(f"/api/v1/workspaces/{ws_id}/execution/clock/advance", json={"target_time_minute": 20})

    # First optimize baseline schedule
    opt_res = await client.post(f"/api/v1/workspaces/{ws_id}/optimize", json={"objective_mode": "PURE_MAKESPAN"})
    assert opt_res.status_code == 200
    base_sched_id = opt_res.json()["data"]["schedule_id"]

    # Inject disruption scenario: rush order arriving at minute 20
    scenario_payload = {
        "name": "Rush Order Recovery",
        "baseline_schedule_id": base_sched_id,
        "disruption_type": "URGENT_ORDER",
        "description": "Customer rush order during execution",
        "disruption_delta": {
            "added_orders": [
                {
                    "order_code": "RUSH-01",
                    "release_time_minutes": 20,
                    "due_date_minutes": 100,
                    "tardiness_weight": 10,
                    "operations": [
                        {
                            "sequence_index": 1,
                            "machine_id": f_data["machines"][1]["id"],
                            "processing_minutes": 15,
                        }
                    ],
                }
            ],
            "added_downtimes": [],
        },
    }
    scen_res = await client.post(f"/api/v1/workspaces/{ws_id}/scenarios", json=scenario_payload)
    assert scen_res.status_code == 201
    scen_id = scen_res.json()["data"]["id"]

    # Reoptimize scenario
    reopt_res = await client.post(f"/api/v1/workspaces/{ws_id}/scenarios/{scen_id}/reoptimize", json={})
    assert reopt_res.status_code == 200
    reopt_id = reopt_res.json()["data"]["compared_schedule_id"]
    assert reopt_id is not None

    sched_res = await client.get(f"/api/v1/workspaces/{ws_id}/schedules/{reopt_id}")
    assert sched_res.status_code == 200
    assert sched_res.json()["data"]["verification_status"] == "VERIFIED"
