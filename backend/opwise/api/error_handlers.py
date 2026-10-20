"""Global error and exception handlers translating exceptions into standard envelopes.

Governed by DATA_AND_API.md Section 3.1 and PROJECT_RULES.md.
Never leaks filesystem paths, credentials, or internal stack traces to clients.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from opwise.api.schemas.common import ErrorBody, ErrorDetail, ErrorEnvelope
from opwise.domain.exceptions import OpwiseError


async def opwise_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all Opwise domain and service exceptions."""
    assert isinstance(exc, OpwiseError)
    envelope = ErrorEnvelope(
        success=False,
        error=ErrorBody(code=exc.error_code, message=exc.message),
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Pydantic HTTP request body and query parameter validation failures."""
    assert isinstance(exc, RequestValidationError)
    details: list[ErrorDetail] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"] if part != "body")
        details.append(ErrorDetail(field=loc or "body", issue=err["msg"]))

    envelope = ErrorEnvelope(
        success=False,
        error=ErrorBody(
            code="VALIDATION_FAILED",
            message="One or more request parameters failed validation.",
            details=details,
        ),
    )
    return JSONResponse(status_code=422, content=envelope.model_dump())


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Starlette and FastAPI HTTPExceptions."""
    assert isinstance(exc, StarletteHTTPException)
    code = "NOT_FOUND" if exc.status_code == 404 else f"HTTP_{exc.status_code}"
    envelope = ErrorEnvelope(
        success=False,
        error=ErrorBody(code=code, message=str(exc.detail)),
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())


async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle database contention and locking errors with 409 conflict."""
    msg = str(exc).lower()
    if "locked" in msg or "busy" in msg:
        envelope = ErrorEnvelope(
            success=False,
            error=ErrorBody(
                code="CONCURRENT_EXECUTION_CONFLICT",
                message="Database is temporarily locked due to concurrent execution. Please retry.",
            ),
        )
        return JSONResponse(status_code=409, content=envelope.model_dump())
    return await generic_exception_handler(request, exc)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected runtime exceptions."""
    envelope = ErrorEnvelope(
        success=False,
        error=ErrorBody(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal server error occurred.",
        ),
    )
    return JSONResponse(status_code=500, content=envelope.model_dump())
