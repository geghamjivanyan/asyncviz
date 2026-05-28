"""Circuit-breaker tests."""

from __future__ import annotations

from asyncviz.runtime.resilience import (
    BreakerState,
    CircuitBreaker,
    SubsystemPolicy,
)


def test_starts_closed() -> None:
    cb = CircuitBreaker("x", SubsystemPolicy())
    assert cb.state == BreakerState.CLOSED
    assert cb.allow_request() is True


def test_trips_after_threshold() -> None:
    cb = CircuitBreaker("x", SubsystemPolicy(failure_threshold=3, failure_window_s=10.0))
    cb.record_failure(now_ns=1)
    cb.record_failure(now_ns=2)
    assert cb.state == BreakerState.CLOSED
    cb.record_failure(now_ns=3)
    assert cb.state == BreakerState.OPEN


def test_failures_outside_window_dont_count() -> None:
    cb = CircuitBreaker("x", SubsystemPolicy(failure_threshold=3, failure_window_s=0.001))
    cb.record_failure(now_ns=0)
    cb.record_failure(now_ns=10**7)  # 10 ms later, outside 1 ms window
    cb.record_failure(now_ns=2 * 10**7)
    # Only the most recent failure should be in the window; breaker
    # stays closed.
    assert cb.state == BreakerState.CLOSED


def test_open_breaker_rejects_requests() -> None:
    cb = CircuitBreaker("x", SubsystemPolicy(failure_threshold=1, failure_window_s=10.0))
    cb.record_failure(now_ns=1)
    assert cb.state == BreakerState.OPEN
    assert cb.allow_request(now_ns=2) is False


def test_transitions_to_half_open_after_cooldown() -> None:
    cb = CircuitBreaker(
        "x",
        SubsystemPolicy(failure_threshold=1, failure_window_s=10.0, open_duration_s=0.001),
    )
    cb.record_failure(now_ns=0)
    assert cb.allow_request(now_ns=10**5) is False  # too soon
    # Past the cooldown — admit a probe.
    assert cb.allow_request(now_ns=2 * 10**6) is True
    assert cb.state == BreakerState.HALF_OPEN


def test_half_open_success_closes_breaker() -> None:
    cb = CircuitBreaker(
        "x",
        SubsystemPolicy(
            failure_threshold=1,
            failure_window_s=10.0,
            open_duration_s=0.001,
            half_open_probes=1,
        ),
    )
    cb.record_failure(now_ns=0)
    cb.allow_request(now_ns=2 * 10**6)
    cb.record_success(now_ns=3 * 10**6)
    assert cb.state == BreakerState.CLOSED


def test_half_open_failure_reopens_breaker() -> None:
    cb = CircuitBreaker(
        "x",
        SubsystemPolicy(
            failure_threshold=1,
            failure_window_s=10.0,
            open_duration_s=0.001,
        ),
    )
    cb.record_failure(now_ns=0)
    cb.allow_request(now_ns=2 * 10**6)
    cb.record_failure(now_ns=3 * 10**6)
    assert cb.state == BreakerState.OPEN


def test_half_open_admits_bounded_probes() -> None:
    cb = CircuitBreaker(
        "x",
        SubsystemPolicy(
            failure_threshold=1,
            open_duration_s=0.001,
            half_open_probes=2,
        ),
    )
    cb.record_failure(now_ns=0)
    assert cb.allow_request(now_ns=2 * 10**6) is True
    assert cb.allow_request(now_ns=3 * 10**6) is True
    # Third probe is denied — only 2 probes per cycle.
    assert cb.allow_request(now_ns=4 * 10**6) is False


def test_force_close_and_reset() -> None:
    cb = CircuitBreaker("x", SubsystemPolicy(failure_threshold=1))
    cb.record_failure()
    assert cb.state == BreakerState.OPEN
    cb.force_close()
    assert cb.state == BreakerState.CLOSED
    cb.record_failure()
    cb.reset()
    assert cb.state == BreakerState.CLOSED
    assert cb.snapshot().trips == 0


def test_snapshot_reports_counters() -> None:
    cb = CircuitBreaker("x", SubsystemPolicy(failure_threshold=2))
    cb.record_failure(now_ns=1)
    cb.record_failure(now_ns=2)
    snap = cb.snapshot()
    assert snap.trips == 1
    assert snap.transitions >= 1
    assert snap.opened_at_ns == 2
