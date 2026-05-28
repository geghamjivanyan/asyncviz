"""Process-wide memory-optimizer metrics."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemoryMetricsSnapshot:
    interned_strings: int = 0
    interner_hits: int = 0
    interner_misses: int = 0
    interner_bypassed: int = 0
    compact_events_built: int = 0
    compact_frames_built: int = 0
    pool_acquires: int = 0
    pool_releases: int = 0
    pool_hits: int = 0
    pool_misses: int = 0
    pool_double_releases: int = 0
    dedup_hits: int = 0
    dedup_misses: int = 0
    reducer_evictions: int = 0
    topology_nodes: int = 0
    topology_evictions: int = 0
    websocket_buffer_acquires: int = 0
    websocket_buffer_hits: int = 0
    replay_cache_hits: int = 0
    replay_cache_misses: int = 0
    replay_cache_evictions: int = 0
    bytes_avoided_estimate: int = 0


class _MemoryMetrics:
    __slots__ = (
        "_bytes_avoided_estimate",
        "_compact_events_built",
        "_compact_frames_built",
        "_dedup_hits",
        "_dedup_misses",
        "_interned_strings",
        "_interner_bypassed",
        "_interner_hits",
        "_interner_misses",
        "_lock",
        "_pool_acquires",
        "_pool_double_releases",
        "_pool_hits",
        "_pool_misses",
        "_pool_releases",
        "_reducer_evictions",
        "_replay_cache_evictions",
        "_replay_cache_hits",
        "_replay_cache_misses",
        "_topology_evictions",
        "_topology_nodes",
        "_websocket_buffer_acquires",
        "_websocket_buffer_hits",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self._interned_strings = 0
        self._interner_hits = 0
        self._interner_misses = 0
        self._interner_bypassed = 0
        self._compact_events_built = 0
        self._compact_frames_built = 0
        self._pool_acquires = 0
        self._pool_releases = 0
        self._pool_hits = 0
        self._pool_misses = 0
        self._pool_double_releases = 0
        self._dedup_hits = 0
        self._dedup_misses = 0
        self._reducer_evictions = 0
        self._topology_nodes = 0
        self._topology_evictions = 0
        self._websocket_buffer_acquires = 0
        self._websocket_buffer_hits = 0
        self._replay_cache_hits = 0
        self._replay_cache_misses = 0
        self._replay_cache_evictions = 0
        self._bytes_avoided_estimate = 0

    # ── mutators ──────────────────────────────────────────────────

    def record_interner_stats(self, size: int, hits: int, misses: int, bypassed: int) -> None:
        with self._lock:
            self._interned_strings = size
            self._interner_hits = hits
            self._interner_misses = misses
            self._interner_bypassed = bypassed

    def record_compact_event(self) -> None:
        with self._lock:
            self._compact_events_built += 1

    def record_compact_frame(self) -> None:
        with self._lock:
            self._compact_frames_built += 1

    def record_pool_stats(
        self,
        *,
        acquires: int,
        releases: int,
        hits: int,
        misses: int,
        double_releases: int,
    ) -> None:
        with self._lock:
            self._pool_acquires += acquires
            self._pool_releases += releases
            self._pool_hits += hits
            self._pool_misses += misses
            self._pool_double_releases += double_releases

    def record_dedup_hit(self) -> None:
        with self._lock:
            self._dedup_hits += 1

    def record_dedup_miss(self) -> None:
        with self._lock:
            self._dedup_misses += 1

    def record_reducer_eviction(self) -> None:
        with self._lock:
            self._reducer_evictions += 1

    def set_topology_size(self, size: int) -> None:
        with self._lock:
            self._topology_nodes = size

    def record_topology_eviction(self) -> None:
        with self._lock:
            self._topology_evictions += 1

    def record_websocket_acquire(self, *, hit: bool) -> None:
        with self._lock:
            self._websocket_buffer_acquires += 1
            if hit:
                self._websocket_buffer_hits += 1

    def record_replay_cache_hit(self) -> None:
        with self._lock:
            self._replay_cache_hits += 1

    def record_replay_cache_miss(self) -> None:
        with self._lock:
            self._replay_cache_misses += 1

    def record_replay_cache_eviction(self) -> None:
        with self._lock:
            self._replay_cache_evictions += 1

    def add_bytes_avoided(self, bytes_count: int) -> None:
        with self._lock:
            self._bytes_avoided_estimate += max(0, bytes_count)

    def snapshot(self) -> MemoryMetricsSnapshot:
        with self._lock:
            return MemoryMetricsSnapshot(
                interned_strings=self._interned_strings,
                interner_hits=self._interner_hits,
                interner_misses=self._interner_misses,
                interner_bypassed=self._interner_bypassed,
                compact_events_built=self._compact_events_built,
                compact_frames_built=self._compact_frames_built,
                pool_acquires=self._pool_acquires,
                pool_releases=self._pool_releases,
                pool_hits=self._pool_hits,
                pool_misses=self._pool_misses,
                pool_double_releases=self._pool_double_releases,
                dedup_hits=self._dedup_hits,
                dedup_misses=self._dedup_misses,
                reducer_evictions=self._reducer_evictions,
                topology_nodes=self._topology_nodes,
                topology_evictions=self._topology_evictions,
                websocket_buffer_acquires=self._websocket_buffer_acquires,
                websocket_buffer_hits=self._websocket_buffer_hits,
                replay_cache_hits=self._replay_cache_hits,
                replay_cache_misses=self._replay_cache_misses,
                replay_cache_evictions=self._replay_cache_evictions,
                bytes_avoided_estimate=self._bytes_avoided_estimate,
            )

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()


_METRICS: _MemoryMetrics | None = None
_METRICS_LOCK = threading.Lock()


def get_memory_metrics() -> _MemoryMetrics:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = _MemoryMetrics()
    return _METRICS


def get_memory_metrics_snapshot() -> MemoryMetricsSnapshot:
    return get_memory_metrics().snapshot()


def reset_memory_metrics() -> None:
    if _METRICS is not None:
        _METRICS.reset()
