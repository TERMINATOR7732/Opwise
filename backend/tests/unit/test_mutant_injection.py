"""Adversarial mutant injection test suite for Opwise Independent Verifier.

Governed by TEST_AND_RELEASE_PLAN.md Milestone 03 and Rule 6.3.
Systematically injects single-fault mutations across all 8 invariant categories.
"""

import copy

from opwise.domain.entities import (
    Factory,
    ObjectiveMode,
    Schedule,
    ScheduledOperation,
    ScheduleKPIs,
    ScheduleStatus,
)
from opwise.verifier.independent_verifier import (
    InvariantRule,
    ScheduleVerifier,
    VerificationStatus,
)

# ==============================================================================
# Invariant 1: Operation Coverage & Cardinality
# ==============================================================================

def test_mutant_missing_operation(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 1a: Dropping a required operation fails Invariant 1 (Cardinality)."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    mutated.scheduled_operations = [op for op in mutated.scheduled_operations if op.operation_id != "OP-02-2"]

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert report.status == VerificationStatus.VERIFICATION_FAILED
    assert InvariantRule.INV_1_CARDINALITY in report.failed_rules
    assert any("OP-02-2" in v.message for v in report.violations)


def test_mutant_duplicate_operation(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 1b: Duplicating an operation fails Invariant 1 (Cardinality)."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    dup = copy.deepcopy(mutated.scheduled_operations[0])
    mutated.scheduled_operations.append(dup)

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert report.status == VerificationStatus.VERIFICATION_FAILED
    assert InvariantRule.INV_1_CARDINALITY in report.failed_rules
    assert any(v.entity_id == dup.operation_id for v in report.violations)


def test_mutant_extra_unknown_operation(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 1c: Adding an unknown operation not in factory fails Invariant 1."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    extra_op = ScheduledOperation(
        operation_id="OP-ROUGE-999",
        order_id="ORD-01",
        machine_id="M1",
        sequence_number=99,
        start_minute=200,
        end_minute=230,
        processing_duration_minutes=30,
    )
    mutated.scheduled_operations.append(extra_op)

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_1_CARDINALITY in report.failed_rules


# ==============================================================================
# Invariant 2: Duration & Machine Alignment
# ==============================================================================

def test_mutant_duration_mismatch(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 2a: Expanding an operation span beyond p fails Invariant 2."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    # OP-01-1 duration is 30, stretch to 45
    mutated.scheduled_operations[0] = ScheduledOperation(
        operation_id="OP-01-1",
        order_id="ORD-01",
        machine_id="M1",
        sequence_number=1,
        start_minute=0,
        end_minute=45,  # span 45 != 30
        processing_duration_minutes=30,
    )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_2_DURATION_MACHINE in report.failed_rules
    assert any(v.entity_id == "OP-01-1" for v in report.violations)


def test_mutant_machine_mismatch(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 2b: Scheduling an operation on the wrong machine fails Invariant 2."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    # OP-01-1 requires M1, schedule on M3
    mutated.scheduled_operations[0] = ScheduledOperation(
        operation_id="OP-01-1",
        order_id="ORD-01",
        machine_id="M3",  # Expected M1
        sequence_number=1,
        start_minute=0,
        end_minute=30,
        processing_duration_minutes=30,
    )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_2_DURATION_MACHINE in report.failed_rules


# ==============================================================================
# Invariant 3: Release Time Compliance
# ==============================================================================

def test_mutant_early_release_violation(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 3: Starting order before release time (S < r) fails Invariant 3."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    # ORD-02 release time is 10. Start OP-02-1 at minute 5.
    for i, op in enumerate(mutated.scheduled_operations):
        if op.operation_id == "OP-02-1":
            mutated.scheduled_operations[i] = ScheduledOperation(
                operation_id=op.operation_id,
                order_id=op.order_id,
                machine_id=op.machine_id,
                sequence_number=op.sequence_number,
                start_minute=5,  # < r_j (10)
                end_minute=45,
                processing_duration_minutes=40,
            )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_3_RELEASE_TIME in report.failed_rules
    assert any(v.entity_id == "ORD-02" for v in report.violations)


# ==============================================================================
# Invariant 4: Precedence Sequence Compliance
# ==============================================================================

def test_mutant_precedence_violation(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 4: Overlapping consecutive operations of an order fails Invariant 4."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    # ORD-01 op 1 ends at 30. Force op 2 to start at 25 (< 30)
    for i, op in enumerate(mutated.scheduled_operations):
        if op.operation_id == "OP-01-2":
            mutated.scheduled_operations[i] = ScheduledOperation(
                operation_id=op.operation_id,
                order_id=op.order_id,
                machine_id=op.machine_id,
                sequence_number=op.sequence_number,
                start_minute=25,  # Preceding ends at 30
                end_minute=70,
                processing_duration_minutes=45,
            )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_4_PRECEDENCE in report.failed_rules
    assert any(v.entity_id == "OP-01-2" for v in report.violations)


# ==============================================================================
# Invariant 5: Machine Exclusivity / Non-Overlap
# ==============================================================================

def test_mutant_machine_overlap(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 5: Overlapping two operations on the same machine fails Invariant 5."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    # Both OP-01-2 and OP-02-1 are on M2.
    # OP-01-2: [30, 75). Force OP-02-1 to [70, 110) -> overlaps [70, 75)
    for i, op in enumerate(mutated.scheduled_operations):
        if op.operation_id == "OP-02-1":
            mutated.scheduled_operations[i] = ScheduledOperation(
                operation_id=op.operation_id,
                order_id=op.order_id,
                machine_id=op.machine_id,
                sequence_number=op.sequence_number,
                start_minute=70,  # collides with OP-01-2 ending at 75
                end_minute=110,
                processing_duration_minutes=40,
            )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_5_MACHINE_OVERLAP in report.failed_rules
    assert any(v.entity_id == "M2" for v in report.violations)


# ==============================================================================
# Invariant 6: Machine Downtime Respect & Half-Open Boundary Non-Collision
# ==============================================================================

def test_mutant_downtime_collision(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 6a: Scheduling an operation inside downtime window fails Invariant 6."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    # M1 has downtime DT-01: [60, 90). Schedule OP-01-1 at [50, 80)
    mutated.scheduled_operations[0] = ScheduledOperation(
        operation_id="OP-01-1",
        order_id="ORD-01",
        machine_id="M1",
        sequence_number=1,
        start_minute=50,
        end_minute=80,  # collides with [60, 90)
        processing_duration_minutes=30,
    )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_6_DOWNTIME_COLLISION in report.failed_rules
    assert any(v.entity_id == "OP-01-1" for v in report.violations)


def test_downtime_boundary_contact_passes(sample_factory: Factory) -> None:
    """Mutant 6b (Negative Control): Exact boundary contact [30, 60) with downtime [60, 90) passes."""
    verifier = ScheduleVerifier()
    # M1 downtime is [60, 90). Schedule OP-01-1 [30, 60), exactly touching start of downtime.
    # OP-01-2 on M2: [60, 105). OP-02-1 on M2: [105, 145). OP-02-2 on M3: [145, 195).
    kpis = ScheduleKPIs(
        makespan_minutes=195,
        total_weighted_tardiness=45,
        late_order_count=1,
        on_time_rate=50.0,
    )
    sched = Schedule(
        id="SCHED-BOUNDARY",
        workspace_id="WS-001",
        status=ScheduleStatus.OPTIMAL,
        objective_mode=ObjectiveMode.PURE_MAKESPAN,
        kpis=kpis,
        scheduled_operations=[
            ScheduledOperation(
                operation_id="OP-01-1",
                order_id="ORD-01",
                machine_id="M1",
                sequence_number=1,
                start_minute=30,
                end_minute=60,  # exact boundary contact at minute 60 with DT [60, 90)
                processing_duration_minutes=30,
            ),
            ScheduledOperation(
                operation_id="OP-01-2",
                order_id="ORD-01",
                machine_id="M2",
                sequence_number=2,
                start_minute=60,
                end_minute=105,
                processing_duration_minutes=45,
            ),
            ScheduledOperation(
                operation_id="OP-02-1",
                order_id="ORD-02",
                machine_id="M2",
                sequence_number=1,
                start_minute=105,
                end_minute=145,
                processing_duration_minutes=40,
            ),
            ScheduledOperation(
                operation_id="OP-02-2",
                order_id="ORD-02",
                machine_id="M3",
                sequence_number=2,
                start_minute=145,
                end_minute=195,
                processing_duration_minutes=50,
            ),
        ],
    )
    report = verifier.verify(sample_factory, sched)
    assert report.is_valid is True
    assert InvariantRule.INV_6_DOWNTIME_COLLISION in report.passed_rules


# ==============================================================================
# Invariant 7: Horizon Bounds & Non-Negative Integer Grid
# ==============================================================================

def test_mutant_negative_start_time(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 7a: Negative start timestamp fails Invariant 7."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    mutated.scheduled_operations[0] = ScheduledOperation(
        operation_id="OP-01-1",
        order_id="ORD-01",
        machine_id="M1",
        sequence_number=1,
        start_minute=-10,  # Negative start
        end_minute=20,
        processing_duration_minutes=30,
    )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_7_HORIZON_BOUNDS in report.failed_rules


def test_mutant_inverted_time_interval(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 7b: Inverted interval (end <= start) fails Invariant 7."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    mutated.scheduled_operations[0] = ScheduledOperation(
        operation_id="OP-01-1",
        order_id="ORD-01",
        machine_id="M1",
        sequence_number=1,
        start_minute=30,
        end_minute=10,  # Inverted
        processing_duration_minutes=30,
    )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_7_HORIZON_BOUNDS in report.failed_rules


def test_mutant_exceeding_horizon(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 7c: Operation completion beyond effective horizon H fails Invariant 7."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    # Effective horizon for sample_factory is 205 (10 + 165 + 30).
    # Schedule OP-02-2 at [300, 350).
    for i, op in enumerate(mutated.scheduled_operations):
        if op.operation_id == "OP-02-2":
            mutated.scheduled_operations[i] = ScheduledOperation(
                operation_id=op.operation_id,
                order_id=op.order_id,
                machine_id=op.machine_id,
                sequence_number=op.sequence_number,
                start_minute=300,
                end_minute=350,  # > H (205)
                processing_duration_minutes=50,
            )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_7_HORIZON_BOUNDS in report.failed_rules


# ==============================================================================
# Invariant 8: Metric Concordance & Stage-1 Preservation
# ==============================================================================

def test_mutant_falsified_makespan_kpi(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 8a: Candidate schedule lying about makespan fails Invariant 8."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    mutated.kpis = ScheduleKPIs(
        makespan_minutes=100,  # True is 165
        total_weighted_tardiness=15,
        late_order_count=1,
        on_time_rate=50.0,
    )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_8_METRIC_CONCORDANCE in report.failed_rules
    assert report.candidate_metrics_match is False


def test_mutant_falsified_tardiness_kpi(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 8b: Candidate schedule falsely claiming zero tardiness fails Invariant 8."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    mutated.kpis = ScheduleKPIs(
        makespan_minutes=165,
        total_weighted_tardiness=0,  # True is 15
        late_order_count=1,
        on_time_rate=50.0,
    )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_8_METRIC_CONCORDANCE in report.failed_rules


def test_mutant_falsified_late_order_count(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 8c: Candidate schedule falsely reporting 0 late orders fails Invariant 8."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    mutated.kpis = ScheduleKPIs(
        makespan_minutes=165,
        total_weighted_tardiness=15,
        late_order_count=0,  # True is 1
        on_time_rate=50.0,
    )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_8_METRIC_CONCORDANCE in report.failed_rules


def test_mutant_falsified_on_time_rate(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 8d: Candidate schedule falsely claiming 100% on-time fails Invariant 8."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    mutated.kpis = ScheduleKPIs(
        makespan_minutes=165,
        total_weighted_tardiness=15,
        late_order_count=1,
        on_time_rate=100.0,  # True is 50.0
    )

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_8_METRIC_CONCORDANCE in report.failed_rules


def test_mutant_stage1_bound_breached(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 8e: Stage 2 schedule exceeding Stage 1 optimal bound fails Invariant 8 (Preservation)."""
    verifier = ScheduleVerifier()
    # Candidate schedule has recomputed tardiness 15.
    # If Stage 1 optimal bound was proven as 10, this solve violates lexicographic gating!
    report = verifier.verify(sample_factory, valid_schedule, stage1_bound=10)

    assert report.is_valid is False
    assert report.status == VerificationStatus.VERIFICATION_FAILED
    assert InvariantRule.INV_8_STAGE1_PRESERVATION in report.failed_rules
    assert any("exceeds Stage-1 optimal bound" in v.message for v in report.violations)


def test_stage1_bound_satisfied_passes(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Negative control: Stage 2 schedule respecting Stage 1 optimal bound passes."""
    verifier = ScheduleVerifier()
    # Candidate schedule has tardiness 15, which satisfies bound 15 or 20.
    report = verifier.verify(sample_factory, valid_schedule, stage1_bound=15)

    assert report.is_valid is True
    assert report.status == VerificationStatus.VERIFIED
    assert InvariantRule.INV_8_STAGE1_PRESERVATION in report.passed_rules


def test_mutant_entire_order_omitted(sample_factory: Factory, valid_schedule: Schedule) -> None:
    """Mutant 1d: Omission of all operations for an order triggers cardinality failure and skips precedence safely."""
    verifier = ScheduleVerifier()
    mutated = copy.deepcopy(valid_schedule)
    mutated.scheduled_operations = [op for op in mutated.scheduled_operations if op.order_id != "ORD-02"]

    report = verifier.verify(sample_factory, mutated)
    assert report.is_valid is False
    assert InvariantRule.INV_1_CARDINALITY in report.failed_rules

