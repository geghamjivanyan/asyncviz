"""Shared fixtures and helpers for blocking-detector tests."""

from __future__ import annotations

from asyncviz.runtime.monitoring.event_loop.lag_measurement import (
    LagMeasurement,
    calculate_lag,
)
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import (
    LagThresholdEvaluation,
    LagThresholds,
)

#: Standard tight thresholds used across the suite. Built once per module
#: import; ``LagThresholds`` is frozen so sharing the instance is safe.
TIGHT_THRESHOLDS = LagThresholds(
    warning_seconds=0.001,
    critical_seconds=0.01,
    freeze_seconds=0.1,
)


def measure(
    lag_ns: int,
    *,
    index: int = 0,
    scheduled_ns: int = 0,
    interval_ns: int = 1_000_000,
) -> LagMeasurement:
    """Build a :class:`LagMeasurement` for tests.

    ``actual_ns`` is derived from ``scheduled_ns + lag_ns`` so the
    monotonic timestamp lines up with the requested lag. Tests can pass
    the same ``scheduled_ns`` (default 0) when they only care about lag
    values; pass a strictly-increasing sequence when cooldowns matter.
    """
    return calculate_lag(
        scheduled_ns=scheduled_ns,
        actual_ns=scheduled_ns + lag_ns,
        interval_ns=interval_ns,
        sample_index=index,
        runtime_id="r",
    )


def evaluate(lag_ns: int, thresholds: LagThresholds = TIGHT_THRESHOLDS) -> LagThresholdEvaluation:
    return thresholds.evaluate(lag_ns)


def measure_and_evaluate(
    lag_ns: int,
    *,
    index: int = 0,
    scheduled_ns: int = 0,
    thresholds: LagThresholds = TIGHT_THRESHOLDS,
) -> tuple[LagMeasurement, LagThresholdEvaluation]:
    m = measure(lag_ns, index=index, scheduled_ns=scheduled_ns)
    return m, thresholds.evaluate(lag_ns)
