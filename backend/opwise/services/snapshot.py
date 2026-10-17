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
    ProductionOrder,
)


def serialize_factory_snapshot(factory_data: Any) -> str:
    """Serialize factory machines, downtimes, and orders into JSON string."""
    return json.dumps(
        {
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
        for o in data.get("orders", []):
            ops = [
                Operation(
                    id=op["id"],
                    order_id=o["id"],
                    sequence_number=op["seq"],
                    machine_id=op["m"],
                    processing_duration_minutes=op["dur"],
                )
                for op in o.get("operations", [])
            ]
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
        return Factory(workspace_id=workspace_id, machines=machines, downtimes=downtimes, orders=orders)
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
