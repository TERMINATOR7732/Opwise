"""Snapshot serialization and deserialization utilities for factory state.

Governed by DATA_AND_API.md Section 1.1 and Section 3.3.
"""

import json
from typing import Any

from opwise.domain.entities import (
    Factory,
    Machine,
    MachineDowntime,
    Operation,
    OperationStatus,
    ProductionOrder,
)


def serialize_factory_snapshot(factory_data: Any) -> str:
    """Serialize factory machines, downtimes, and orders into JSON string."""
    clock = getattr(factory_data, "current_time_minute", 0)
    return json.dumps(
        {
            "current_time_minute": clock,
            "machines": [{"id": m.id, "name": m.name} for m in factory_data.machines],
            "downtimes": [
                {
                    "id": dt.id,
                    "machine_id": dt.machine_id,
                    "start": dt.start_minute,
                    "end": dt.end_minute,
                }
                for dt in factory_data.downtimes
            ],
            "orders": [
                {
                    "id": o.id,
                    "code": o.order_code,
                    "release": o.release_time_minutes,
                    "due": o.due_date_minutes,
                    "weight": o.tardiness_weight,
                    "operations": [
                        {
                            "id": op.id,
                            "seq": op.sequence_number,
                            "m": op.machine_id,
                            "dur": op.processing_duration_minutes,
                            "status": op.status.value if hasattr(op.status, "value") else str(op.status or "PLANNED"),
                            "actual_start": op.actual_start_minute,
                            "actual_end": op.actual_end_minute,
                            "rem_dur": op.remaining_duration_minutes,
                        }
                        for op in o.operations
                    ],
                }
                for o in factory_data.orders
            ],
        }
    )


def reconstruct_factory_from_snapshot(workspace_id: str, snapshot_str: str) -> Factory | None:
    """Reconstruct a domain Factory entity from an immutable input snapshot JSON string."""
    try:
        data = json.loads(snapshot_str)
        clock = data.get("current_time_minute", 0)
        if not isinstance(clock, int) or clock < 0:
            return None

        machines = [Machine(id=m["id"], name=m["name"]) for m in data.get("machines", [])]
        downtimes = [
            MachineDowntime(
                id=dt["id"],
                machine_id=dt["machine_id"],
                start_minute=dt["start"],
                end_minute=dt["end"],
            )
            for dt in data.get("downtimes", [])
        ]
        orders: list[ProductionOrder] = []
        valid_statuses = {s.value for s in OperationStatus}
        for o in data.get("orders", []):
            ops: list[Operation] = []
            for op in o.get("operations", []):
                raw_status = op.get("status", "PLANNED")
                if raw_status not in valid_statuses:
                    return None
                status = OperationStatus(raw_status)
                actual_start = op.get("actual_start")
                actual_end = op.get("actual_end")
                rem_dur = op.get("rem_dur")
                ops.append(
                    Operation(
                        id=op["id"],
                        order_id=o["id"],
                        sequence_number=op["seq"],
                        machine_id=op["m"],
                        processing_duration_minutes=op["dur"],
                        status=status,
                        actual_start_minute=actual_start,
                        actual_end_minute=actual_end,
                        remaining_duration_minutes=rem_dur,
                    )
                )
            orders.append(
                ProductionOrder(
                    id=o["id"],
                    order_code=o["code"],
                    release_time_minutes=o["release"],
                    due_date_minutes=o["due"],
                    tardiness_weight=o["weight"],
                    operations=ops,
                )
            )
        return Factory(
            workspace_id=workspace_id,
            machines=machines,
            downtimes=downtimes,
            orders=orders,
            current_time_minute=clock,
        )
    except Exception:
        return None


def extract_snapshot_overview(snapshot_str: str) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Extract machine descriptors and downtime intervals from snapshot JSON string."""
    try:
        data = json.loads(snapshot_str)
        machines = [{"id": str(m["id"]), "name": str(m.get("name", m["id"]))} for m in data.get("machines", [])]
        downtimes = [
            {
                "id": str(dt["id"]),
                "machine_id": str(dt["machine_id"]),
                "start": int(dt["start"]),
                "end": int(dt["end"]),
                "reason": dt.get("reason"),
            }
            for dt in data.get("downtimes", [])
        ]
        return machines, downtimes
    except Exception:
        return [], []
