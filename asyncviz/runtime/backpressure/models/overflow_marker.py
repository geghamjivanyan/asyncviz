"""Overflow marker — replay-safe gap reporting.

Mirrors :class:`SamplingMarker` but specifically for events that
were *dropped by the backpressure controller* rather than by the
sampler. Replay reconstruction tools render explicit gaps where
overflow happened so the operator can see "we shed N events at
position P".
"""

from __future__ import annotations

from dataclasses import dataclass

OVERFLOW_MARKER_EVENT_TYPE = "asyncviz.backpressure.overflow"
"""Reserved synthetic event type."""


@dataclass(frozen=True, slots=True)
class OverflowMarker:
    """One overflow-window summary."""

    first_sequence: int
    last_sequence: int
    dropped: int
    subsystem: str
    """``bus`` / ``websocket`` / ``recorder`` / ``reducer`` — names
    the producer of the overflow."""

    drop_policy: str
    """The active drop policy when the overflow occurred."""

    state_at_overflow: str
    """``normal``/``elevated``/``overload``/``emergency`` — the
    controller's state at the moment of overflow."""

    @property
    def span(self) -> int:
        return max(0, self.last_sequence - self.first_sequence + 1)

    def to_payload(self) -> dict:
        return {
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "dropped": self.dropped,
            "subsystem": self.subsystem,
            "drop_policy": self.drop_policy,
            "state_at_overflow": self.state_at_overflow,
        }
