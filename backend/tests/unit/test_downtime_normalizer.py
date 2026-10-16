"""Unit tests for machine downtime canonical merge normalization and horizon calculation.

Governed by SOLVER_MODEL.md Section 3 and DECISIONS.md (ADR-010).
"""

import pytest

from opwise.domain.downtime import (
    calculate_effective_horizon,
    normalize_machine_downtimes,
)
from opwise.domain.entities import MachineDowntime, Operation, ProductionOrder
from opwise.domain.exceptions import IntegerOverflowError, InvalidIntervalError


def test_empty_downtimes() -> None:
    """Empty list returns empty normalization result."""
    res = normalize_machine_downtimes([])
    assert res.merged_downtimes == []
    assert res.filtered_zero_length_count == 0
    assert len(res.advisory_warnings) == 0


def test_negative_start_minute_rejected() -> None:
    """Negative start minute raises InvalidIntervalError."""
    dt = MachineDowntime(id="DT1", machine_id="M1", start_minute=-10, end_minute=30)
    with pytest.raises(InvalidIntervalError) as exc_info:
        normalize_machine_downtimes([dt])
    assert exc_info.value.error_code == "INVALID_DOWNTIME_INTERVAL"
    assert exc_info.value.status_code == 422


def test_inverted_interval_rejected() -> None:
    """Inverted interval (start > end) raises InvalidIntervalError."""
    dt = MachineDowntime(id="DT1", machine_id="M1", start_minute=50, end_minute=20)
    with pytest.raises(InvalidIntervalError) as exc_info:
        normalize_machine_downtimes([dt])
    assert exc_info.value.error_code == "INVALID_DOWNTIME_INTERVAL"


def test_zero_length_downtime_filtered() -> None:
    """Zero-length interval (start == end) is filtered with advisory warning."""
    dts = [
        MachineDowntime(id="DT1", machine_id="M1", start_minute=30, end_minute=30),
        MachineDowntime(id="DT2", machine_id="M1", start_minute=60, end_minute=90),
    ]
    res = normalize_machine_downtimes(dts)
    assert len(res.merged_downtimes) == 1
    assert res.merged_downtimes[0].id == "DT2"
    assert res.filtered_zero_length_count == 1
    assert len(res.advisory_warnings) == 1
    assert "DT1" in res.advisory_warnings[0]


def test_overlapping_downtimes_merged() -> None:
    """Overlapping intervals on same machine are merged into [min, max)."""
    dts = [
        MachineDowntime(id="DT1", machine_id="M1", start_minute=30, end_minute=60),
        MachineDowntime(id="DT2", machine_id="M1", start_minute=50, end_minute=90),
    ]
    res = normalize_machine_downtimes(dts)
    assert len(res.merged_downtimes) == 1
    merged = res.merged_downtimes[0]
    assert merged.start_minute == 30
    assert merged.end_minute == 90
    assert merged.duration_minutes == 60


def test_adjacent_downtimes_merged() -> None:
    """Adjacent intervals (e.g. [0, 30) and [30, 60)) are merged into [0, 60)."""
    dts = [
        MachineDowntime(id="DT1", machine_id="M1", start_minute=0, end_minute=30),
        MachineDowntime(id="DT2", machine_id="M1", start_minute=30, end_minute=60),
    ]
    res = normalize_machine_downtimes(dts)
    assert len(res.merged_downtimes) == 1
    merged = res.merged_downtimes[0]
    assert merged.start_minute == 0
    assert merged.end_minute == 60


def test_disjoint_downtimes_remain_separate() -> None:
    """Disjoint intervals (e.g. [10, 30) and [40, 60)) remain separate."""
    dts = [
        MachineDowntime(id="DT1", machine_id="M1", start_minute=10, end_minute=30),
        MachineDowntime(id="DT2", machine_id="M1", start_minute=40, end_minute=60),
    ]
    res = normalize_machine_downtimes(dts)
    assert len(res.merged_downtimes) == 2
    assert res.merged_downtimes[0].start_minute == 10
    assert res.merged_downtimes[1].start_minute == 40


def test_multi_machine_isolation() -> None:
    """Downtimes on different machines are never merged together."""
    dts = [
        MachineDowntime(id="DT1", machine_id="M1", start_minute=10, end_minute=50),
        MachineDowntime(id="DT2", machine_id="M2", start_minute=20, end_minute=60),
    ]
    res = normalize_machine_downtimes(dts)
    assert len(res.merged_downtimes) == 2
    m1_dts = [d for d in res.merged_downtimes if d.machine_id == "M1"]
    m2_dts = [d for d in res.merged_downtimes if d.machine_id == "M2"]
    assert len(m1_dts) == 1
    assert len(m2_dts) == 1


def test_calculate_effective_horizon() -> None:
    """Verify horizon formula: max(release) + sum(processing) + sum(downtime)."""
    orders = [
        ProductionOrder(
            id="O1",
            order_code="J1",
            release_time_minutes=20,
            operations=[
                Operation(id="OP1", order_id="O1", sequence_number=1, machine_id="M1", processing_duration_minutes=30),
            ],
        ),
        ProductionOrder(
            id="O2",
            order_code="J2",
            release_time_minutes=50,
            operations=[
                Operation(id="OP2", order_id="O2", sequence_number=1, machine_id="M1", processing_duration_minutes=40),
            ],
        ),
    ]
    downtimes = [
        MachineDowntime(id="DT1", machine_id="M1", start_minute=10, end_minute=40),  # 30m
    ]

    # max_release = 50, processing = 70, downtime = 30 -> 150
    h = calculate_effective_horizon(orders, downtimes)
    assert h == 150


def test_horizon_overflow_protection() -> None:
    """Verify that excessive horizons trigger IntegerOverflowError."""
    huge_order = ProductionOrder(
        id="O1",
        order_code="J1",
        release_time_minutes=15_000_000,
        operations=[
            Operation(id="OP1", order_id="O1", sequence_number=1, machine_id="M1", processing_duration_minutes=10),
        ],
    )
    with pytest.raises(IntegerOverflowError) as exc_info:
        calculate_effective_horizon([huge_order], [])
    assert exc_info.value.error_code == "INTEGER_OVERFLOW_RISK"
    assert exc_info.value.status_code == 422
