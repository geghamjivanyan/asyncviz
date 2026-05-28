"""Replay + recorder backpressure adapter.

Bounded channel for the recorder's persistence path + a marker
emitter so dropped events get an explicit overflow marker in the
recording stream.

The recorder's default drop policy is ``block`` (it'd rather slow
the producer than lose events), but operators with a fast disk can
swap to ``drop-oldest``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.runtime.backpressure.backpressure_configuration import (
    BackpressureConfig,
    DropPolicy,
)
from asyncviz.runtime.backpressure.bounded_event_channel import (
    BoundedEventChannel,
    ChannelStats,
)
from asyncviz.runtime.backpressure.models.overflow_marker import (
    OVERFLOW_MARKER_EVENT_TYPE,
    OverflowMarker,
)
from asyncviz.runtime.backpressure.models.overload_state import OverloadState


@dataclass(slots=True)
class ReplayBackpressureStats:
    channel: ChannelStats
    markers_emitted: int
    last_marker_seq: int


class ReplayBackpressureAdapter:
    """Bounded recorder/replay inbox + overflow-marker bookkeeping."""

    __slots__ = (
        "_channel",
        "_config",
        "_first_drop_seq",
        "_last_drop_seq",
        "_last_marker_seq",
        "_lock",
        "_marker_window",
        "_markers_emitted",
        "_pending_drops",
    )

    def __init__(
        self,
        config: BackpressureConfig,
        *,
        policy: DropPolicy | None = None,
    ) -> None:
        self._config = config
        self._channel: BoundedEventChannel = BoundedEventChannel(
            "recorder",
            capacity=config.recorder_capacity,
            policy=policy or config.recorder_drop_policy,
        )
        self._marker_window = config.marker_summary_window
        self._pending_drops = 0
        self._first_drop_seq = 0
        self._last_drop_seq = 0
        self._markers_emitted = 0
        self._last_marker_seq = 0
        self._lock = threading.Lock()

    @property
    def channel(self) -> BoundedEventChannel:
        return self._channel

    @property
    def pressure_ratio(self) -> float:
        return self._channel.pressure_ratio

    def offer(self, event, *, priority: int = 0):  # type: ignore[no-untyped-def]
        return self._channel.offer(event, priority=priority)

    def take(self):  # type: ignore[no-untyped-def]
        return self._channel.take()

    def record_drop(
        self, *, sequence: int, state: OverloadState,
    ) -> OverflowMarker | None:
        """Record one dropped event. Returns a marker when the
        window has accumulated enough drops to warrant emission;
        ``None`` otherwise."""
        with self._lock:
            if self._pending_drops == 0:
                self._first_drop_seq = sequence
            self._last_drop_seq = sequence
            self._pending_drops += 1
            if self._pending_drops < self._marker_window:
                return None
            marker = OverflowMarker(
                first_sequence=self._first_drop_seq,
                last_sequence=self._last_drop_seq,
                dropped=self._pending_drops,
                subsystem="recorder",
                drop_policy=str(self._channel.policy),
                state_at_overflow=state.name.lower(),
            )
            self._pending_drops = 0
            self._first_drop_seq = 0
            self._last_drop_seq = 0
            self._markers_emitted += 1
            self._last_marker_seq = marker.last_sequence
            return marker

    def flush_pending_drops(
        self, *, state: OverloadState,
    ) -> OverflowMarker | None:
        with self._lock:
            if self._pending_drops == 0:
                return None
            marker = OverflowMarker(
                first_sequence=self._first_drop_seq,
                last_sequence=self._last_drop_seq,
                dropped=self._pending_drops,
                subsystem="recorder",
                drop_policy=str(self._channel.policy),
                state_at_overflow=state.name.lower(),
            )
            self._pending_drops = 0
            self._first_drop_seq = 0
            self._last_drop_seq = 0
            self._markers_emitted += 1
            self._last_marker_seq = marker.last_sequence
            return marker

    def stats(self) -> ReplayBackpressureStats:
        with self._lock:
            return ReplayBackpressureStats(
                channel=self._channel.stats(),
                markers_emitted=self._markers_emitted,
                last_marker_seq=self._last_marker_seq,
            )

    def reset(self) -> None:
        with self._lock:
            self._pending_drops = 0
            self._first_drop_seq = 0
            self._last_drop_seq = 0
            self._markers_emitted = 0
            self._last_marker_seq = 0
        self._channel.clear()


def overflow_marker_to_event(
    marker: OverflowMarker, *, sequence: int, monotonic_ns: int,
) -> dict:
    """Build a recorder-ready event dict for one marker."""
    return {
        "event_type": OVERFLOW_MARKER_EVENT_TYPE,
        "sequence": sequence,
        "monotonic_ns": monotonic_ns,
        "payload": marker.to_payload(),
    }
