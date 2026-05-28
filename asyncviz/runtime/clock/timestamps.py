from __future__ import annotations

import uuid
from dataclasses import dataclass

from asyncviz.runtime.clock.conversions import (
    NS_PER_SECOND,
    ns_to_ms,
    ns_to_seconds,
    seconds_to_ns,
    wall_seconds_to_iso,
)


@dataclass(frozen=True, slots=True)
class Duration:
    """A non-negative time interval, stored as nanoseconds.

    The runtime's canonical duration type. Always compute durations from
    monotonic deltas — never from wall-clock subtraction — to remain immune
    to system-clock adjustments.
    """

    nanoseconds: int

    def __post_init__(self) -> None:
        if self.nanoseconds < 0:
            # Clamp rather than raise: instrumentation produced this value on
            # a hot path and we'd rather show ``0`` than crash a done-callback.
            object.__setattr__(self, "nanoseconds", 0)

    @property
    def seconds(self) -> float:
        return ns_to_seconds(self.nanoseconds)

    @property
    def milliseconds(self) -> float:
        return ns_to_ms(self.nanoseconds)

    @classmethod
    def from_seconds(cls, seconds: float) -> Duration:
        return cls(nanoseconds=max(0, seconds_to_ns(seconds)))

    @classmethod
    def between(cls, start_ns: int, end_ns: int) -> Duration:
        """Compute a Duration from two ``monotonic_ns`` readings.

        Always non-negative; if ``end_ns < start_ns`` (extremely rare clock
        anomaly), returns zero rather than a negative interval.
        """
        return cls(nanoseconds=max(0, end_ns - start_ns))


@dataclass(frozen=True, slots=True)
class MonotonicTimestamp:
    """A single monotonic clock reading.

    Cheaper than :class:`RuntimeTimestamp` — no wall-clock derivation, no
    sequence allocation. Useful when a producer only needs ordering.
    """

    monotonic_ns: int

    @property
    def monotonic_seconds(self) -> float:
        return ns_to_seconds(self.monotonic_ns)


@dataclass(frozen=True, slots=True)
class RuntimeTimestamp:
    """The canonical "now" produced by :class:`RuntimeClock`.

    Carries every view a downstream consumer might want — wall-clock,
    monotonic seconds, raw monotonic nanoseconds, plus the issuing clock's
    ``runtime_id``. Replay-safe because all fields are primitives.
    """

    wall_seconds: float
    monotonic_ns: int
    runtime_id: uuid.UUID

    @property
    def monotonic_seconds(self) -> float:
        return ns_to_seconds(self.monotonic_ns)

    @property
    def wall_iso(self) -> str:
        return wall_seconds_to_iso(self.wall_seconds)

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-safe dict (used by debug endpoints and tests)."""
        return {
            "wall_seconds": self.wall_seconds,
            "wall_iso": self.wall_iso,
            "monotonic_seconds": self.monotonic_seconds,
            "monotonic_ns": self.monotonic_ns,
            "runtime_id": str(self.runtime_id),
        }


@dataclass(frozen=True, slots=True)
class EventTimestamp:
    """Timestamp + sequence pair stamped on a runtime event at the source.

    Constructed by :meth:`RuntimeClock.stamp_event`. Carries the ordering
    primitive (``sequence``) plus the timestamp triple needed for display.
    """

    sequence: int
    wall_seconds: float
    monotonic_ns: int
    runtime_id: uuid.UUID

    @property
    def monotonic_seconds(self) -> float:
        return self.monotonic_ns / NS_PER_SECOND

    @property
    def wall_iso(self) -> str:
        return wall_seconds_to_iso(self.wall_seconds)
