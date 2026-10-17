"""Integration tests for Safe CSV/XLSX Import (Milestone 12B).

Governed by DATA_AND_API.md Section 3.2, Section 4, and PROJECT_RULES.md.
"""

import io
import os
import tempfile
import zipfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import httpx
import openpyxl  # type: ignore[import-untyped]
import pytest
from fastapi import FastAPI

from alembic import command
from alembic.config import Config
from opwise.config import Settings
from opwise.io.templates import (
    generate_csv_template_zip,
    generate_excel_template_workbook,
)
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


@pytest.mark.asyncio
async def test_download_starter_templates(app_with_db: FastAPI) -> None:
    """Verify template download endpoints return valid archives and workbooks."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Download CSV template
        csv_resp = await client.get("/api/v1/templates/csv")
        assert csv_resp.status_code == 200
        assert "application/zip" in csv_resp.headers["content-type"]
        with zipfile.ZipFile(io.BytesIO(csv_resp.content)) as zf:
            names = set(zf.namelist())
            assert "machines.csv" in names
            assert "orders.csv" in names

        # 2. Download XLSX template
        xlsx_resp = await client.get("/api/v1/templates/xlsx")
        assert xlsx_resp.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_resp.content))
        assert "Machines" in wb.sheetnames
        assert "Orders" in wb.sheetnames

        # 3. Invalid template format
        bad_resp = await client.get("/api/v1/templates/parquet")
        assert bad_resp.status_code == 400


@pytest.mark.asyncio
async def test_csv_bundle_preview_and_confirm(app_with_db: FastAPI) -> None:
    """Verify end-to-end two-phase CSV import and atomic replacement."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "CSV Plant"})
        ws_id = ws_res.json()["data"]["id"]

        # Phase 1: Preview valid CSV zip
        zip_bytes = generate_csv_template_zip()
        files = {"file": ("starter.zip", zip_bytes, "application/zip")}
        prev_res = await client.post(f"/api/v1/workspaces/{ws_id}/import/preview", files=files)
        assert prev_res.status_code == 200
        data = prev_res.json()["data"]
        job_id = data["job_id"]
        assert data["status"] == "PENDING_CONFIRMATION"
        assert data["summary"]["machine_count"] == 3
        assert data["summary"]["order_count"] == 3

        # Verify no side-effects prior to confirmation
        factory_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
        assert len(factory_res.json()["data"]["machines"]) == 0

        # Phase 2: Confirm import
        conf_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/import/confirm",
            json={"job_id": job_id},
        )
        assert conf_res.status_code == 200
        assert conf_res.json()["data"]["status"] == "COMMITTED"

        # Verify factory now has the imported data
        post_fact = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
        assert len(post_fact.json()["data"]["machines"]) == 3
        assert len(post_fact.json()["data"]["orders"]) == 3

        # Re-confirming should fail with 400
        reconf = await client.post(
            f"/api/v1/workspaces/{ws_id}/import/confirm",
            json={"job_id": job_id},
        )
        assert reconf.status_code == 400


@pytest.mark.asyncio
async def test_excel_preview_and_confirm(app_with_db: FastAPI) -> None:
    """Verify end-to-end two-phase Excel workbook import."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Excel Plant"})
        ws_id = ws_res.json()["data"]["id"]

        xlsx_bytes = generate_excel_template_workbook()
        files = {"file": ("factory.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        prev_res = await client.post(f"/api/v1/workspaces/{ws_id}/import/preview", files=files)
        assert prev_res.status_code == 200
        job_id = prev_res.json()["data"]["job_id"]

        conf_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/import/confirm",
            json={"job_id": job_id},
        )
        assert conf_res.status_code == 200
        fact_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
        assert len(fact_res.json()["data"]["machines"]) == 3


@pytest.mark.asyncio
async def test_import_workspace_isolation(app_with_db: FastAPI) -> None:
    """Verify import jobs cannot be accessed or confirmed across workspaces."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws1 = (await client.post("/api/v1/workspaces", json={"name": "WS 1"})).json()["data"]["id"]
        ws2 = (await client.post("/api/v1/workspaces", json={"name": "WS 2"})).json()["data"]["id"]

        zip_bytes = generate_csv_template_zip()
        prev = await client.post(
            f"/api/v1/workspaces/{ws1}/import/preview",
            files={"file": ("starter.zip", zip_bytes, "application/zip")},
        )
        job_id = prev.json()["data"]["job_id"]

        # Cross-workspace get fails with 404
        get_res = await client.get(f"/api/v1/workspaces/{ws2}/import/{job_id}")
        assert get_res.status_code == 404

        # Cross-workspace confirm fails with 404
        conf_res = await client.post(
            f"/api/v1/workspaces/{ws2}/import/confirm",
            json={"job_id": job_id},
        )
        assert conf_res.status_code == 404


