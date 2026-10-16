"""Unit tests for pure domain entities and invariants."""

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


def test_machine_creation() -> None:
    """Test machine entity creation and properties."""
    m = Machine(id="M1", name="CNC Mill", description="Primary vertical mill")
    assert m.id == "M1"
    assert m.name == "CNC Mill"
    assert m.description == "Primary vertical mill"


def test_downtime_duration_and_overlap() -> None:
    """Test half-open interval duration and overlap detection."""
    dt1 = MachineDowntime(id="DT-1", machine_id="M1", start_minute=30, end_minute=60)
    dt2 = MachineDowntime(id="DT-2", machine_id="M1", start_minute=50, end_minute=90)
    dt3 = MachineDowntime(id="DT-3", machine_id="M1", start_minute=60, end_minute=80)
    dt_diff_machine = MachineDowntime(id="DT-4", machine_id="M2", start_minute=30, end_minute=60)

    assert dt1.duration_minutes == 30
    assert dt1.overlaps_with(dt2) is True
    # Contact at minute 60 is adjacent, not overlapping
    assert dt1.overlaps_with(dt3) is False
    assert dt1.is_adjacent_to(dt3) is True
    assert dt1.overlaps_with(dt_diff_machine) is False


def test_order_total_processing_time() -> None:
    """Test production order total duration accumulation."""
    ops = [
        Operation(id="OP1", order_id="O1", sequence_number=1, machine_id="M1", processing_duration_minutes=25),
        Operation(id="OP2", order_id="O1", sequence_number=2, machine_id="M2", processing_duration_minutes=35),
    ]
    order = ProductionOrder(id="O1", order_code="J1", operations=ops)
    assert order.total_processing_time == 60


def test_factory_lookup_methods(sample_factory: Factory) -> None:
    """Test factory machine and order retrieval."""
    assert sample_factory.get_machine("M1") is not None
    assert sample_factory.get_machine("M999") is None
    assert sample_factory.get_order("ORD-01") is not None
    assert sample_factory.get_order("ORD-999") is None


def test_schedule_and_kpis() -> None:
    """Test schedule container entity and KPI types."""
    kpis = ScheduleKPIs(
        makespan_minutes=165,
        total_weighted_tardiness=0,
        late_order_count=0,
        on_time_rate=100.0,
    )
    scheduled_op = ScheduledOperation(
        operation_id="OP1",
        order_id="O1",
        machine_id="M1",
        sequence_number=1,
        start_minute=0,
        end_minute=30,
        processing_duration_minutes=30,
        slack_minutes=15,
    )
    schedule = Schedule(
        id="SCHED-01",
        workspace_id="WS-01",
        status=ScheduleStatus.OPTIMAL,
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        kpis=kpis,
        scheduled_operations=[scheduled_op],
        verified=True,
    )

    assert schedule.status == ScheduleStatus.OPTIMAL
    assert schedule.objective_mode == ObjectiveMode.PURE_MAKESPAN
    assert schedule.kpis.makespan_minutes == 165
    assert schedule.verified is True
    assert len(schedule.scheduled_operations) == 1
    assert InputClassification.VALID_NON_EMPTY_FACTORY.value == "VALID_NON_EMPTY_FACTORY"
