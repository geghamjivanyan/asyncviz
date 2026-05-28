from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock


@dataclass
class RuntimeState:
    """Server-side runtime status (started/stopped, uptime).

    This is the *dashboard server's* lifecycle, not the user program's
    asyncio runtime. Once instrumentation lands, a separate ``RuntimeSnapshot``
    will represent the observed program.

    Uptime is computed monotonically from the runtime's :class:`RuntimeClock`
    — the wall-clock ``started_at`` field is preserved for display only and
    never participates in duration math.
    """

    started_at: float | None = None
    stopped_at: float | None = None
    _started_at_monotonic_ns: int | None = None
    _stopped_at_monotonic_ns: int | None = None
    _clock: RuntimeClock | None = None

    @property
    def clock(self) -> RuntimeClock:
        if self._clock is None:
            self._clock = get_runtime_clock()
        return self._clock

    def bind_clock(self, clock: RuntimeClock) -> None:
        """Bind a specific clock instance. Used by bootstrap; no-op if matched."""
        self._clock = clock

    def mark_started(self) -> None:
        clock = self.clock
        self.started_at = clock.now()
        self.stopped_at = None
        self._started_at_monotonic_ns = clock.monotonic_ns()
        self._stopped_at_monotonic_ns = None

    def mark_stopped(self) -> None:
        clock = self.clock
        self.stopped_at = clock.now()
        self._stopped_at_monotonic_ns = clock.monotonic_ns()

    @property
    def status(self) -> str:
        if self.started_at is None:
            return "idle"
        if self.stopped_at is not None:
            return "stopped"
        return "running"

    @property
    def uptime_seconds(self) -> float:
        if self._started_at_monotonic_ns is None:
            return 0.0
        end_ns = (
            self._stopped_at_monotonic_ns
            if self._stopped_at_monotonic_ns is not None
            else self.clock.monotonic_ns()
        )
        return max(0.0, (end_ns - self._started_at_monotonic_ns) / 1_000_000_000)