@pytest.mark.asyncio
async def test_preview_validation_errors_returns_422(app_with_db: FastAPI) -> None:
    """Verify validation errors return 422 with structured row-level diagnostics."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Invalid Data Plant"})
        ws_id = ws_res.json()["data"]["id"]

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("machines.csv", "machine_id,name\nM1,Mill\n")
            zf.writestr("orders.csv", "order_id,name,release_minute,due_minute,tardiness_weight\nORD1,Job,0,10,1\n")
            zf.writestr("operations.csv", "operation_id,order_id,sequence_index,machine_id,processing_minutes\nOP1,ORD1,1,UNKNOWN_M,15\n")

        files = {"file": ("invalid.zip", buf.getvalue(), "application/zip")}
        prev_res = await client.post(f"/api/v1/workspaces/{ws_id}/import/preview", files=files)
        assert prev_res.status_code == 422
        body = prev_res.json()
        assert body["success"] is False
        assert body["error"]["code"] == "IMPORT_VALIDATION_FAILED"
        assert len(body["error"]["details"]) >= 1
        assert "UNKNOWN_M" in body["error"]["details"][0]["issue"]

        # Confirming failed job must be rejected with 400
        job_id = body["data"]["job_id"]
        conf_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/import/confirm",
            json={"job_id": job_id},
        )
        assert conf_res.status_code == 400


@pytest.mark.asyncio
async def test_preview_security_violation_returns_400(app_with_db: FastAPI) -> None:
    """Verify security violations (e.g., formula injection, corrupt files) return 400."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Security Plant"})
        ws_id = ws_res.json()["data"]["id"]

        # Corrupt / invalid zip archive
        files = {"file": ("corrupt.zip", b"not-a-valid-zip-content", "application/zip")}
        bad_zip_res = await client.post(f"/api/v1/workspaces/{ws_id}/import/preview", files=files)
        assert bad_zip_res.status_code == 400

        # Path traversal in ZIP archive
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../etc/passwd", "root:x:0:0:")

        files_sec = {"file": ("traversal.zip", buf.getvalue(), "application/zip")}
        sec_res = await client.post(f"/api/v1/workspaces/{ws_id}/import/preview", files=files_sec)
        assert sec_res.status_code == 400

@pytest.mark.asyncio
async def test_confirm_atomic_rollback_on_failure(app_with_db: FastAPI) -> None:
    """Verify transaction rolls back without corrupting factory data on confirmation failure."""
    transport = httpx.ASGITransport(app=app_with_db)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        ws_res = await client.post("/api/v1/workspaces", json={"name": "Rollback Plant"})
        ws_id = ws_res.json()["data"]["id"]

        # Pre-seed factory with existing machine
        await client.put(
            f"/api/v1/workspaces/{ws_id}/factory",
            json={"machines": [{"external_id": "ORIG-1", "name": "Original Machine"}], "orders": [], "downtimes": []},
        )

        zip_bytes = generate_csv_template_zip()
        files = {"file": ("valid.zip", zip_bytes, "application/zip")}
        prev = await client.post(f"/api/v1/workspaces/{ws_id}/import/preview", files=files)
        job_id = prev.json()["data"]["job_id"]

        with (
            patch("opwise.persistence.repository.FactoryRepository.replace_factory", side_effect=RuntimeError("Simulated DB Crash")),
            pytest.raises(RuntimeError),
        ):
            await client.post(
                f"/api/v1/workspaces/{ws_id}/import/confirm",
                json={"job_id": job_id},
            )

        # Confirm original factory was preserved and not corrupted
        fact_res = await client.get(f"/api/v1/workspaces/{ws_id}/factory")
        machines = fact_res.json()["data"]["machines"]
        assert len(machines) == 1
        assert machines[0]["external_id"] == "ORIG-1"
