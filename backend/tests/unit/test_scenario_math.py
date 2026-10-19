"""Unit tests for scenario mathematical analysis, disruption synthesis, and lifecycle validation.

Governed by SPECIFICATION.md Section 6, DATA_AND_API.md Section 1.1, and Milestone 15C contract.
"""

import pytest

from opwise.api.schemas.scenario import (
    DisruptionDelta,
    DowntimeDisruptionItem,
    OperationDisruptionItem,
    OrderDisruptionItem,
)
from opwise.domain.entities import (
    Factory,
    Machine,
    MachineDowntime,
    Operation,
    OperationStatus,
    ProductionOrder,
)
from opwise.domain.exceptions import (
    DomainError,
    InvalidIntervalError,
    LifecycleStateError,
    ReferentialIntegrityError,
)
from opwise.persistence.models import ScheduledOperationModel
from opwise.services.scenario_math import (
    compute_operation_divergences,
    synthesize_disrupted_factory,
    validate_disruption,
)


@pytest.fixture
def base_execution_factory() -> Factory:
    """Fixture with clock=40, machine M1, completed op, in-progress op, and planned op."""
    machines = [Machine(id="M1", name="Mill 1")]
    downtimes: list[MachineDowntime] = []
    orders = [
        ProductionOrder(
            id="ORD-1",
            order_code="Order 1",
            release_time_minutes=0,
            due_date_minutes=200,
            tardiness_weight=1,
            operations=[
                Operation(
                    id="OP-1",
                    order_id="ORD-1",
                    sequence_number=1,
                    machine_id="M1",
                    processing_duration_minutes=30,
                    status=OperationStatus.COMPLETED,
                    actual_start_minute=0,
                    actual_end_minute=30,
                    remaining_duration_minutes=None,
                ),
                Operation(
                    id="OP-2",
                    order_id="ORD-1",
                    sequence_number=2,
                    machine_id="M1",
                    processing_duration_minutes=25,
                    status=OperationStatus.IN_PROGRESS,
                    actual_start_minute=30,
                    actual_end_minute=None,
                    remaining_duration_minutes=15,  # Locks M1 from clock 40 to 40+15=55
                ),
                Operation(
                    id="OP-3",
                    order_id="ORD-1",
                    sequence_number=3,
                    machine_id="M1",
                    processing_duration_minutes=20,
                    status=OperationStatus.PLANNED,
                    actual_start_minute=None,
                    actual_end_minute=None,
                    remaining_duration_minutes=None,
                ),
            ],
        )
    ]
    return Factory(
        workspace_id="ws-unit",
        machines=machines,
        downtimes=downtimes,
        orders=orders,
        current_time_minute=40,
    )


