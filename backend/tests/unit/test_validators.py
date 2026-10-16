"""Unit tests for factory validation and the 6 formal input classifications.

Governed by SPECIFICATION.md Section 1.4 and DATA_AND_API.md Section 3.3.
"""

import pytest

from opwise.domain.entities import (
    Factory,
    InputClassification,
    Machine,
    MachineDowntime,
    Operation,
    ProductionOrder,
)
from opwise.domain.exceptions import (
    EmptyWorkspaceError,
    InvalidBoundsError,
    InvalidDurationError,
    InvalidSequenceError,
    OrderWithoutOperationsError,
    ReferentialIntegrityError,
)
from opwise.domain.validators import validate_factory_for_optimization


def test_case_1_empty_workspace_rejected() -> None:
    """Case 1: Workspace with 0 machines and 0 orders is rejected with HTTP 422 EMPTY_WORKSPACE."""
    empty_factory = Factory(workspace_id="WS-EMPTY", machines=[], orders=[])
    with pytest.raises(EmptyWorkspaceError) as exc_info:
        validate_factory_for_optimization(empty_factory)
    assert exc_info.value.error_code == "EMPTY_WORKSPACE"
    assert exc_info.value.status_code == 422


def test_case_1_orders_without_machines_rejected() -> None:
    """Workspace with orders but 0 machines is rejected."""
    factory = Factory(
        workspace_id="WS-NO-MACHINES",
        machines=[],
        orders=[
            ProductionOrder(
                id="O1",
                order_code="J1",
                operations=[
                    Operation(id="OP1", order_id="O1", sequence_number=1, machine_id="M1", processing_duration_minutes=10)
                ],
            )
        ],
    )
    with pytest.raises(EmptyWorkspaceError):
        validate_factory_for_optimization(factory)


def test_case_2_no_work_state_accepted(sample_machines: list[Machine]) -> None:
    """Case 2: Factory with machines but 0 orders is accepted as NO_WORK_STATE with is_optimizable=False."""
    factory = Factory(
        workspace_id="WS-NO-WORK",
        machines=sample_machines,
        downtimes=[MachineDowntime(id="DT1", machine_id="M1", start_minute=10, end_minute=20)],
        orders=[],
    )
    res = validate_factory_for_optimization(factory)
    assert res.classification == InputClassification.NO_WORK_STATE
    assert res.is_optimizable is False
    assert res.effective_horizon_minutes == 0
    assert "No-Work" in res.message


def test_case_3_order_without_operations_rejected(sample_machines: list[Machine]) -> None:
    """Case 3: Orders without operations are rejected with ORDER_WITHOUT_OPERATIONS."""
    factory = Factory(
        workspace_id="WS-INCOMPLETE",
        machines=sample_machines,
        orders=[ProductionOrder(id="ORD-EMPTY", order_code="EMPTY", operations=[])],
    )
    with pytest.raises(OrderWithoutOperationsError) as exc_info:
        validate_factory_for_optimization(factory)
    assert exc_info.value.error_code == "ORDER_WITHOUT_OPERATIONS"
    assert exc_info.value.status_code == 422
    assert exc_info.value.order_id == "ORD-EMPTY"


def test_case_4_missing_machine_reference_rejected(sample_machines: list[Machine]) -> None:
    """Case 4: Operation referencing non-existent machine raises REFERENTIAL_INTEGRITY_VIOLATION."""
    factory = Factory(
        workspace_id="WS-BAD-REF",
        machines=sample_machines,  # M1, M2, M3
        orders=[
            ProductionOrder(
                id="O1",
                order_code="J1",
                operations=[
                    Operation(
                        id="OP1",
                        order_id="O1",
                        sequence_number=1,
                        machine_id="M999",  # Non-existent
                        processing_duration_minutes=20,
                    )
                ],
            )
        ],
    )
    with pytest.raises(ReferentialIntegrityError) as exc_info:
        validate_factory_for_optimization(factory)
    assert exc_info.value.error_code == "REFERENTIAL_INTEGRITY_VIOLATION"
    assert exc_info.value.status_code == 422
    assert exc_info.value.entity_type == "Machine"
    assert exc_info.value.missing_id == "M999"


