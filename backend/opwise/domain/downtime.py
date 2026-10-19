import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from opwise.domain.entities import MachineDowntime, OperationStatus
from opwise.domain.exceptions import InvalidIntervalError

if TYPE_CHECKING:
    from opwise.domain.entities import ProductionOrder

logger = logging.getLogger("opwise.domain.downtime")


@dataclass(frozen=True)
class NormalizationResult:
    """The result of canonical downtime merge normalization."""

    merged_downtimes: list[MachineDowntime]
    filtered_zero_length_count: int
    advisory_warnings: list[str]


def normalize_machine_downtimes(
    downtimes: list[MachineDowntime],
) -> NormalizationResult:
    """Sort, validate, and canonically merge downtime intervals per machine.

    Rules:
    1. Rejects negative start minutes (Ds < 0) or inverted intervals (Ds > De).
    2. Filters zero-length intervals (Ds == De) with an advisory warning.
    3. Merges overlapping intervals (D1,s <= D2,s < D1,e) into [min, max).
    4. Merges adjacent intervals (D1,e == D2,s) into [D1,s, D2,e).
    5. Preserves boundary non-collision: contact at minute T does not collide.
    """
    by_machine: dict[str, list[MachineDowntime]] = defaultdict(list)
    advisories: list[str] = []
    zero_count = 0

    # Step 1: Validate intervals and filter zero-length
    for dt in downtimes:
        if dt.start_minute < 0 or dt.start_minute > dt.end_minute:
            raise InvalidIntervalError(
                downtime_id=dt.id,
                start=dt.start_minute,
                end=dt.end_minute,
            )
        if dt.start_minute == dt.end_minute:
            zero_count += 1
            advisories.append(
                f"Filtered zero-length downtime '{dt.id}' on machine '{dt.machine_id}' at minute {dt.start_minute}."
            )
            continue
        by_machine[dt.machine_id].append(dt)

    merged_all: list[MachineDowntime] = []

    # Step 2: Canonical merge per machine
    for machine_id, machine_dts in by_machine.items():
        # Sort by start_minute ascending, then end_minute
        sorted_dts = sorted(machine_dts, key=lambda d: (d.start_minute, d.end_minute))
        if not sorted_dts:
            continue

        current = sorted_dts[0]
        merged_machine: list[MachineDowntime] = []

        for next_dt in sorted_dts[1:]:
            # Overlapping or adjacent: current.end_minute >= next_dt.start_minute
            if current.end_minute >= next_dt.start_minute:
                # Merge into unified half-open interval
                new_end = max(current.end_minute, next_dt.end_minute)
                current = MachineDowntime(
                    id=f"{current.id}+{next_dt.id}",
                    machine_id=machine_id,
                    start_minute=current.start_minute,
                    end_minute=new_end,
                    reason=f"Merged: {current.reason or current.id}; {next_dt.reason or next_dt.id}".strip("; "),
                )
            else:
                merged_machine.append(current)
                current = next_dt

        merged_machine.append(current)
        merged_all.extend(merged_machine)

    return NormalizationResult(
        merged_downtimes=merged_all,
        filtered_zero_length_count=zero_count,
        advisory_warnings=advisories,
    )


def calculate_effective_horizon(
    orders: list["ProductionOrder"],
    merged_downtimes: list[MachineDowntime],
    current_time_minute: int = 0,
    max_cap: int = 10_000_000,
    overflow_limit: int = 2_147_483_647,
) -> int:
    """Compute the safe dynamic scheduling horizon H with overflow guards.

    Execution-Aware Formula:
        base_start = max(max(r_j), current_time_minute)
        future_work = sum(p_planned) + sum(remaining_in_progress)
        max_historical_end = max(actual_end_completed)
        H = max(base_start + future_work + sum(downtimes), max_historical_end)
    """
    from opwise.domain.exceptions import IntegerOverflowError

    max_release: int = max((o.release_time_minutes for o in orders), default=0)
    base_start: int = max(max_release, current_time_minute)

    future_work: int = 0
    max_historical_end: int = 0

    for o in orders:
        for op in o.operations:
            if op.status == OperationStatus.PLANNED:
                future_work += op.processing_duration_minutes
            elif op.status == OperationStatus.IN_PROGRESS:
                future_work += (
                    op.remaining_duration_minutes
                    if op.remaining_duration_minutes is not None
                    else op.processing_duration_minutes
                )
            elif op.status == OperationStatus.COMPLETED and op.actual_end_minute is not None:
                max_historical_end = max(max_historical_end, op.actual_end_minute)

    total_downtime: int = sum(dt.duration_minutes for dt in merged_downtimes)

    horizon: int = max(base_start + future_work + total_downtime, max_historical_end)

    if horizon > overflow_limit:
        raise IntegerOverflowError(calculated_horizon=horizon, max_allowed=overflow_limit)

    if horizon > max_cap:
        raise IntegerOverflowError(calculated_horizon=horizon, max_allowed=max_cap)

    return horizon
