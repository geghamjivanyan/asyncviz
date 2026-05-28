"""Monotonic-clock adapter for the lag monitor.

The monitor reads the system monotonic clock through this thin abstraction
so tests can inject a deterministic fake (see
:class:`tests.unit.monitoring.helpers.FakeMonotonicClock`). Wall time is
intentionally absent — every lag measurement is a *delta of monotonic
readings*, so wall clock drift cannot pollute the signal.

Two clock surfaces are exposed:

* :class:`MonotonicClockProtocol` — duck-typed contract; ``monotonic_ns()``
  is the only required method.
* :class:`SystemMonotonicClock`   — the production implementation; thin
  wrapper around :func:`time.monotonic_ns` to keep the import surface
  identical to the rest of the runtime.

:class:`LagClock` is the orchestration adapter — it understands the lag
monitor's contract (last sampled, scheduled-next, drift), and provides
small helpers for the scheduler / sampler so they don't reach for raw
``time`` themselves.
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from asyncviz.runtime.clock.conversions import NS_PER_SECOND, seconds_to_ns


@runtime_checkable
class MonotonicClockProtocol(Protocol):
    """The minimal clock contract the lag monitor depends on.

    Both the production system clock and the test fake satisfy this. The
    contract is deliberately a single method so swapping in deterministic
    clocks in tests is trivial.
    """

    def monotonic_ns(self) -> int:  # pragma: no cover - protocol
        ...


class SystemMonotonicClock:
    """Default :class:`MonotonicClockProtocol` — wraps :func:`time.monotonic_ns`.

    Held as the default ``LagClock`` source. Allocates nothing per call;
    the wrapped builtin is a CPython fast-path.
    """

    __slots__ = ()

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()


class LagClock:
    """Adapter the lag monitor uses for every timing query.

    Wraps a :class:`MonotonicClockProtocol` and provides:

    * :meth:`now_ns`           — raw reading.
    * :meth:`elapsed_ns`       — ``now - start`` clamped at zero.
    * :meth:`seconds_to_ns`    — helper for converting a configured
      interval into integer nanoseconds without floating-point drift.
    * :meth:`schedule_next_ns` — given a previous wake-up and an
      interval, returns the next monotonic deadline. Drift-corrected.

    Pure: no internal state beyond the wrapped clock object. Safe to
    share across threads.
    """

    __slots__ = ("_source",)

    def __init__(self, source: MonotonicClockProtocol | None = None) -> None:
        self._source = source or SystemMonotonicClock()

    @property
    def source(self) -> MonotonicClockProtocol:
        return self._source

    def now_ns(self) -> int:
        return self._source.monotonic_ns()

    def now_seconds(self) -> float:
        return self._source.monotonic_ns() / NS_PER_SECOND

    @staticmethod
    def elapsed_ns(start_ns: int, end_ns: int) -> int:
        """Non-negative delta between two monotonic readings."""
        if end_ns < start_ns:
            return 0
        return end_ns - start_ns

    @staticmethod
    def seconds_to_ns(seconds: float) -> int:
        """Convert a positive float-seconds interval to integer nanoseconds.

        Negative inputs clamp to zero — the scheduler treats a zero
        interval as "schedule immediately" and never as a sleep request.
        """
        if seconds <= 0:
            return 0
        return seconds_to_ns(seconds)

    @staticmethod
    def schedule_next_ns(previous_deadline_ns: int, interval_ns: int) -> int:
        """Next deadline = previous + interval. Caller compares to ``now_ns``.

        Drift-correct: the scheduler adds the configured interval to the
        *target* deadline, not to ``now``. If a sample fires late, the
        next deadline still lands on the original cadence so the rolling
        window doesn't smear.
        """
        if interval_ns <= 0:
            return previous_deadline_ns
        return previous_deadline_ns + interval_ns
