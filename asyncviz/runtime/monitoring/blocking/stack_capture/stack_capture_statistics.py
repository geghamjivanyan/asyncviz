"""Lifetime stats over captured stacks.

Distinct from :class:`StackCaptureMetrics` (engine self-counters) — this
module tracks aggregates over the *content* the engine produced:
top-frame frequencies, captures-per-window, captures-per-severity, etc.

Useful for the dashboard's "what's blocking us most?" panel without
forcing every consumer to scan the replay log.
"""

from __future__ import annotations

import threading
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_frames import (
    CapturedStack,
)


@dataclass(frozen=True, slots=True)
class TopFrameStat:
    """One entry in the "top-frame" leaderboard."""

    function: str
    module: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "function": self.function,
            "module": self.module,
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class StackCaptureStatisticsSnapshot:
    captures_total: int
    captures_by_severity: dict[str, int]
    captures_by_trigger: dict[str, int]
    captures_per_window: dict[str, int]
    top_top_frames: tuple[TopFrameStat, ...]
    last_capture_id: int
    last_capture_monotonic_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "captures_total": self.captures_total,
            "captures_by_severity": dict(self.captures_by_severity),
            "captures_by_trigger": dict(self.captures_by_trigger),
            "captures_per_window": dict(self.captures_per_window),
            "top_top_frames": [t.to_dict() for t in self.top_top_frames],
            "last_capture_id": self.last_capture_id,
            "last_capture_monotonic_ns": self.last_capture_monotonic_ns,
        }


class StackCaptureStatistics:
    """Tracks lifetime aggregates over emitted captures.

    The recent-capture ring lets the API expose the last N capture
    payloads without keeping every payload in memory forever.
    """

    DEFAULT_RECENT_CAPACITY: int = 32
    DEFAULT_TOP_FRAME_LIMIT: int = 10

    __slots__ = (
        "_captures_by_severity",
        "_captures_by_trigger",
        "_captures_per_window",
        "_captures_total",
        "_last_capture_id",
        "_last_capture_monotonic_ns",
        "_lock",
        "_recent",
        "_recent_capacity",
        "_top_frame_counter",
        "_top_frame_limit",
    )

    def __init__(
        self,
        *,
        recent_capacity: int = DEFAULT_RECENT_CAPACITY,
        top_frame_limit: int = DEFAULT_TOP_FRAME_LIMIT,
    ) -> None:
        if recent_capacity <= 0:
            raise ValueError(f"recent_capacity must be > 0 (got {recent_capacity})")
        if top_frame_limit <= 0:
            raise ValueError(f"top_frame_limit must be > 0 (got {top_frame_limit})")
        self._lock = threading.Lock()
        self._captures_total = 0
        self._captures_by_severity: Counter[str] = Counter()
        self._captures_by_trigger: Counter[str] = Counter()
        self._captures_per_window: Counter[str] = Counter()
        self._top_frame_counter: Counter[tuple[str, str]] = Counter()
        self._top_frame_limit = top_frame_limit
        self._recent_capacity = recent_capacity
        self._recent: deque[CapturedStack] = deque(maxlen=recent_capacity)
        self._last_capture_id = 0
        self._last_capture_monotonic_ns = 0

    @property
    def recent_capacity(self) -> int:
        return self._recent_capacity

    def reset(self) -> None:
        with self._lock:
            self._captures_total = 0
            self._captures_by_severity.clear()
            self._captures_by_trigger.clear()
            self._captures_per_window.clear()
            self._top_frame_counter.clear()
            self._recent.clear()
            self._last_capture_id = 0
            self._last_capture_monotonic_ns = 0

    def observe(self, stack: CapturedStack) -> None:
        with self._lock:
            self._captures_total += 1
            self._captures_by_severity[stack.severity] += 1
            self._captures_by_trigger[stack.trigger] += 1
            if stack.window_id is not None:
                self._captures_per_window[stack.window_id] += 1
            if stack.frames:
                top = stack.frames[0]
                self._top_frame_counter[(top.function, top.module)] += 1
            self._recent.append(stack)
            self._last_capture_id = stack.capture_id
            self._last_capture_monotonic_ns = stack.monotonic_ns

    def recent(self) -> tuple[CapturedStack, ...]:
        with self._lock:
            return tuple(self._recent)

    def snapshot(self) -> StackCaptureStatisticsSnapshot:
        with self._lock:
            top = self._top_frame_counter.most_common(self._top_frame_limit)
            return StackCaptureStatisticsSnapshot(
                captures_total=self._captures_total,
                captures_by_severity=dict(self._captures_by_severity),
                captures_by_trigger=dict(self._captures_by_trigger),
                captures_per_window=dict(self._captures_per_window),
                top_top_frames=tuple(
                    TopFrameStat(function=k[0], module=k[1], count=v) for k, v in top
                ),
                last_capture_id=self._last_capture_id,
                last_capture_monotonic_ns=self._last_capture_monotonic_ns,
            )
