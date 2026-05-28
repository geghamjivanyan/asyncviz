"""Self-observability counters for :class:`SnapshotService`."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SnapshotMetricsSnapshot:
    """Immutable view of :class:`SnapshotMetrics`."""

    snapshots_generated: int
    full_snapshots: int
    filtered_snapshots: int
    total_generation_ns: int
    max_generation_ns: int
    last_generation_ns: int
    last_payload_bytes: int
    max_payload_bytes: int
    sources_skipped: int
    consistency_errors: int

    @property
    def average_generation_ns(self) -> float:
        if self.snapshots_generated == 0:
            return 0.0
        return self.total_generation_ns / self.snapshots_generated


class SnapshotMetrics:
    """Thread-safe counters for the snapshot service.

    Surfaced via :class:`SnapshotMetricsSnapshot` and the
    ``/api/runtime/snapshot/metrics`` debug endpoint. Captures both shape-
    independent counters (snapshots generated, sources skipped) and the
    last-known generation timings + payload sizes so operators can spot
    slow snapshots before they become user-visible.
    """

    __slots__ = (
        "_consistency_errors",
        "_filtered_snapshots",
        "_full_snapshots",
        "_last_generation_ns",
        "_last_payload_bytes",
        "_lock",
        "_max_generation_ns",
        "_max_payload_bytes",
        "_snapshots_generated",
        "_sources_skipped",
        "_total_generation_ns",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshots_generated = 0
        self._full_snapshots = 0
        self._filtered_snapshots = 0
        self._total_generation_ns = 0
        self._max_generation_ns = 0
        self._last_generation_ns = 0
        self._last_payload_bytes = 0
        self._max_payload_bytes = 0
        self._sources_skipped = 0
        self._consistency_errors = 0

    def record_generation(
        self,
        *,
        duration_ns: int,
        payload_bytes: int,
        filtered: bool,
        sources_skipped: int,
    ) -> None:
        with self._lock:
            self._snapshots_generated += 1
            if filtered:
                self._filtered_snapshots += 1
            else:
                self._full_snapshots += 1
            self._total_generation_ns += duration_ns
            if duration_ns > self._max_generation_ns:
                self._max_generation_ns = duration_ns
            self._last_generation_ns = duration_ns
            self._last_payload_bytes = payload_bytes
            if payload_bytes > self._max_payload_bytes:
                self._max_payload_bytes = payload_bytes
            self._sources_skipped += sources_skipped

    def record_consistency_error(self) -> None:
        with self._lock:
            self._consistency_errors += 1

    def reset(self) -> None:
        with self._lock:
            self._snapshots_generated = 0
            self._full_snapshots = 0
            self._filtered_snapshots = 0
            self._total_generation_ns = 0
            self._max_generation_ns = 0
            self._last_generation_ns = 0
            self._last_payload_bytes = 0
            self._max_payload_bytes = 0
            self._sources_skipped = 0
            self._consistency_errors = 0

    def snapshot(self) -> SnapshotMetricsSnapshot:
        with self._lock:
            return SnapshotMetricsSnapshot(
                snapshots_generated=self._snapshots_generated,
                full_snapshots=self._full_snapshots,
                filtered_snapshots=self._filtered_snapshots,
                total_generation_ns=self._total_generation_ns,
                max_generation_ns=self._max_generation_ns,
                last_generation_ns=self._last_generation_ns,
                last_payload_bytes=self._last_payload_bytes,
                max_payload_bytes=self._max_payload_bytes,
                sources_skipped=self._sources_skipped,
                consistency_errors=self._consistency_errors,
            )
