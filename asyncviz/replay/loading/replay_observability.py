"""Process-wide replay-loader counters.

Mirrors the structure of :mod:`asyncviz.replay.format.ndjson_observability`
but tracks loader-layer concerns (chunks scanned, seeks performed,
snapshot loads, malformed frames isolated, integrity failures).
Single singleton, atomic via one lock, reset for tests."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReplayLoaderMetricsSnapshot:
    """Immutable diagnostics view of the loader metrics."""

    sessions_opened: int = 0
    sessions_closed: int = 0
    frames_loaded: int = 0
    chunks_scanned: int = 0
    chunks_skipped: int = 0
    seeks_performed: int = 0
    seek_chunk_scans: int = 0
    snapshots_loaded: int = 0
    malformed_frames: int = 0
    integrity_failures: int = 0
    sequence_violations: int = 0
    state_reconstructions: int = 0
    filter_drops: int = 0
    window_drops: int = 0


class _LoaderMetrics:
    """Atomic counter set behind one lock."""

    __slots__ = (
        "_chunks_scanned",
        "_chunks_skipped",
        "_filter_drops",
        "_frames_loaded",
        "_integrity_failures",
        "_lock",
        "_malformed_frames",
        "_seek_chunk_scans",
        "_seeks_performed",
        "_sequence_violations",
        "_sessions_closed",
        "_sessions_opened",
        "_snapshots_loaded",
        "_state_reconstructions",
        "_window_drops",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self._sessions_opened = 0
        self._sessions_closed = 0
        self._frames_loaded = 0
        self._chunks_scanned = 0
        self._chunks_skipped = 0
        self._seeks_performed = 0
        self._seek_chunk_scans = 0
        self._snapshots_loaded = 0
        self._malformed_frames = 0
        self._integrity_failures = 0
        self._sequence_violations = 0
        self._state_reconstructions = 0
        self._filter_drops = 0
        self._window_drops = 0

    # ── mutators ──────────────────────────────────────────────────

    def record_session_opened(self) -> None:
        with self._lock:
            self._sessions_opened += 1

    def record_session_closed(self) -> None:
        with self._lock:
            self._sessions_closed += 1

    def record_frame_loaded(self) -> None:
        with self._lock:
            self._frames_loaded += 1

    def record_chunk_scanned(self) -> None:
        with self._lock:
            self._chunks_scanned += 1

    def record_chunk_skipped(self) -> None:
        with self._lock:
            self._chunks_skipped += 1

    def record_seek(self, *, chunks_scanned: int) -> None:
        with self._lock:
            self._seeks_performed += 1
            self._seek_chunk_scans += max(0, chunks_scanned)

    def record_snapshot_loaded(self) -> None:
        with self._lock:
            self._snapshots_loaded += 1

    def record_malformed_frame(self) -> None:
        with self._lock:
            self._malformed_frames += 1

    def record_integrity_failure(self) -> None:
        with self._lock:
            self._integrity_failures += 1

    def record_sequence_violation(self) -> None:
        with self._lock:
            self._sequence_violations += 1

    def record_state_reconstruction(self) -> None:
        with self._lock:
            self._state_reconstructions += 1

    def record_filter_drop(self) -> None:
        with self._lock:
            self._filter_drops += 1

    def record_window_drop(self) -> None:
        with self._lock:
            self._window_drops += 1

    def snapshot(self) -> ReplayLoaderMetricsSnapshot:
        with self._lock:
            return ReplayLoaderMetricsSnapshot(
                sessions_opened=self._sessions_opened,
                sessions_closed=self._sessions_closed,
                frames_loaded=self._frames_loaded,
                chunks_scanned=self._chunks_scanned,
                chunks_skipped=self._chunks_skipped,
                seeks_performed=self._seeks_performed,
                seek_chunk_scans=self._seek_chunk_scans,
                snapshots_loaded=self._snapshots_loaded,
                malformed_frames=self._malformed_frames,
                integrity_failures=self._integrity_failures,
                sequence_violations=self._sequence_violations,
                state_reconstructions=self._state_reconstructions,
                filter_drops=self._filter_drops,
                window_drops=self._window_drops,
            )

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()


_METRICS: _LoaderMetrics | None = None
_METRICS_LOCK = threading.Lock()


def get_loader_metrics() -> _LoaderMetrics:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = _LoaderMetrics()
    return _METRICS


def get_loader_metrics_snapshot() -> ReplayLoaderMetricsSnapshot:
    return get_loader_metrics().snapshot()


def reset_loader_metrics() -> None:
    if _METRICS is not None:
        _METRICS.reset()
