"""Bounded replay windows.

A :class:`ReplayWindow` is the loader's structured way to say
"give me only the frames inside this range". Both sequence- and
timestamp-based ranges share one type so the loader can apply them
identically.

Windows are *open at the end* by default (``end is None``) so the
common case — "play from sequence N onward" — doesn't need an
explicit upper bound."""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.format import ReplayFrame


@dataclass(frozen=True, slots=True)
class ReplayWindow:
    """One bounded view into a replay session."""

    start_sequence: int = 0
    end_sequence: int | None = None
    """``None`` means unbounded above."""

    start_monotonic_ns: int = 0
    end_monotonic_ns: int | None = None
    """``None`` means unbounded above."""

    def contains(self, frame: ReplayFrame) -> bool:
        if frame.sequence < self.start_sequence:
            return False
        if self.end_sequence is not None and frame.sequence > self.end_sequence:
            return False
        if frame.monotonic_ns < self.start_monotonic_ns:
            return False
        return not (
            self.end_monotonic_ns is not None
            and frame.monotonic_ns > self.end_monotonic_ns
        )

    def below_window(self, frame: ReplayFrame) -> bool:
        """Frame is *before* the window starts. The streaming reader
        can use this to skip without checking the upper bound."""
        if frame.sequence < self.start_sequence:
            return True
        return frame.monotonic_ns < self.start_monotonic_ns

    def above_window(self, frame: ReplayFrame) -> bool:
        """Frame is *after* the window ends. The streaming reader
        can use this as an early-stop signal — once we're above, no
        later frame will fall back inside (sequences + monotonic_ns
        are monotonic)."""
        if self.end_sequence is not None and frame.sequence > self.end_sequence:
            return True
        return (
            self.end_monotonic_ns is not None
            and frame.monotonic_ns > self.end_monotonic_ns
        )

    @staticmethod
    def unbounded() -> ReplayWindow:
        return ReplayWindow()

    @staticmethod
    def for_sequences(start: int, end: int | None = None) -> ReplayWindow:
        return ReplayWindow(start_sequence=start, end_sequence=end)

    @staticmethod
    def for_timestamps(start_ns: int, end_ns: int | None = None) -> ReplayWindow:
        return ReplayWindow(start_monotonic_ns=start_ns, end_monotonic_ns=end_ns)
