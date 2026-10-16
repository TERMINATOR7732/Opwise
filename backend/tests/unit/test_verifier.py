"""Unit tests for the independent clean-room schedule verifier.

Governed by TEST_AND_RELEASE_PLAN.md Milestone 03 and SOLVER_MODEL.md Section 6.
"""

import copy
import time

from opwise.domain.entities import (
    Factory,
    Machine,
    ObjectiveMode,
    Schedule,
    ScheduleKPIs,
    ScheduleStatus,
)
from opwise.verifier.independent_verifier import (
    InvariantRule,
    ScheduleVerifier,
    VerificationStatus,
)


def test_verifier_valid_schedule_passes_all_invariants(
    sample_factory: Factory,
    valid_schedule: Schedule,
) -> None:
    """Empirically verify that a compliant schedule passes all 8 invariants."""
    verifier = ScheduleVerifier()
    report = verifier.verify(sample_factory, valid_schedule)

    assert report.is_valid is True
    assert report.status == VerificationStatus.VERIFIED
    assert len(report.failed_rules) == 0
    assert len(report.violations) == 0
    assert report.candidate_metrics_match is True
    assert report.recomputed_metrics is not None
    assert InvariantRule.INV_1_CARDINALITY in report.passed_rules
    assert InvariantRule.INV_2_DURATION_MACHINE in report.passed_rules
    assert InvariantRule.INV_3_RELEASE_TIME in report.passed_rules
    assert InvariantRule.INV_4_PRECEDENCE in report.passed_rules
    assert InvariantRule.INV_5_MACHINE_OVERLAP in report.passed_rules
    assert InvariantRule.INV_6_DOWNTIME_COLLISION in report.passed_rules
    assert InvariantRule.INV_7_HORIZON_BOUNDS in report.passed_rules
    assert InvariantRule.INV_8_METRIC_CONCORDANCE in report.passed_rules


def test_verifier_immutability_strict(
    sample_factory: Factory,
    valid_schedule: Schedule,
) -> None:
    """Verify that verifier execution does not mutate factory or schedule objects."""
    verifier = ScheduleVerifier()
    factory_copy = copy.deepcopy(sample_factory)
    schedule_copy = copy.deepcopy(valid_schedule)

    report = verifier.verify(sample_factory, valid_schedule)

    assert report.is_valid is True
    assert sample_factory == factory_copy
    assert valid_schedule == schedule_copy
    assert valid_schedule.verified is False  # verifier does not alter verified flag on input


def test_verifier_recomputed_metrics_and_utilization(
    sample_factory: Factory,
    valid_schedule: Schedule,
) -> None:
    """Verify exact analytical KPI and machine utilization recalculation."""
    verifier = ScheduleVerifier()
    report = verifier.verify(sample_factory, valid_schedule)

    assert report.recomputed_metrics is not None
    metrics = report.recomputed_metrics

    assert metrics.makespan_minutes == 165
    assert metrics.total_weighted_tardiness == 15
    assert metrics.late_order_count == 1
    assert metrics.on_time_rate == 50.0

    # Machine M1: 30m op, 30m downtime inside [0, 165], 135m available, 105m idle
    m1_util = metrics.machine_utilizations["M1"]
    assert m1_util.workload_minutes == 30
    assert m1_util.downtime_minutes == 30
    assert m1_util.idle_minutes == 105
    assert m1_util.net_utilization_pct == 22.22
    assert m1_util.gross_utilization_pct == 18.18

    # Machine M2: 85m ops (45 + 40), 0m downtime, 80m idle
    m2_util = metrics.machine_utilizations["M2"]
    assert m2_util.workload_minutes == 85
    assert m2_util.downtime_minutes == 0
    assert m2_util.idle_minutes == 80
    assert m2_util.net_utilization_pct == 51.52
    assert m2_util.gross_utilization_pct == 51.52

    # Machine M3: 50m ops, 0m downtime, 115m idle
    m3_util = metrics.machine_utilizations["M3"]
    assert m3_util.workload_minutes == 50
    assert m3_util.downtime_minutes == 0
    assert m3_util.idle_minutes == 115
    assert m3_util.net_utilization_pct == 30.3
    assert m3_util.gross_utilization_pct == 30.3


