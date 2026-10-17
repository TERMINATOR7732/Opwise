"""Service managing two-phase CSV and Excel import staging and atomic confirmation.

Governed by DATA_AND_API.md Section 4.3, SPECIFICATION.md Section 9, and PROJECT_RULES.md.
"""

import json
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from opwise.api.schemas.factory import (
    DowntimeCreate,
    FactoryConfigPayload,
    MachineCreate,
    OperationCreate,
    OrderCreate,
)
from opwise.api.schemas.import_job import (
    ImportConfirmResponse,
    ImportJobDetailResponse,
    ImportPreviewResponse,
    ImportRowError,
    ImportStagedData,
    ImportSummary,
)
from opwise.domain.downtime import normalize_machine_downtimes
from opwise.domain.entities import MachineDowntime
from opwise.domain.exceptions import DataExchangeError, ResourceNotFoundError
from opwise.io.csv_parser import parse_csv_zip_archive
from opwise.io.excel_parser import parse_excel_workbook
from opwise.io.parsing_types import ParsedFactoryData, RowError
from opwise.persistence.import_repository import ImportJobRepository
from opwise.persistence.repository import WorkspaceRepository
from opwise.services.factory_service import FactoryService


def _validate_unique_identifiers(parsed: ParsedFactoryData) -> None:
    """Ensure machines, orders, operations, and downtimes have unique IDs."""
    seen_machines: set[str] = set()
    for m in parsed.machines:
        if m.machine_id in seen_machines:
            parsed.errors.append(RowError("Machines", 0, "machine_id", m.machine_id, f"Duplicate machine ID '{m.machine_id}'."))
        seen_machines.add(m.machine_id)

    seen_orders: set[str] = set()
    for o in parsed.orders:
        if o.order_id in seen_orders:
            parsed.errors.append(RowError("Orders", 0, "order_id", o.order_id, f"Duplicate order ID '{o.order_id}'."))
        seen_orders.add(o.order_id)

    seen_ops: set[str] = set()
    for op in parsed.operations:
        if op.operation_id in seen_ops:
            parsed.errors.append(RowError("Operations", 0, "operation_id", op.operation_id, f"Duplicate operation ID '{op.operation_id}'."))
        seen_ops.add(op.operation_id)


def _validate_cross_table_references(parsed: ParsedFactoryData) -> None:
    """Validate referential integrity between operations, machines, orders, and downtimes."""
    machine_ids = {m.machine_id for m in parsed.machines}
    order_ids = {o.order_id for o in parsed.orders}

    for op in parsed.operations:
        if op.order_id not in order_ids:
            parsed.errors.append(
                RowError("Operations", 0, "order_id", op.order_id, f"Operation '{op.operation_id}' references non-existent order '{op.order_id}'.")
            )
        if op.machine_id not in machine_ids:
            parsed.errors.append(
                RowError("Operations", 0, "machine_id", op.machine_id, f"Operation '{op.operation_id}' references non-existent machine '{op.machine_id}'.")
            )

    for dt in parsed.downtimes:
        if dt.machine_id not in machine_ids:
            parsed.errors.append(
                RowError("Downtimes", 0, "machine_id", dt.machine_id, f"Downtime '{dt.downtime_id}' references non-existent machine '{dt.machine_id}'.")
            )


def _validate_operation_sequences(parsed: ParsedFactoryData) -> None:
    """Validate that every order has contiguous 1..N operation sequences."""
    ops_by_order: dict[str, list] = defaultdict(list)
    for op in parsed.operations:
        ops_by_order[op.order_id].append(op)

    for order in parsed.orders:
        ops = ops_by_order.get(order.order_id, [])
        if not ops:
            parsed.errors.append(
                RowError("Orders", 0, "order_id", order.order_id, f"Order '{order.order_id}' contains zero operations.")
            )
            continue
        sorted_ops = sorted(ops, key=lambda x: x.sequence_index)
        for expected_seq, op in enumerate(sorted_ops, start=1):
            if op.sequence_index != expected_seq:
                parsed.errors.append(
                    RowError(
                        "Operations",
                        0,
                        "sequence_index",
                        str(op.sequence_index),
                        f"Non-contiguous sequence index for order '{order.order_id}' (expected {expected_seq}, found {op.sequence_index}).",
                    )
                )


def _normalize_staged_downtimes(parsed: ParsedFactoryData) -> list[DowntimeCreate]:
    """Perform canonical downtime normalization and collect advisory notes."""
    raw_downtimes = [
        MachineDowntime(
            id=dt.downtime_id,
            machine_id=dt.machine_id,
            start_minute=dt.start_minute,
            end_minute=dt.end_minute,
            reason=dt.reason,
        )
        for dt in parsed.downtimes
    ]
    norm_result = normalize_machine_downtimes(raw_downtimes)
    parsed.warnings.extend(norm_result.advisory_warnings)

    return [
        DowntimeCreate(
            machine_id=dt.machine_id,
            start_minute=dt.start_minute,
            end_minute=dt.end_minute,
            reason=dt.reason,
        )
        for dt in norm_result.merged_downtimes
    ]


