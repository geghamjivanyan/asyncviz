"""Canonical event-memory optimizer façade.

Composes every memory-layer primitive into one cohesive API:

    optimizer = EventMemoryOptimizer()
    compact = optimizer.compact_event(runtime_event)
    compact_frame = optimizer.compact_replay_frame(replay_frame)
    canonical_str = optimizer.intern("asyncio.task.created")
    with optimizer.websocket_buffer() as buf:
        ...
    optimizer.add_topology_edge("a", "b")
    diag = optimizer.diagnostics()
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from asyncviz.replay.format import ReplayFrame
from asyncviz.runtime.events.models.base import RuntimeEvent
from asyncviz.runtime.memory.event_compaction import compact_dict, compact_event
from asyncviz.runtime.memory.event_deduplication import (
    DedupDecision,
    EventDeduplicator,
)
from asyncviz.runtime.memory.event_interning import StringInterner
from asyncviz.runtime.memory.event_pooling import ObjectPool, PoolToken
from asyncviz.runtime.memory.memory_configuration import (
    MemoryOptimizerConfig,
    default_config,
)
from asyncviz.runtime.memory.memory_diagnostics import (
    MemoryDiagnostics,
    build_memory_diagnostics,
)
from asyncviz.runtime.memory.memory_observability import get_memory_metrics
from asyncviz.runtime.memory.memory_thresholds import (
    MemoryThresholdMonitor,
)
from asyncviz.runtime.memory.models.compact_event import CompactEvent
from asyncviz.runtime.memory.models.compact_frame import CompactReplayFrame
from asyncviz.runtime.memory.replay_compaction import (
    ReplayFrameCache,
    compact_frame,
)
from asyncviz.runtime.memory.topology_memory import CompactTopology
from asyncviz.runtime.memory.websocket_memory import WebsocketBufferPool


class EventMemoryOptimizer:
    """Top-level memory-optimization façade."""

    __slots__ = (
        "_config",
        "_dedup",
        "_interner",
        "_pools",
        "_replay_cache",
        "_thresholds",
        "_topology",
        "_ws_buffers",
    )

    def __init__(self, config: MemoryOptimizerConfig | None = None) -> None:
        cfg = config or default_config()
        self._config = cfg
        self._interner = StringInterner(capacity=cfg.interner_capacity)
        self._dedup = EventDeduplicator(window_size=cfg.dedup_window)
        self._topology = CompactTopology(
            capacity=cfg.topology_node_capacity, interner=self._interner,
        )
        self._ws_buffers = WebsocketBufferPool(
            capacity_buffers=cfg.websocket_buffer_count,
            default_bytes=cfg.websocket_buffer_bytes,
        )
        self._replay_cache = ReplayFrameCache(
            capacity=cfg.replay_frame_cache_capacity,
        )
        self._thresholds = MemoryThresholdMonitor()
        self._pools: dict[str, ObjectPool] = {}  # type: ignore[type-arg]

    # ── accessors ─────────────────────────────────────────────────

    @property
    def config(self) -> MemoryOptimizerConfig:
        return self._config

    @property
    def interner(self) -> StringInterner:
        return self._interner

    @property
    def topology(self) -> CompactTopology:
        return self._topology

    @property
    def replay_cache(self) -> ReplayFrameCache:
        return self._replay_cache

    @property
    def websocket_buffers(self) -> WebsocketBufferPool:
        return self._ws_buffers

    @property
    def deduplicator(self) -> EventDeduplicator:
        return self._dedup

    @property
    def thresholds(self) -> MemoryThresholdMonitor:
        return self._thresholds

    # ── string interning ──────────────────────────────────────────

    def intern(self, value: str) -> str:
        if not self._config.interning_enabled:
            return value
        return self._interner.intern(value)

    # ── event compaction ──────────────────────────────────────────

    def compact_event(
        self,
        event: RuntimeEvent,
        *,
        intern_payload: bool = True,
    ) -> CompactEvent:
        return compact_event(
            event, interner=self._interner, intern_payload=intern_payload,
        )

    def compact_dict_event(
        self, data: dict[str, Any], *, intern_payload: bool = True,
    ) -> CompactEvent:
        return compact_dict(
            data, interner=self._interner, intern_payload=intern_payload,
        )

    # ── replay-frame compaction ───────────────────────────────────

    def compact_replay_frame(
        self,
        frame: ReplayFrame,
        *,
        intern_payload: bool = True,
        cache: bool = False,
    ) -> CompactReplayFrame:
        compact = compact_frame(
            frame, interner=self._interner, intern_payload=intern_payload,
        )
        if cache:
            self._replay_cache.put(compact)
        return compact

    # ── deduplication ─────────────────────────────────────────────

    def observe_event(self, event: CompactEvent) -> DedupDecision:
        if not self._config.dedup_enabled:
            return DedupDecision(duplicate=False, digest="")
        return self._dedup.observe(event)

    # ── pooling ───────────────────────────────────────────────────

    def register_pool(self, name: str, pool: ObjectPool) -> None:  # type: ignore[type-arg]
        self._pools[name] = pool

    def get_pool(self, name: str) -> ObjectPool | None:  # type: ignore[type-arg]
        return self._pools.get(name)

    def acquire_from_pool(self, name: str) -> PoolToken:  # type: ignore[type-arg]
        pool = self._pools.get(name)
        if pool is None:
            raise KeyError(f"no pool registered with name: {name!r}")
        return pool.acquire()

    @contextmanager
    def websocket_buffer(self, *, min_bytes: int = 0):  # type: ignore[no-untyped-def]
        buffer = self._ws_buffers.acquire(min_bytes=min_bytes)
        try:
            yield buffer
        finally:
            self._ws_buffers.release(buffer)

    # ── topology ──────────────────────────────────────────────────

    def add_topology_edge(self, source: str, target: str) -> None:
        self._topology.add_edge(source, target)
        get_memory_metrics().set_topology_size(len(self._topology))

    # ── diagnostics ───────────────────────────────────────────────

    def diagnostics(self, *, trace_limit: int = 32) -> MemoryDiagnostics:
        interner_stats = self._interner.stats()
        get_memory_metrics().record_interner_stats(
            size=interner_stats.size,
            hits=interner_stats.hits,
            misses=interner_stats.misses,
            bypassed=interner_stats.bypassed,
        )
        pool_stats = tuple(
            (name, pool.stats()) for name, pool in self._pools.items()
        )
        return build_memory_diagnostics(
            interner_stats=interner_stats,
            pools=pool_stats,
            topology_stats=self._topology.stats(),
            websocket_stats=self._ws_buffers.stats(),
            trace_limit=trace_limit,
        )

    # ── lifecycle ─────────────────────────────────────────────────

    def reset(self) -> None:
        """Wipe all caches + pools + dedup window. Used between
        recording sessions in tests."""
        self._interner.clear()
        self._dedup.reset()
        self._topology.clear()
        self._ws_buffers.clear()
        self._replay_cache.clear()
        for pool in self._pools.values():
            pool.clear()
        self._thresholds.reset()


_GLOBAL_OPTIMIZER: EventMemoryOptimizer | None = None


def get_global_optimizer() -> EventMemoryOptimizer:
    global _GLOBAL_OPTIMIZER
    if _GLOBAL_OPTIMIZER is None:
        _GLOBAL_OPTIMIZER = EventMemoryOptimizer()
    return _GLOBAL_OPTIMIZER


def reset_global_optimizer() -> None:
    global _GLOBAL_OPTIMIZER
    if _GLOBAL_OPTIMIZER is not None:
        _GLOBAL_OPTIMIZER.reset()
    _GLOBAL_OPTIMIZER = None
