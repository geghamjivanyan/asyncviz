"""Replay-aware sampling.

Buffers per-window drop counts + emits a :class:`SamplingMarker`
when the window closes. Replay reconstruction tools consume
markers to render explicit gaps in the timeline / overlay layers,
so a sampled recording is *visibly* sampled — no silent loss.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from asyncviz.runtime.sampling.models.sampling_decision import SamplingDecision
from asyncviz.runtime.sampling.models.sampling_marker import (
    SAMPLING_MARKER_EVENT_TYPE,
    SamplingMarker,
)
from asyncviz.runtime.sampling.models.sampling_priority import SamplingPriority


@dataclass(slots=True)
class _Window:
    """Internal — one drop window's accumulator."""

    first_sequence: int = 0
    last_sequence: int = 0
    retained: int = 0
    dropped: int = 0
    dropped_by_priority: dict[SamplingPriority, int] = field(
        default_factory=lambda: dict.fromkeys(SamplingPriority, 0),
    )

    def observe(self, decision: SamplingDecision) -> None:
        if self.first_sequence == 0:
            self.first_sequence = decision.sequence
        self.last_sequence = decision.sequence
        if decision.retain:
            self.retained += 1
        else:
            self.dropped += 1
            self.dropped_by_priority[decision.priority] = (
                self.dropped_by_priority.get(decision.priority, 0) + 1
            )

    def flush(self) -> SamplingMarker:
        marker = SamplingMarker(
            first_sequence=self.first_sequence,
            last_sequence=self.last_sequence,
            retained=self.retained,
            dropped=self.dropped,
            dropped_by_priority={
                p: c for p, c in self.dropped_by_priority.items() if c > 0
            },
            reason_summary=(
                f"dropped {self.dropped} retained {self.retained} "
                f"seq=[{self.first_sequence},{self.last_sequence}]"
            ),
        )
        self.first_sequence = 0
        self.last_sequence = 0
        self.retained = 0
        self.dropped = 0
        for key in self.dropped_by_priority:
            self.dropped_by_priority[key] = 0
        return marker


class ReplaySamplingBookkeeper:
    """Aggregates per-decision counts into :class:`SamplingMarker`s."""

    __slots__ = ("_lock", "_marker_count", "_window", "_window_size")

    def __init__(self, *, window_size: int = 256) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self._window_size = window_size
        self._window = _Window()
        self._lock = threading.Lock()
        self._marker_count = 0

    @property
    def window_size(self) -> int:
        return self._window_size

    @property
    def marker_count(self) -> int:
        with self._lock:
            return self._marker_count

    def observe(self, decision: SamplingDecision) -> SamplingMarker | None:
        """Record one decision. Returns a marker when the current
        window completes (i.e. ``window_size`` total events have
        been observed). Otherwise returns ``None``."""
        with self._lock:
            self._window.observe(decision)
            if self._window.retained + self._window.dropped < self._window_size:
                return None
            marker = self._window.flush()
            self._marker_count += 1
            return marker

    def flush(self) -> SamplingMarker | None:
        """Force-close the current window. Returns the marker if
        the window has any observations, ``None`` if it's empty."""
        with self._lock:
            if self._window.retained + self._window.dropped == 0:
                return None
            marker = self._window.flush()
            self._marker_count += 1
            return marker

    def reset(self) -> None:
        with self._lock:
            self._window = _Window()
            self._marker_count = 0


def marker_to_event_dict(
    marker: SamplingMarker,
    *,
    sequence: int,
    monotonic_ns: int,
) -> dict:
    """Build a JSON-safe event dict from a marker. The recorder
    embeds this into the recording stream as a special event with
    ``event_type == SAMPLING_MARKER_EVENT_TYPE``."""
    return {
        "event_type": SAMPLING_MARKER_EVENT_TYPE,
        "sequence": sequence,
        "monotonic_ns": monotonic_ns,
        "payload": marker.to_payload(),
    }
