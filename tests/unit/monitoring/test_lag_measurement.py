from __future__ import annotations

from asyncviz.runtime.monitoring.event_loop.lag_measurement import (
    LagMeasurement,
    calculate_lag,
)


def test_calculate_lag_simple() -> None:
    m = calculate_lag(
        scheduled_ns=1_000,
        actual_ns=1_500,
        interval_ns=1_000,
        sample_index=3,
        runtime_id="r",
    )
    assert isinstance(m, LagMeasurement)
    assert m.lag_ns == 500
    assert m.scheduler_delay_ns == 500
    assert m.sample_index == 3
    assert m.runtime_id == "r"


def test_calculate_lag_clamps_negative_to_zero() -> None:
    """Clock anomaly: actual < scheduled. Lag clamps at 0."""
    m = calculate_lag(
        scheduled_ns=2_000,
        actual_ns=1_500,
        interval_ns=1_000,
        sample_index=0,
        runtime_id="r",
    )
    assert m.lag_ns == 0
    assert m.scheduler_delay_ns == 0


def test_calculate_lag_exact_wakeup_has_zero_lag() -> None:
    m = calculate_lag(
        scheduled_ns=10_000,
        actual_ns=10_000,
        interval_ns=1_000,
        sample_index=0,
        runtime_id="r",
    )
    assert m.lag_ns == 0


def test_measurement_seconds_conversion() -> None:
    m = calculate_lag(
        scheduled_ns=0,
        actual_ns=1_500_000,
        interval_ns=1_000_000,
        sample_index=0,
        runtime_id="r",
    )
    assert m.lag_ms == 1.5
    assert m.lag_seconds == 1.5e-3
    assert m.interval_seconds == 1e-3


def test_measurement_to_dict_carries_canonical_fields() -> None:
    m = calculate_lag(
        scheduled_ns=10,
        actual_ns=510,
        interval_ns=100,
        sample_index=2,
        runtime_id="abc",
    )
    d = m.to_dict()
    for key in (
        "sample_index",
        "scheduled_ns",
        "actual_ns",
        "interval_ns",
        "interval_seconds",
        "lag_ns",
        "lag_seconds",
        "lag_ms",
        "scheduler_delay_ns",
        "scheduler_delay_seconds",
        "runtime_id",
    ):
        assert key in d
    assert d["lag_ns"] == 500
    assert d["runtime_id"] == "abc"