def test_case_4_downtime_missing_machine_rejected(sample_machines: list[Machine]) -> None:
    """Downtime referencing non-existent machine raises REFERENTIAL_INTEGRITY_VIOLATION."""
    factory = Factory(
        workspace_id="WS-BAD-DT",
        machines=sample_machines,
        downtimes=[MachineDowntime(id="DT1", machine_id="M_UNKNOWN", start_minute=10, end_minute=30)],
        orders=[],
    )
    with pytest.raises(ReferentialIntegrityError) as exc_info:
        validate_factory_for_optimization(factory)
    assert exc_info.value.error_code == "REFERENTIAL_INTEGRITY_VIOLATION"


def test_duplicate_machine_ids_rejected() -> None:
    """Duplicate machine IDs raise ReferentialIntegrityError."""
    factory = Factory(
        workspace_id="WS-DUP-M",
        machines=[Machine(id="M1", name="Mill A"), Machine(id="M1", name="Mill B")],
        orders=[],
    )
    with pytest.raises(ReferentialIntegrityError):
        validate_factory_for_optimization(factory)


def test_non_contiguous_operation_sequence_rejected(sample_machines: list[Machine]) -> None:
    """Non-contiguous sequence numbers (e.g. 1, 3) raise InvalidSequenceError."""
    factory = Factory(
        workspace_id="WS-SEQ",
        machines=sample_machines,
        orders=[
            ProductionOrder(
                id="O1",
                order_code="J1",
                operations=[
                    Operation(id="OP1", order_id="O1", sequence_number=1, machine_id="M1", processing_duration_minutes=20),
                    Operation(id="OP2", order_id="O1", sequence_number=3, machine_id="M2", processing_duration_minutes=20),
                ],
            )
        ],
    )
    with pytest.raises(InvalidSequenceError) as exc_info:
        validate_factory_for_optimization(factory)
    assert exc_info.value.error_code == "INVALID_OPERATION_SEQUENCE"
    assert exc_info.value.status_code == 422


def test_non_positive_operation_duration_rejected(sample_machines: list[Machine]) -> None:
    """Operation with duration <= 0 raises InvalidDurationError."""
    factory = Factory(
        workspace_id="WS-DUR",
        machines=sample_machines,
        orders=[
            ProductionOrder(
                id="O1",
                order_code="J1",
                operations=[
                    Operation(id="OP1", order_id="O1", sequence_number=1, machine_id="M1", processing_duration_minutes=0),
                ],
            )
        ],
    )
    with pytest.raises(InvalidDurationError) as exc_info:
        validate_factory_for_optimization(factory)
    assert exc_info.value.error_code == "INVALID_PROCESSING_TIME"
    assert exc_info.value.status_code == 422


def test_negative_release_time_rejected(sample_machines: list[Machine]) -> None:
    """Order with release_time < 0 raises InvalidBoundsError."""
    factory = Factory(
        workspace_id="WS-REL",
        machines=sample_machines,
        orders=[
            ProductionOrder(
                id="O1",
                order_code="J1",
                release_time_minutes=-5,
                operations=[
                    Operation(id="OP1", order_id="O1", sequence_number=1, machine_id="M1", processing_duration_minutes=20),
                ],
            )
        ],
    )
    with pytest.raises(InvalidBoundsError) as exc_info:
        validate_factory_for_optimization(factory)
    assert exc_info.value.error_code == "INVALID_TIME_BOUNDS"


def test_case_5_valid_factory_passes(sample_factory: Factory) -> None:
    """Case 5: Valid factory passes validation with VALID_NON_EMPTY_FACTORY and correct horizon."""
    res = validate_factory_for_optimization(sample_factory)
    assert res.classification == InputClassification.VALID_NON_EMPTY_FACTORY
    assert res.is_optimizable is True
    # release=10, sum(p) = 30+45+40+50 = 165, downtime=30 -> 10 + 165 + 30 = 205
    assert res.effective_horizon_minutes == 205
    assert res.normalization is not None
    assert len(res.normalization.merged_downtimes) == 1
