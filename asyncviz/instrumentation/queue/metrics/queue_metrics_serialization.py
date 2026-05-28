"""Serialization helpers for queue metrics snapshots + deltas.

The engine uses these to render JSON-safe payloads for the diagnostics
endpoint and the websocket streaming surface. Snapshot / delta classes
themselves expose ``to_dict`` where useful; this module provides
``from_dict`` round-trip helpers for the replay layer.
"""

from __future__ import annotations

from typing import Any

from asyncviz.instrumentation.queue.metrics.queue_metrics_models import (
    QueueContentionSnapshot,
    QueueMetricsRecord,
    QueueOccupancySnapshot,
    QueuePressureSnapshot,
    QueueThroughputSnapshot,
    QueueWaitSnapshot,
)


def record_from_dict(data: dict[str, Any]) -> QueueMetricsRecord:
    """Reconstruct a :class:`QueueMetricsRecord` from its ``to_dict`` view."""
    return QueueMetricsRecord(
        queue_id=str(data["queue_id"]),
        queue_kind=str(data["queue_kind"]),
        maxsize=int(data.get("maxsize", 0)),
        sequence=int(data.get("sequence", 0)),
        occupancy=QueueOccupancySnapshot(**_subdict(data, "occupancy")),
        throughput=QueueThroughputSnapshot(**_subdict(data, "throughput")),
        contention=QueueContentionSnapshot(**_subdict(data, "contention")),
        pressure=QueuePressureSnapshot(**_subdict(data, "pressure")),
        put_wait=QueueWaitSnapshot(**_subdict(data, "put_wait")),
        get_wait=QueueWaitSnapshot(**_subdict(data, "get_wait")),
    )


def _subdict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    raw = parent.get(key) or {}
    return {k: v for k, v in raw.items() if not k.startswith("_")}
