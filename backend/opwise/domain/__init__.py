"""Opwise pure domain package."""

from opwise.domain.downtime import (
    NormalizationResult,
    calculate_effective_horizon,
    normalize_machine_downtimes,
)
from opwise.domain.entities import (
    Factory,
    InputClassification,
    Machine,
    MachineDowntime,
    ObjectiveMode,
    Operation,
    ProductionOrder,
    Schedule,
    ScheduledOperation,
    ScheduleKPIs,
    ScheduleStatus,
)
from opwise.domain.exceptions import (
    DomainError,
    EmptyWorkspaceError,
    IntegerOverflowError,
    InvalidBoundsError,
    InvalidDurationError,
    InvalidIntervalError,
    InvalidSequenceError,
    OpwiseError,
    OrderWithoutOperationsError,
    ReferentialIntegrityError,
)
from opwise.domain.validators import (
    FactoryValidationResult,
    validate_factory_for_optimization,
)

__all__ = [
    "DomainError",
    "EmptyWorkspaceError",
    "Factory",
    "FactoryValidationResult",
    "InputClassification",
    "IntegerOverflowError",
    "InvalidBoundsError",
    "InvalidDurationError",
    "InvalidIntervalError",
    "InvalidSequenceError",
    "Machine",
    "MachineDowntime",
    "NormalizationResult",
    "ObjectiveMode",
    "Operation",
    "OpwiseError",
    "OrderWithoutOperationsError",
    "ProductionOrder",
    "ReferentialIntegrityError",
    "Schedule",
    "ScheduleKPIs",
    "ScheduleStatus",
    "ScheduledOperation",
    "calculate_effective_horizon",
    "normalize_machine_downtimes",
    "validate_factory_for_optimization",
]
