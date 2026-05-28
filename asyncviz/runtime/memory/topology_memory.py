"""Compact graph storage for dependency / await topologies.

Interns node ids + stores adjacency as a dict of frozensets keyed
by interned strings. Bounded by node count; nodes are evicted in
insertion order (FIFO) when the cap is exceeded.

The adjacency dict is the dominant memory footprint of the
dependency-graph visualization once the runtime gets large; this
module exists to keep it sane on long-running runtimes.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass

from asyncviz.runtime.memory.event_interning import StringInterner
from asyncviz.runtime.memory.memory_observability import get_memory_metrics
from asyncviz.runtime.memory.memory_tracing import record_memory_trace


@dataclass(frozen=True, slots=True)
class TopologyStats:
    node_count: int
    edge_count: int
    capacity: int
    evictions: int


class CompactTopology:
    """Compact bounded adjacency graph."""

    __slots__ = (
        "_capacity",
        "_evictions",
        "_interner",
        "_lock",
        "_nodes",
    )

    def __init__(
        self, *, capacity: int = 65536, interner: StringInterner,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._interner = interner
        self._nodes: OrderedDict[str, set[str]] = OrderedDict()
        self._lock = threading.Lock()
        self._evictions = 0

    def add_edge(self, source: str, target: str) -> None:
        src = self._interner.intern(source)
        tgt = self._interner.intern(target)
        with self._lock:
            adjacency = self._nodes.get(src)
            if adjacency is None:
                adjacency = set()
                self._nodes[src] = adjacency
                self._evict_if_needed_locked()
            adjacency.add(tgt)
            # Also touch the target node so it counts toward the LRU
            # discipline even when it has no outgoing edges.
            if tgt not in self._nodes:
                self._nodes[tgt] = set()
                self._evict_if_needed_locked()
            else:
                self._nodes.move_to_end(tgt)
            self._nodes.move_to_end(src)

    def neighbors(self, source: str) -> frozenset[str]:
        with self._lock:
            adjacency = self._nodes.get(source)
            return frozenset(adjacency) if adjacency else frozenset()

    def remove_node(self, node: str) -> None:
        with self._lock:
            self._nodes.pop(node, None)
            for adjacency in self._nodes.values():
                adjacency.discard(node)

    def __contains__(self, node: str) -> bool:
        with self._lock:
            return node in self._nodes

    def __len__(self) -> int:
        with self._lock:
            return len(self._nodes)

    def edge_count(self) -> int:
        with self._lock:
            return sum(len(adj) for adj in self._nodes.values())

    def stats(self) -> TopologyStats:
        with self._lock:
            return TopologyStats(
                node_count=len(self._nodes),
                edge_count=sum(len(adj) for adj in self._nodes.values()),
                capacity=self._capacity,
                evictions=self._evictions,
            )

    def clear(self) -> None:
        with self._lock:
            self._nodes.clear()
            self._evictions = 0

    def _evict_if_needed_locked(self) -> None:
        while len(self._nodes) > self._capacity:
            evicted, _ = self._nodes.popitem(last=False)
            self._evictions += 1
            # Strip references from the remaining adjacencies so the
            # evicted id can be garbage-collected.
            for adjacency in self._nodes.values():
                adjacency.discard(evicted)
            metrics = get_memory_metrics()
            metrics.record_topology_eviction()
            metrics.set_topology_size(len(self._nodes))
            record_memory_trace("topology-evicted", evicted)
