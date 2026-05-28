"""Single lag-sampling step.

The sampler is intentionally tiny — it computes one
:class:`LagMeasurement` from a (scheduled_ns, actual_ns, interval_ns)
triple and returns it. All state is held by the caller (the scheduler);
the sampler is pure-functional so tests can call it without spinning up
the asyncio loop.

Kept separate from the scheduler because:

* the same sampling math runs from both the asyncio loop (production)
  and synchronous test helpers (fake clocks).
* future implementations may bypass the scheduler entirely (e.g. a
  monotonic-trigger sampler from instrumentation hooks).
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.monitoring.event_loop.lag_clock import LagClock
from asyncviz.runtime.monitoring.event_loop.lag_measurement import (
    LagMeasurement,
    calculate_lag,
)


@dataclass(frozen=True, slots=True)
class SampleRequest:
    """Inputs for one :meth:`LagSampler.sample` call."""

    sample_index: int
    scheduled_ns: int
    interval_ns: int
    runtime_id: str


class LagSampler:
    """Stateless sampler bound to a :class:`LagClock`.

    The only mutable state is the clock; everything else flows through
    the request. Thread-safe by construction.
    """

    __slots__ = ("_clock",)

    def __init__(self, clock: LagClock) -> None:
        self._clock = clock

    @property
    def clock(self) -> LagClock:
        return self._clock

    def sample(self, request: SampleRequest) -> LagMeasurement:
        """Take one sample using the bound clock.

        Reads the clock exactly once. The returned measurement is fully
        derived from the request + the single clock reading, which keeps
        the sample's ``lag_ns`` honest (no second clock read can sneak
        in between the deadline and the measurement).
        """
        actual_ns = self._clock.now_ns()
        return calculate_lag(
            scheduled_ns=request.scheduled_ns,
            actual_ns=actual_ns,
            interval_ns=request.interval_ns,
            sample_index=request.sample_index,
            runtime_id=request.runtime_id,
        )
