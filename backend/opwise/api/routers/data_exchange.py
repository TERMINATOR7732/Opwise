"""Data exchange router handling two-phase CSV/Excel import and starter templates.

Governed by DATA_AND_API.md Section 3.2 and Section 4.
"""

from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile
from fastapi.responses import JSONResponse

from opwise.api.dependencies import ImportServiceDep
from opwise.api.schemas.common import SuccessEnvelope
from opwise.api.schemas.import_job import (
    ImportConfirmRequest,
    ImportConfirmResponse,
    ImportJobDetailResponse,
    ImportPreviewResponse,
)
from opwise.domain.exceptions import DataExchangeError
from opwise.io.templates import (
    generate_csv_template_zip,
    generate_excel_template_workbook,
)

router = APIRouter(tags=["data-exchange"])


@router.post(
    "/workspaces/{workspace_id}/import/preview",
    response_model=SuccessEnvelope[ImportPreviewResponse],
)
async def preview_import(
    workspace_id: str,
    file: Annotated[UploadFile, File()],
    import_service: ImportServiceDep = None,  # type: ignore[assignment]
) -> Response:
    """Phase 1: Parse and validate an uploaded CSV bundle (.zip) or Excel (.xlsx) file."""
    filename = file.filename or "upload.file"
    content = await file.read()

    preview_resp, status_code = await import_service.preview_import(
        workspace_id=workspace_id,
        filename=filename,
        content=content,
    )

    if status_code == 422:
        error_details = [
            {
                "field": f"{e.sheet}[row {e.row}].{e.column}",
                "issue": e.issue,
                "value": e.value,
            }
            for e in preview_resp.errors
        ]
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "IMPORT_VALIDATION_FAILED",
                    "message": f"Import validation failed with {len(preview_resp.errors)} error(s). No changes committed.",
                    "details": error_details,
                },
                "data": preview_resp.model_dump(mode="json"),
            },
        )

    return JSONResponse(
        status_code=200,
        content=SuccessEnvelope(data=preview_resp).model_dump(mode="json"),
    )


@router.post(
    "/workspaces/{workspace_id}/import/confirm",
    response_model=SuccessEnvelope[ImportConfirmResponse],
)
async def confirm_import(
    workspace_id: str,
    payload: ImportConfirmRequest,
    import_service: ImportServiceDep = None,  # type: ignore[assignment]
) -> SuccessEnvelope[ImportConfirmResponse]:
    """Phase 2: Atomically commit a staged import job into workspace factory data."""
    confirm_resp = await import_service.confirm_import(
        workspace_id=workspace_id,
        job_id=payload.job_id,
    )
    return SuccessEnvelope(data=confirm_resp)


@router.get(
    "/workspaces/{workspace_id}/import/{job_id}",
    response_model=SuccessEnvelope[ImportJobDetailResponse],
)
async def get_import_job(
    workspace_id: str,
    job_id: str,
    import_service: ImportServiceDep = None,  # type: ignore[assignment]
) -> SuccessEnvelope[ImportJobDetailResponse]:
    """Retrieve details and status for a staged or committed import job."""
    job_detail = await import_service.get_job(workspace_id=workspace_id, job_id=job_id)
    return SuccessEnvelope(data=job_detail)


@router.get("/templates/{format}")
async def get_starter_template(format: str) -> Response:
    """Download starter CSV bundle (.zip) or Excel workbook (.xlsx)."""
    fmt_lower = format.lower().strip()
    if fmt_lower == "csv":
        zip_bytes = generate_csv_template_zip()
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=opwise_factory_template.zip"},
        )
    if fmt_lower == "xlsx":
        xlsx_bytes = generate_excel_template_workbook()
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=opwise_factory_template.xlsx"},
        )
    raise DataExchangeError("Template format must be 'csv' or 'xlsx'.", status_code=400)
