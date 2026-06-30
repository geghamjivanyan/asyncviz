"""Process-wide seek metrics."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SeekMetricsSnapshot:
    seeks_requested: int = 0
    seeks_completed: int = 0
    seeks_cancelled: int = 0
    seeks_failed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    checkpoint_hits: int = 0
    snapshot_hits: int = 0
    full_reconstructions: int = 0
    cumulative_latency_ns: int = 0
    max_latency_ns: int = 0
    cumulative_frames_replayed: int = 0
    coordination_drops: int = 0
    integrity_violations: int = 0
    budget_exceeded: int = 0


class _SeekMetrics:
    __slots__ = (
        "_budget_exceeded",
        "_cache_hits",
        "_cache_misses",
        "_checkpoint_hits",
        "_coordination_drops",
        "_cumulative_frames_replayed",
        "_cumulative_latency_ns",
        "_full_reconstructions",
        "_integrity_violations",
        "_lock",
        "_max_latency_ns",
        "_seeks_cancelled",
        "_seeks_completed",
        "_seeks_failed",
        "_seeks_requested",
        "_snapshot_hits",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self._seeks_requested = 0
        self._seeks_completed = 0
        self._seeks_cancelled = 0
        self._seeks_failed = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._checkpoint_hits = 0
        self._snapshot_hits = 0
        self._full_reconstructions = 0
        self._cumulative_latency_ns = 0
        self._max_latency_ns = 0
        self._cumulative_frames_replayed = 0
        self._coordination_drops = 0
        self._integrity_violations = 0
        self._budget_exceeded = 0

    def record_requested(self) -> None:
        with self._lock:
            self._seeks_requested += 1

    def record_completed(
        self,
        *,
        latency_ns: int,
        frames_replayed: int,
    ) -> None:
        with self._lock:
            self._seeks_completed += 1
            self._cumulative_latency_ns += max(0, latency_ns)
            if latency_ns > self._max_latency_ns:
                self._max_latency_ns = latency_ns
            self._cumulative_frames_replayed += max(0, frames_replayed)

    def record_cancelled(self) -> None:
        with self._lock:
            self._seeks_cancelled += 1

    def record_failed(self) -> None:
        with self._lock:
            self._seeks_failed += 1

    def record_cache_hit(self) -> None:
        with self._lock:
            self._cache_hits += 1

    def record_cache_miss(self) -> None:
        with self._lock:
            self._cache_misses += 1

    def record_checkpoint_hit(self) -> None:
        with self._lock:
            self._checkpoint_hits += 1

    def record_snapshot_hit(self) -> None:
        with self._lock:
            self._snapshot_hits += 1

    def record_full_reconstruction(self) -> None:
        with self._lock:
            self._full_reconstructions += 1

    def record_coordination_drop(self) -> None:
        with self._lock:
            self._coordination_drops += 1

    def record_integrity_violation(self) -> None:
        with self._lock:
            self._integrity_violations += 1

    def record_budget_exceeded(self) -> None:
        with self._lock:
            self._budget_exceeded += 1

    def snapshot(self) -> SeekMetricsSnapshot:
        with self._lock:
            return SeekMetricsSnapshot(
                seeks_requested=self._seeks_requested,
                seeks_completed=self._seeks_completed,
                seeks_cancelled=self._seeks_cancelled,
                seeks_failed=self._seeks_failed,
                cache_hits=self._cache_hits,
                cache_misses=self._cache_misses,
                checkpoint_hits=self._checkpoint_hits,
                snapshot_hits=self._snapshot_hits,
                full_reconstructions=self._full_reconstructions,
                cumulative_latency_ns=self._cumulative_latency_ns,
                max_latency_ns=self._max_latency_ns,
                cumulative_frames_replayed=self._cumulative_frames_replayed,
                coordination_drops=self._coordination_drops,
                integrity_violations=self._integrity_violations,
                budget_exceeded=self._budget_exceeded,
            )

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()


_METRICS: _SeekMetrics | None = None
_METRICS_LOCK = threading.Lock()


def get_seek_metrics() -> _SeekMetrics:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = _SeekMetrics()
    return _METRICS


def get_seek_metrics_snapshot() -> SeekMetricsSnapshot:
    return get_seek_metrics().snapshot()


def reset_seek_metrics() -> None:
    if _METRICS is not None:
        _METRICS.reset()