class TestValidateDisruption:
    """Rigorous validation of injected downtimes and rush orders against plant clock & lifecycles."""

    def test_invalid_disruption_type_rejected(self, base_execution_factory: Factory) -> None:
        delta = DisruptionDelta(added_downtimes=[], added_orders=[])
        with pytest.raises(DomainError, match="Invalid disruption_type"):
            validate_disruption(base_execution_factory, "RANDOM_TYPE", delta)

    def test_invalid_machine_id_rejected(self, base_execution_factory: Factory) -> None:
        delta = DisruptionDelta(
            added_downtimes=[
                DowntimeDisruptionItem(machine_id="NON_EXISTENT", start_minute=60, end_minute=80)
            ],
            added_orders=[],
        )
        with pytest.raises(ReferentialIntegrityError):
            validate_disruption(base_execution_factory, "MACHINE_DOWNTIME", delta)

    def test_invalid_interval_rejected(self, base_execution_factory: Factory) -> None:
        # Negative start
        delta1 = DisruptionDelta.model_construct(
            added_downtimes=[
                DowntimeDisruptionItem.model_construct(machine_id="M1", start_minute=-5, end_minute=50)
            ],
            added_orders=[],
        )
        with pytest.raises(InvalidIntervalError):
            validate_disruption(base_execution_factory, "MACHINE_DOWNTIME", delta1)

        # End <= start
        delta2 = DisruptionDelta.model_construct(
            added_downtimes=[
                DowntimeDisruptionItem.model_construct(machine_id="M1", start_minute=60, end_minute=50)
            ],
            added_orders=[],
        )
        with pytest.raises(InvalidIntervalError):
            validate_disruption(base_execution_factory, "MACHINE_DOWNTIME", delta2)

    def test_historical_downtime_ending_at_or_before_clock_rejected(
        self, base_execution_factory: Factory
    ) -> None:
        # Clock is 40. Injected downtime [10, 35) ends before 40.
        delta = DisruptionDelta(
            added_downtimes=[
                DowntimeDisruptionItem(machine_id="M1", start_minute=10, end_minute=35)
            ],
            added_orders=[],
        )
        with pytest.raises(LifecycleStateError) as exc_info:
            validate_disruption(base_execution_factory, "MACHINE_DOWNTIME", delta)
        assert exc_info.value.error_code == "HISTORICAL_DOWNTIME_CONFLICT"

        # Injected downtime ending exactly at clock 40
        delta_eq = DisruptionDelta(
            added_downtimes=[
                DowntimeDisruptionItem(machine_id="M1", start_minute=10, end_minute=40)
            ],
            added_orders=[],
        )
        with pytest.raises(LifecycleStateError) as exc_info_eq:
            validate_disruption(base_execution_factory, "MACHINE_DOWNTIME", delta_eq)
        assert exc_info_eq.value.error_code == "HISTORICAL_DOWNTIME_CONFLICT"

    def test_downtime_colliding_with_completed_operation_rejected(
        self, base_execution_factory: Factory
    ) -> None:
        # OP-1 was completed [0, 30). Downtime [20, 50) spans clock 40 but collides with [0, 30).
        delta = DisruptionDelta(
            added_downtimes=[
                DowntimeDisruptionItem(machine_id="M1", start_minute=20, end_minute=50)
            ],
            added_orders=[],
        )
        with pytest.raises(LifecycleStateError) as exc_info:
            validate_disruption(base_execution_factory, "MACHINE_DOWNTIME", delta)
        assert exc_info.value.error_code == "HISTORICAL_DOWNTIME_CONFLICT"
        assert "OP-1" in str(exc_info.value)

    def test_downtime_colliding_with_in_progress_locked_window_rejected(
        self, base_execution_factory: Factory
    ) -> None:
        # OP-2 is IN_PROGRESS: actual_start=30, clock=40, remaining=15 -> locked window is [30, 55).
        # Injected downtime [50, 70) collides with [30, 55).
        delta = DisruptionDelta(
            added_downtimes=[
                DowntimeDisruptionItem(machine_id="M1", start_minute=50, end_minute=70)
            ],
            added_orders=[],
        )
        with pytest.raises(LifecycleStateError) as exc_info:
            validate_disruption(base_execution_factory, "MACHINE_DOWNTIME", delta)
        assert exc_info.value.error_code == "HISTORICAL_DOWNTIME_CONFLICT"
        assert "OP-2" in str(exc_info.value)

    def test_downtime_touching_boundary_allowed(
        self, base_execution_factory: Factory
    ) -> None:
        # OP-2 locked window ends at 40 + 15 = 55.
        # Downtime starting exactly at 55 [55, 75) does NOT collide under half-open semantics!
        delta = DisruptionDelta(
            added_downtimes=[
                DowntimeDisruptionItem(machine_id="M1", start_minute=55, end_minute=75)
            ],
            added_orders=[],
        )
        # Should not raise
        validate_disruption(base_execution_factory, "MACHINE_DOWNTIME", delta)

    def test_rush_order_release_before_clock_rejected(
        self, base_execution_factory: Factory
    ) -> None:
        # Clock is 40. Rush order with release_time_minutes=35 precedes clock.
        delta = DisruptionDelta(
            added_downtimes=[],
            added_orders=[
                OrderDisruptionItem(
                    order_code="RUSH-PRE",
                    release_time_minutes=35,
                    due_date_minutes=80,
                    tardiness_weight=5.0,
                    operations=[
                        OperationDisruptionItem(sequence_index=1, machine_id="M1", processing_minutes=15)
                    ],
                )
            ],
        )
        with pytest.raises(LifecycleStateError) as exc_info:
            validate_disruption(base_execution_factory, "URGENT_ORDER", delta)
        assert exc_info.value.error_code == "INVALID_SEQUENCE"

    def test_rush_order_validation_errors(self, base_execution_factory: Factory) -> None:
        # Empty operations
        with pytest.raises(DomainError, match="at least one operation"):
            validate_disruption(
                base_execution_factory,
                "URGENT_ORDER",
                DisruptionDelta.model_construct(
                    added_downtimes=[],
                    added_orders=[
                        OrderDisruptionItem.model_construct(
                            order_code="RUSH-EMPTY",
                            release_time_minutes=40,
                            due_date_minutes=100,
                            tardiness_weight=1,
                            operations=[],
                        )
                    ],
                ),
            )

        # Due date < release
        with pytest.raises(DomainError, match="due date .* cannot precede release time"):
            validate_disruption(
                base_execution_factory,
                "URGENT_ORDER",
                DisruptionDelta.model_construct(
                    added_downtimes=[],
                    added_orders=[
                        OrderDisruptionItem.model_construct(
                            order_code="RUSH-DUE",
                            release_time_minutes=50,
                            due_date_minutes=45,
                            tardiness_weight=1,
                            operations=[
                                OperationDisruptionItem(sequence_index=1, machine_id="M1", processing_minutes=10)
                            ],
                        )
                    ],
                ),
            )

        # Negative tardiness weight
        with pytest.raises(DomainError, match="tardiness weight .* cannot be negative"):
            validate_disruption(
                base_execution_factory,
                "URGENT_ORDER",
                DisruptionDelta.model_construct(
                    added_downtimes=[],
                    added_orders=[
                        OrderDisruptionItem.model_construct(
                            order_code="RUSH-NEG",
                            release_time_minutes=40,
                            due_date_minutes=100,
                            tardiness_weight=-2,
                            operations=[
                                OperationDisruptionItem(sequence_index=1, machine_id="M1", processing_minutes=10)
                            ],
                        )
                    ],
                ),
            )

        # Non-positive processing time
        with pytest.raises(DomainError, match="must have positive duration"):
            validate_disruption(
                base_execution_factory,
                "URGENT_ORDER",
                DisruptionDelta.model_construct(
                    added_downtimes=[],
                    added_orders=[
                        OrderDisruptionItem.model_construct(
                            order_code="RUSH-ZERO",
                            release_time_minutes=40,
                            due_date_minutes=100,
                            tardiness_weight=1,
                            operations=[
                                OperationDisruptionItem.model_construct(sequence_index=1, machine_id="M1", processing_minutes=0)
                            ],
                        )
                    ],
                ),
            )