def test_verifier_no_work_state() -> None:
    """Test Case 2: Factory with machines but 0 orders correctly verified."""
    factory = Factory(
        workspace_id="WS-EMPTY",
        machines=[Machine(id="M1", name="Mill")],
        downtimes=[],
        orders=[],
    )
    schedule = Schedule(
        id="SCHED-EMPTY",
        workspace_id="WS-EMPTY",
        status=ScheduleStatus.NO_WORK_STATE,
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        kpis=ScheduleKPIs(
            makespan_minutes=0,
            total_weighted_tardiness=0,
            late_order_count=0,
            on_time_rate=100.0,
        ),
        scheduled_operations=[],
        verified=False,
    )
    verifier = ScheduleVerifier()
    report = verifier.verify(factory, schedule)

    assert report.is_valid is True
    assert report.status == VerificationStatus.VERIFIED
    assert len(report.failed_rules) == 0
    assert report.candidate_metrics_match is True
    assert report.recomputed_metrics is not None
    assert report.recomputed_metrics.makespan_minutes == 0
    assert report.recomputed_metrics.on_time_rate == 100.0


def test_verifier_no_work_state_mismatched_kpis() -> None:
    """Test Case 2 fails if candidate schedule claims non-zero makespan."""
    factory = Factory(
        workspace_id="WS-EMPTY",
        machines=[Machine(id="M1", name="Mill")],
        downtimes=[],
        orders=[],
    )
    schedule = Schedule(
        id="SCHED-EMPTY-BAD",
        workspace_id="WS-EMPTY",
        status=ScheduleStatus.NO_WORK_STATE,
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        kpis=ScheduleKPIs(
            makespan_minutes=50,  # Falsified
            total_weighted_tardiness=0,
            late_order_count=0,
            on_time_rate=100.0,
        ),
        scheduled_operations=[],
        verified=False,
    )
    verifier = ScheduleVerifier()
    report = verifier.verify(factory, schedule)

    assert report.is_valid is False
    assert report.status == VerificationStatus.VERIFICATION_FAILED
    assert InvariantRule.INV_8_METRIC_CONCORDANCE in report.failed_rules


def test_verifier_skipped_for_empty_solve_statuses(sample_factory: Factory) -> None:
    """Test unattempted/infeasible solves without operations return SKIPPED."""
    verifier = ScheduleVerifier()
    for status in [ScheduleStatus.INFEASIBLE, ScheduleStatus.TIMEOUT, ScheduleStatus.MODEL_INVALID]:
        sched = Schedule(
            id=f"SCHED-{status.value}",
            workspace_id="WS-001",
            status=status,
            objective_mode=ObjectiveMode.PURE_MAKESPAN,
            kpis=ScheduleKPIs(
                makespan_minutes=0,
                total_weighted_tardiness=0,
                late_order_count=0,
                on_time_rate=100.0,
            ),
            scheduled_operations=[],
        )
        report = verifier.verify(sample_factory, sched)
        assert report.status == VerificationStatus.SKIPPED
        assert report.is_valid is False


def test_verifier_execution_speed(
    sample_factory: Factory,
    valid_schedule: Schedule,
) -> None:
    """Verify performance requirement: schedule verification audit executes in < 5ms."""
    verifier = ScheduleVerifier()
    start_time = time.perf_counter()
    report = verifier.verify(sample_factory, valid_schedule)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    assert report.is_valid is True
    assert elapsed_ms < 5.0, f"Verification took {elapsed_ms:.2f}ms, expected < 5.0ms"
