"""Topology-growth protection.

The dependency-graph / task-tree reducers can accumulate unbounded
nodes if a runtime keeps creating tasks without ever finishing
them. This adapter caps node count + applies a FIFO eviction when
the cap is exceeded, keeping the visualization payload bounded.

Critically, it works *with* the sampling layer's
:func:`force_retain_structural` guarantee — structural-event
emission is never dropped, but the *derived topology view* can be
pruned without corrupting the underlying event stream.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TopologyBackpressureStats:
    capacity: int
    size: int
    evicted_total: int


class BoundedTopologyView:
    """LRU-capped node view of a topology graph."""

    __slots__ = ("_capacity", "_evicted", "_lock", "_nodes")

    def __init__(self, *, capacity: int = 65_536) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._nodes: OrderedDict[str, dict] = OrderedDict()
        self._evicted = 0
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def upsert(self, node_id: str, payload: dict) -> None:
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id] = payload
                self._nodes.move_to_end(node_id)
                return
            self._nodes[node_id] = payload
            while len(self._nodes) > self._capacity:
                self._nodes.popitem(last=False)
                self._evicted += 1

    def get(self, node_id: str) -> dict | None:
        with self._lock:
            value = self._nodes.get(node_id)
            if value is None:
                return None
            self._nodes.move_to_end(node_id)
            return value

    def remove(self, node_id: str) -> None:
        with self._lock:
            self._nodes.pop(node_id, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._nodes)

    def __contains__(self, node_id: str) -> bool:
        with self._lock:
            return node_id in self._nodes

    def stats(self) -> TopologyBackpressureStats:
        with self._lock:
            return TopologyBackpressureStats(
                capacity=self._capacity,
                size=len(self._nodes),
                evicted_total=self._evicted,
            )

    def clear(self) -> None:
        with self._lock:
            self._nodes.clear()
            self._evicted = 0
