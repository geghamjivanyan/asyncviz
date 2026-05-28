"""Canonical lag-measurement value type + measurement semantics.

The lag monitor sleeps on the event loop for a configured interval and
compares the *actual* monotonic delta to the *expected* one. The excess
is the scheduler / event-loop lag — the time the loop spent unable to
service the wake-up callback.

This module deliberately performs only integer-nanosecond math; float
arithmetic is reserved for display surfaces. Measurements are frozen
slot dataclasses so the high-frequency sample path allocates a single
small object and produces zero garbage churn beyond that.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.clock.conversions import NS_PER_MS, NS_PER_SECOND


@dataclass(frozen=True, slots=True)
class LagMeasurement:
    """One sampled event-loop lag observation.

    Fields:

    * ``sample_index``      — monotonic sample counter (0-based; lifetime
      of the monitor). Carries ordering when sequences aren't allocated.
    * ``scheduled_ns``      — the deadline the sampler was *supposed* to
      wake up at. Drives drift correction so successive deadlines stay
      on the configured cadence.
    * ``actual_ns``         — when the sampler actually got CPU.
    * ``interval_ns``       — the configured sample cadence (the
      ``actual - scheduled`` *expected* spacing).
    * ``lag_ns``            — ``max(0, actual_ns - scheduled_ns)``. This
      is the event-loop blocking time at this sample.
    * ``scheduler_delay_ns``— same as ``lag_ns`` today; named separately
      so future implementations can split scheduler-internal latency
      from loop-blocking latency without breaking consumers.
    * ``runtime_id``        — issuing runtime; lets multi-runtime
      diagnostics distinguish sources.

    All values are integer nanoseconds; display helpers below convert.
    """

    sample_index: int
    scheduled_ns: int
    actual_ns: int
    interval_ns: int
    lag_ns: int
    scheduler_delay_ns: int
    runtime_id: str

    @property
    def lag_seconds(self) -> float:
        return self.lag_ns / NS_PER_SECOND

    @property
    def lag_ms(self) -> float:
        return self.lag_ns / NS_PER_MS

    @property
    def scheduler_delay_seconds(self) -> float:
        return self.scheduler_delay_ns / NS_PER_SECOND

    @property
    def interval_seconds(self) -> float:
        return self.interval_ns / NS_PER_SECOND

    def to_dict(self) -> dict[str, object]:
        """JSON-safe view (used by debug endpoints + the event payload)."""
        return {
            "sample_index": self.sample_index,
            "scheduled_ns": self.scheduled_ns,
            "actual_ns": self.actual_ns,
            "interval_ns": self.interval_ns,
            "interval_seconds": self.interval_seconds,
            "lag_ns": self.lag_ns,
            "lag_seconds": self.lag_seconds,
            "lag_ms": self.lag_ms,
            "scheduler_delay_ns": self.scheduler_delay_ns,
            "scheduler_delay_seconds": self.scheduler_delay_seconds,
            "runtime_id": self.runtime_id,
        }


def calculate_lag(
    *,
    scheduled_ns: int,
    actual_ns: int,
    interval_ns: int,
    sample_index: int,
    runtime_id: str,
) -> LagMeasurement:
    """Build a :class:`LagMeasurement` from the canonical inputs.

    Centralized so every producer agrees on the lag formula. Negative
    deltas (rare clock anomalies) clamp to zero — the rest of the
    pipeline relies on ``lag_ns >= 0`` for histogram + percentile math.
    """
    lag_ns = actual_ns - scheduled_ns
    if lag_ns < 0:
        lag_ns = 0
    return LagMeasurement(
        sample_index=sample_index,
        scheduled_ns=scheduled_ns,
        actual_ns=actual_ns,
        interval_ns=interval_ns,
        lag_ns=lag_ns,
        scheduler_delay_ns=lag_ns,
        runtime_id=runtime_id,
    )
