"""Streaming subscription types for :class:`TimelineSegmentEngine`.

Listeners receive a :class:`TimelineDelta` on every successful state
mutation — segment opened, segment closed, task finalized. The
websocket streaming engine forwards each delta as a typed envelope so
the frontend timeline can update incrementally without re-fetching the
full snapshot.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from asyncviz.runtime.timeline.models import ActiveTimelineSegment, TimelineSegment


class TimelineDeltaKind(StrEnum):
    """What just happened to the timeline."""

    SEGMENT_OPENED = "segment_opened"
    SEGMENT_CLOSED = "segment_closed"
    SPAN_FINALIZED = "span_finalized"


@dataclass(frozen=True, slots=True)
class TimelineDelta:
    """One incremental timeline update.

    ``segment`` is populated on ``SEGMENT_CLOSED`` (the finalized one).
    ``open_segment`` is populated on ``SEGMENT_OPENED`` (the newly-open one).
    ``terminal_state`` is populated on ``SPAN_FINALIZED``.

    ``sequence`` is the state-store sequence that triggered the change;
    enables ordering against runtime_event deltas. ``monotonic_ns`` is the
    canonical event timestamp.
    """

    kind: TimelineDeltaKind
    task_id: str
    sequence: int | None
    monotonic_ns: int
    wall_seconds: float
    segment: TimelineSegment | None = None
    open_segment: ActiveTimelineSegment | None = None
    terminal_state: str | None = None
    closed_a_segment: bool = False


TimelineListener = Callable[[TimelineDelta], None]


@dataclass(slots=True)
class TimelineSubscription:
    """Handle returned by :meth:`TimelineSubscriptionRegistry.add`."""

    id: int
    listener: TimelineListener

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TimelineSubscription) and other.id == self.id


class TimelineSubscriptionRegistry:
    """Tiny synchronous fan-out for :class:`TimelineDelta` listeners."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = 0
        self._listeners: dict[int, TimelineSubscription] = {}

    def add(self, listener: TimelineListener) -> TimelineSubscription:
        with self._lock:
            self._next_id += 1
            sub = TimelineSubscription(id=self._next_id, listener=listener)
            self._listeners[sub.id] = sub
        return sub

    def remove(self, subscription_or_id: TimelineSubscription | int) -> bool:
        sub_id = (
            subscription_or_id.id
            if isinstance(subscription_or_id, TimelineSubscription)
            else subscription_or_id
        )
        with self._lock:
            return self._listeners.pop(sub_id, None) is not None

    def listeners(self) -> list[TimelineSubscription]:
        with self._lock:
            return list(self._listeners.values())

    def count(self) -> int:
        with self._lock:
            return len(self._listeners)

    def clear(self) -> None:
        with self._lock:
            self._listeners.clear()