class TestSynthesizeDisruptedFactory:
    """Verify cloning and preservation of plant clock and operation lifecycles."""

    def test_clock_and_lifecycles_preserved(self, base_execution_factory: Factory) -> None:
        delta = DisruptionDelta(
            added_downtimes=[
                DowntimeDisruptionItem(machine_id="M1", start_minute=60, end_minute=80, reason="Motor repair")
            ],
            added_orders=[
                OrderDisruptionItem(
                    order_code="RUSH-1",
                    release_time_minutes=40,
                    due_date_minutes=120,
                    tardiness_weight=3.0,
                    operations=[
                        OperationDisruptionItem(sequence_index=1, machine_id="M1", processing_minutes=15)
                    ],
                )
            ],
        )

        disrupted = synthesize_disrupted_factory("ws-unit", base_execution_factory, delta)

        # 1. Factory clock strictly preserved
        assert disrupted.current_time_minute == base_execution_factory.current_time_minute == 40

        # 2. Existing order operations preserve lifecycle attributes
        ord1 = next(o for o in disrupted.orders if o.id == "ORD-1")
        op1 = ord1.operations[0]
        assert op1.status == OperationStatus.COMPLETED
        assert op1.actual_start_minute == 0
        assert op1.actual_end_minute == 30

        op2 = ord1.operations[1]
        assert op2.status == OperationStatus.IN_PROGRESS
        assert op2.actual_start_minute == 30
        assert op2.remaining_duration_minutes == 15

        op3 = ord1.operations[2]
        assert op3.status == OperationStatus.PLANNED
        assert op3.actual_start_minute is None
        assert op3.actual_end_minute is None

        # 3. Injected rush order operations tagged as PLANNED
        rush_order = next(o for o in disrupted.orders if o.order_code == "RUSH-1")
        assert len(rush_order.operations) == 1
        rush_op = rush_order.operations[0]
        assert rush_op.status == OperationStatus.PLANNED
        assert rush_op.actual_start_minute is None
        assert rush_op.actual_end_minute is None
        assert rush_op.remaining_duration_minutes is None

        # 4. Injected downtime present
        assert any(dt.start_minute == 60 and dt.end_minute == 80 for dt in disrupted.downtimes)