def _build_staged_payload(parsed: ParsedFactoryData) -> ImportStagedData:
    """Build staged payload combining machines, orders with operations, and normalized downtimes."""
    ops_by_order: dict[str, list[OperationCreate]] = defaultdict(list)
    for op in parsed.operations:
        ops_by_order[op.order_id].append(
            OperationCreate(
                sequence_index=op.sequence_index,
                machine_id=op.machine_id,
                processing_minutes=op.processing_minutes,
            )
        )

    orders_create = [
        OrderCreate(
            external_id=o.order_id,
            name=o.name,
            release_minute=o.release_minute,
            due_minute=o.due_minute,
            tardiness_weight=o.tardiness_weight,
            operations=sorted(ops_by_order.get(o.order_id, []), key=lambda x: x.sequence_index),
        )
        for o in parsed.orders
    ]

    machines_create = [
        MachineCreate(external_id=m.machine_id, name=m.name) for m in parsed.machines
    ]
    downtimes_create = _normalize_staged_downtimes(parsed)
    return ImportStagedData(machines=machines_create, orders=orders_create, downtimes=downtimes_create)


class ImportService:
    """Orchestrates two-phase CSV and Excel import validation, staging, and atomic commit."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workspace_repo = WorkspaceRepository(session)
        self.import_repo = ImportJobRepository(session)
        self.factory_service = FactoryService(session)

    async def preview_import(
        self, workspace_id: str, filename: str, content: bytes
    ) -> tuple[ImportPreviewResponse, int]:
        """Phase 1: Parse and validate file, returning row errors (422) or staged job (200)."""
        ws = await self.workspace_repo.get_by_id(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        fn_lower = filename.lower().strip()
        if fn_lower.endswith(".xlsx"):
            parsed = parse_excel_workbook(content)
        elif fn_lower.endswith(".zip"):
            parsed = parse_csv_zip_archive(content)
        else:
            raise DataExchangeError(
                f"Unsupported file format '{filename}'. Please upload a .zip CSV bundle or .xlsx Excel workbook."
            )

        _validate_unique_identifiers(parsed)
        _validate_cross_table_references(parsed)
        _validate_operation_sequences(parsed)

        row_errors = [
            ImportRowError(sheet=e.sheet, row=e.row, column=e.column, value=e.value, issue=e.issue)
            for e in parsed.errors
        ]

        if not parsed.is_valid:
            errors_json = json.dumps([e.model_dump() for e in row_errors])
            failed_job = await self.import_repo.create_job(
                workspace_id=workspace_id,
                filename=filename,
                status="FAILED",
                staged_data_json="{}",
                error_report_json=errors_json,
            )
            await self.session.commit()
            return (
                ImportPreviewResponse(
                    job_id=failed_job.id,
                    filename=filename,
                    status="FAILED",
                    is_valid=False,
                    warnings=parsed.warnings,
                    errors=row_errors,
                ),
                422,
            )

        staged = _build_staged_payload(parsed)
        job = await self.import_repo.create_job(
            workspace_id=workspace_id,
            filename=filename,
            status="PENDING_CONFIRMATION",
            staged_data_json=staged.model_dump_json(),
        )
        await self.session.commit()

        summary = ImportSummary(
            machine_count=len(staged.machines),
            order_count=len(staged.orders),
            operation_count=sum(len(o.operations) for o in staged.orders),
            downtime_count=len(staged.downtimes),
        )

        return (
            ImportPreviewResponse(
                job_id=job.id,
                filename=filename,
                status="PENDING_CONFIRMATION",
                is_valid=True,
                summary=summary,
                warnings=parsed.warnings,
                staged_data=staged,
            ),
            200,
        )

    async def confirm_import(
        self, workspace_id: str, job_id: str
    ) -> ImportConfirmResponse:
        """Phase 2: Atomically commit a staged import job into the workspace factory."""
        ws = await self.workspace_repo.get_by_id(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        job = await self.import_repo.get_by_id(workspace_id, job_id)
        if job is None:
            raise ResourceNotFoundError("ImportJob", job_id)

        if job.status == "COMMITTED":
            raise DataExchangeError("Import job has already been committed.")
        if job.status != "PENDING_CONFIRMATION":
            raise DataExchangeError(f"Import job in status '{job.status}' cannot be confirmed.")

        staged = ImportStagedData.model_validate_json(job.staged_data_json)
        payload = FactoryConfigPayload(
            machines=staged.machines,
            orders=staged.orders,
            downtimes=staged.downtimes,
        )

        factory_resp = await self.factory_service.replace_factory_config(workspace_id, payload)
        await self.import_repo.update_status(workspace_id, job_id, "COMMITTED")
        await self.session.commit()

        return ImportConfirmResponse(
            job_id=job.id,
            status="COMMITTED",
            message="Factory configuration imported successfully.",
            factory=factory_resp,
        )

    async def get_job(self, workspace_id: str, job_id: str) -> ImportJobDetailResponse:
        """Retrieve detailed import job status with workspace isolation."""
        ws = await self.workspace_repo.get_by_id(workspace_id)
        if ws is None:
            raise ResourceNotFoundError("Workspace", workspace_id)

        job = await self.import_repo.get_by_id(workspace_id, job_id)
        if job is None:
            raise ResourceNotFoundError("ImportJob", job_id)

        summary = None
        if job.staged_data_json:
            try:
                staged = ImportStagedData.model_validate_json(job.staged_data_json)
                summary = ImportSummary(
                    machine_count=len(staged.machines),
                    order_count=len(staged.orders),
                    operation_count=sum(len(o.operations) for o in staged.orders),
                    downtime_count=len(staged.downtimes),
                )
            except Exception:
                summary = None

        return ImportJobDetailResponse(
            id=job.id,
            workspace_id=job.workspace_id,
            filename=job.filename,
            status=job.status,
            created_at=job.created_at,
            summary=summary,
        )
