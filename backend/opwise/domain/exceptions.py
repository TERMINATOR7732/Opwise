"""Hierarchical domain exceptions for Opwise.

Governed by PROJECT_RULES.md, ARCHITECTURE.md, and DATA_AND_API.md.
"""


class OpwiseError(Exception):
    """Base exception for all Opwise internal and domain errors."""

    def __init__(self, message: str, error_code: str = "INTERNAL_ERROR", status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


class DomainError(OpwiseError):
    """Base exception for domain modeling and validation failures."""

    def __init__(self, message: str, error_code: str = "DOMAIN_ERROR", status_code: int = 422) -> None:
        super().__init__(message=message, error_code=error_code, status_code=status_code)


class EmptyWorkspaceError(DomainError):
    """Raised when optimization is requested on an empty workspace (|M|=0, |J|=0)."""

    def __init__(self, message: str = "Workspace is empty. Add machines and production orders.") -> None:
        super().__init__(message=message, error_code="EMPTY_WORKSPACE", status_code=422)


class OrderWithoutOperationsError(DomainError):
    """Raised when a production order has zero operations."""

    def __init__(self, order_id: str) -> None:
        message = f"Production order '{order_id}' contains zero operations."
        super().__init__(message=message, error_code="ORDER_WITHOUT_OPERATIONS", status_code=422)
        self.order_id = order_id


class ReferentialIntegrityError(DomainError):
    """Raised when an operation references a non-existent machine or order."""

    def __init__(self, entity_type: str, missing_id: str, context: str) -> None:
        message = f"Referential integrity failure: {entity_type} '{missing_id}' does not exist (context: {context})."
        super().__init__(message=message, error_code="REFERENTIAL_INTEGRITY_VIOLATION", status_code=422)
        self.entity_type = entity_type
        self.missing_id = missing_id
        self.context = context


class InvalidDurationError(DomainError):
    """Raised when an operation processing duration is non-positive (p <= 0)."""

    def __init__(self, operation_id: str, duration: int) -> None:
        message = f"Operation '{operation_id}' has non-positive duration {duration}. Must be strictly positive (> 0)."
        super().__init__(message=message, error_code="INVALID_PROCESSING_TIME", status_code=422)
        self.operation_id = operation_id
        self.duration = duration


class InvalidBoundsError(DomainError):
    """Raised when release time, due date, or weight violate non-negativity."""

    def __init__(self, field_name: str, value: int, min_allowed: int = 0) -> None:
        message = f"Invalid parameter '{field_name}' with value {value}. Must be >= {min_allowed}."
        super().__init__(message=message, error_code="INVALID_TIME_BOUNDS", status_code=422)
        self.field_name = field_name
        self.value = value


class InvalidIntervalError(DomainError):
    """Raised when a downtime interval is negative or inverted (start > end)."""

    def __init__(self, downtime_id: str, start: int, end: int) -> None:
        message = f"Downtime '{downtime_id}' has invalid interval [{start}, {end}). Start must be <= end and >= 0."
        super().__init__(message=message, error_code="INVALID_DOWNTIME_INTERVAL", status_code=422)
        self.downtime_id = downtime_id
        self.start = start
        self.end = end


class InvalidSequenceError(DomainError):
    """Raised when operation sequence indices are not contiguous 1..n."""

    def __init__(self, order_id: str, expected_seq: int, found_seq: int) -> None:
        message = f"Order '{order_id}' has non-contiguous sequence numbers (expected {expected_seq}, found {found_seq})."
        super().__init__(message=message, error_code="INVALID_OPERATION_SEQUENCE", status_code=422)
        self.order_id = order_id


class IntegerOverflowError(DomainError):
    """Raised when the calculated scheduling horizon exceeds 32-bit limits or safety caps."""

    def __init__(self, calculated_horizon: int, max_allowed: int) -> None:
        message = f"Calculated horizon {calculated_horizon} exceeds maximum safety limit {max_allowed}."
        super().__init__(message=message, error_code="INTEGER_OVERFLOW_RISK", status_code=422)
        self.calculated_horizon = calculated_horizon
        self.max_allowed = max_allowed


class ResourceNotFoundError(OpwiseError):
    """Raised when a requested resource (e.g., workspace, schedule) is not found."""

    def __init__(self, resource_type: str, resource_id: str) -> None:
        message = f"{resource_type} with ID '{resource_id}' was not found."
        super().__init__(message=message, error_code="RESOURCE_NOT_FOUND", status_code=404)
        self.resource_type = resource_type
        self.resource_id = resource_id