class TestComputeOperationDivergences:
    """Verify divergence calculations with completed and in-progress operations."""

    def test_completed_and_in_progress_divergences(self) -> None:
        baseline_ops = [
            ScheduledOperationModel(
                schedule_id="base",
                operation_id="op-1",
                order_id="ORD-1",
                sequence_number=1,
                machine_id="M1",
                start_minute=0,
                end_minute=30,
                processing_duration_minutes=30,
                slack_minutes=0,
            ),
            ScheduledOperationModel(
                schedule_id="base",
                operation_id="op-2",
                order_id="ORD-1",
                sequence_number=2,
                machine_id="M1",
                start_minute=30,
                end_minute=55,
                processing_duration_minutes=25,
                slack_minutes=0,
            ),
            ScheduledOperationModel(
                schedule_id="base",
                operation_id="op-3",
                order_id="ORD-1",
                sequence_number=3,
                machine_id="M1",
                start_minute=55,
                end_minute=75,
                processing_duration_minutes=20,
                slack_minutes=0,
            ),
        ]

        # In recovery schedule:
        # op-1 unchanged at 0..30 (UNMODIFIED)
        # op-2 unchanged at 30..55 (UNMODIFIED)
        # op-3 pushed to 80..100 due to downtime [55, 80) (DELAYED +25m)
        # rush-1 added at 100..115 (NEW_RUSH_OPERATION)
        recovery_ops = [
            ScheduledOperationModel(
                schedule_id="rec",
                operation_id="op-1",
                order_id="ORD-1",
                sequence_number=1,
                machine_id="M1",
                start_minute=0,
                end_minute=30,
                processing_duration_minutes=30,
                slack_minutes=0,
            ),
            ScheduledOperationModel(
                schedule_id="rec",
                operation_id="op-2",
                order_id="ORD-1",
                sequence_number=2,
                machine_id="M1",
                start_minute=30,
                end_minute=55,
                processing_duration_minutes=25,
                slack_minutes=0,
            ),
            ScheduledOperationModel(
                schedule_id="rec",
                operation_id="op-3",
                order_id="ORD-1",
                sequence_number=3,
                machine_id="M1",
                start_minute=80,
                end_minute=100,
                processing_duration_minutes=20,
                slack_minutes=0,
            ),
            ScheduledOperationModel(
                schedule_id="rec",
                operation_id="op-rush-1",
                order_id="RUSH-1",
                sequence_number=1,
                machine_id="M1",
                start_minute=100,
                end_minute=115,
                processing_duration_minutes=15,
                slack_minutes=0,
            ),
        ]

        divergences = compute_operation_divergences(baseline_ops, recovery_ops)

        # Check ORD-1 op 1
        d1 = next(d for d in divergences if d.order_id == "ORD-1" and d.sequence_index == 1)
        assert d1.status == "UNMODIFIED"
        assert d1.delta_start_minutes == 0

        # Check ORD-1 op 2
        d2 = next(d for d in divergences if d.order_id == "ORD-1" and d.sequence_index == 2)
        assert d2.status == "UNMODIFIED"
        assert d2.delta_start_minutes == 0

        # Check ORD-1 op 3
        d3 = next(d for d in divergences if d.order_id == "ORD-1" and d.sequence_index == 3)
        assert d3.status == "DELAYED"
        assert d3.delta_start_minutes == 25  # 80 - 55 = 25

        # Check RUSH-1
        drush = next(d for d in divergences if d.order_id == "RUSH-1")
        assert drush.status == "NEW_RUSH_OPERATION"
        assert drush.delta_start_minutes is None
