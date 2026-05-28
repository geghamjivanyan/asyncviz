"""Per-task segment buffer with bounded growth.

Active segments are kept on :class:`TaskTimelineState`; finalized segments
live in the buffer here. For deeply ping-ponging tasks (RUN ↔ WAIT) the
segment count can grow without bound, so we cap each task at a configurable
limit and drop the oldest finalized segment when exceeded.

The cap is generous (default 4096) — that's ~2000 run/wait flips per task,
two orders of magnitude beyond any practical workload before the buffer
rolls.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Iterable

from asyncviz.runtime.timeline.models import TimelineSegment

DEFAULT_SEGMENT_LIMIT: int = 4096


class SegmentBuffer:
    """Thread-safe per-task finalized-segment ring."""

    def __init__(self, *, per_task_limit: int = DEFAULT_SEGMENT_LIMIT) -> None:
        if per_task_limit < 1:
            raise ValueError("per_task_limit must be >= 1")
        self._lock = threading.RLock()
        self._limit = per_task_limit
        self._segments: dict[str, deque[TimelineSegment]] = {}
        self._evicted = 0

    @property
    def per_task_limit(self) -> int:
        return self._limit

    @property
    def total_evicted(self) -> int:
        with self._lock:
            return self._evicted

    def append(self, segment: TimelineSegment) -> None:
        with self._lock:
            bucket = self._segments.get(segment.task_id)
            if bucket is None:
                bucket = deque(maxlen=self._limit)
                self._segments[segment.task_id] = bucket
            if len(bucket) == self._limit:
                self._evicted += 1
            bucket.append(segment)

    def append_many(self, task_id: str, segments: Iterable[TimelineSegment]) -> None:
        for segment in segments:
            self.append(segment)

    def get(self, task_id: str) -> tuple[TimelineSegment, ...]:
        with self._lock:
            bucket = self._segments.get(task_id)
            return tuple(bucket) if bucket is not None else ()

    def discard(self, task_id: str) -> None:
        with self._lock:
            self._segments.pop(task_id, None)

    def clear(self) -> None:
        with self._lock:
            self._segments.clear()
            self._evicted = 0

    def task_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._segments.keys())

    def __contains__(self, task_id: object) -> bool:
        if not isinstance(task_id, str):
            return False
        with self._lock:
            return task_id in self._segments

    def __len__(self) -> int:
        with self._lock:
            return len(self._segments)

    def total_segments(self) -> int:
        with self._lock:
            return sum(len(bucket) for bucket in self._segments.values())
