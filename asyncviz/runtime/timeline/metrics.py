from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimelineMetricsSnapshot:
    """Immutable view of :class:`TimelineMetrics`.

    All counters are monotonically increasing for the lifetime of the engine
    instance. ``active_segments`` is a gauge.
    """

    transitions_applied: int
    transitions_rejected: int
    segments_opened: int
    segments_closed: int
    segments_by_type: dict[str, int]
    invalid_transitions: int
    active_segments: int
    finalized_spans: int
    rebuilds_completed: int


class TimelineMetrics:
    """Thread-safe counters for the timeline engine."""

    __slots__ = (
        "_active_segments",
        "_finalized_spans",
        "_invalid_transitions",
        "_lock",
        "_rebuilds_completed",
        "_segments_by_type",
        "_segments_closed",
        "_segments_opened",
        "_transitions_applied",
        "_transitions_rejected",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._transitions_applied = 0
        self._transitions_rejected = 0
        self._segments_opened = 0
        self._segments_closed = 0
        self._segments_by_type: dict[str, int] = defaultdict(int)
        self._invalid_transitions = 0
        self._active_segments = 0
        self._finalized_spans = 0
        self._rebuilds_completed = 0

    def record_applied(self) -> None:
        with self._lock:
            self._transitions_applied += 1

    def record_rejected(self, *, invalid: bool = False) -> None:
        with self._lock:
            self._transitions_rejected += 1
            if invalid:
                self._invalid_transitions += 1

    def record_segment_opened(self, segment_type: str) -> None:
        with self._lock:
            self._segments_opened += 1
            self._segments_by_type[segment_type] += 1
            self._active_segments += 1

    def record_segment_closed(self) -> None:
        with self._lock:
            self._segments_closed += 1
            if self._active_segments > 0:
                self._active_segments -= 1

    def record_finalized_span(self) -> None:
        with self._lock:
            self._finalized_spans += 1

    def record_rebuild(self) -> None:
        with self._lock:
            self._rebuilds_completed += 1

    def reset(self) -> None:
        with self._lock:
            self._transitions_applied = 0
            self._transitions_rejected = 0
            self._segments_opened = 0
            self._segments_closed = 0
            self._segments_by_type.clear()
            self._invalid_transitions = 0
            self._active_segments = 0
            self._finalized_spans = 0
            # ``rebuilds_completed`` survives reset — it's a lifetime counter.

    def snapshot(self) -> TimelineMetricsSnapshot:
        with self._lock:
            return TimelineMetricsSnapshot(
                transitions_applied=self._transitions_applied,
                transitions_rejected=self._transitions_rejected,
                segments_opened=self._segments_opened,
                segments_closed=self._segments_closed,
                segments_by_type=dict(self._segments_by_type),
                invalid_transitions=self._invalid_transitions,
                active_segments=self._active_segments,
                finalized_spans=self._finalized_spans,
                rebuilds_completed=self._rebuilds_completed,
            )
