"""Clock re-anchoring for the seek coordinator.

When a seek completes, the engine's virtual clock has to jump to
the landed frame's ``monotonic_ns`` so subsequent playback uses the
seek target as its time anchor. This module wraps the
:class:`ReplayClock` so the coordinator can describe that jump in
one explicit call (instead of poking at clock internals).
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.replay_clock import ReplayClock


@dataclass(frozen=True, slots=True)
class ClockAnchor:
    """Snapshot of the clock's anchor right after a seek lands."""

    virtual_ns: int
    speed: float
    paused: bool


class SeekClockCoordinator:
    """Owns the clock side of a seek transition."""

    __slots__ = ("_clock",)

    def __init__(self, clock: ReplayClock) -> None:
        self._clock = clock

    @property
    def virtual_ns(self) -> int:
        return self._clock.current_virtual_ns()

    @property
    def paused(self) -> bool:
        return self._clock.paused

    def anchor_at(self, virtual_ns: int) -> ClockAnchor:
        """Jump the clock to ``virtual_ns`` + return the anchor."""
        self._clock.jump_to(virtual_ns)
        return ClockAnchor(
            virtual_ns=self._clock.current_virtual_ns(),
            speed=self._clock.speed,
            paused=self._clock.paused,
        )

    def freeze(self) -> ClockAnchor:
        """Pause the clock if it isn't already. Used by the
        coordinator's pause-before-seek path."""
        if not self._clock.paused:
            self._clock.pause()
        return ClockAnchor(
            virtual_ns=self._clock.current_virtual_ns(),
            speed=self._clock.speed,
            paused=self._clock.paused,
        )

    def resume(self) -> ClockAnchor:
        """Resume the clock if currently paused."""
        if self._clock.paused:
            self._clock.resume()
        return ClockAnchor(
            virtual_ns=self._clock.current_virtual_ns(),
            speed=self._clock.speed,
            paused=self._clock.paused,
        )
