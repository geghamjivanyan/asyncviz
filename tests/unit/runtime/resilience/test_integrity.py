"""Integrity-invariant tests."""

from __future__ import annotations

import pytest

from asyncviz.runtime.resilience import (
    BreakerSnapshot,
    BreakerState,
    FailureDomainSnapshot,
    IsolationIntegrityError,
    SupervisorSnapshot,
    assert_isolation_clean,
    check_domain,
    check_supervisor,
)


def _breaker(state: BreakerState = BreakerState.CLOSED, *, trips: int = 0) -> BreakerSnapshot:
    return BreakerSnapshot(
        state=state,
        failures_in_window=0,
        successes_since_open=0,
        trips=trips,
        transitions=0,
        opened_at_ns=0,
        last_failure_at_ns=0,
        last_success_at_ns=0,
    )


def _domain(**kwargs: object) -> FailureDomainSnapshot:
    defaults = {
        "name": "x",
        "breaker": _breaker(),
        "total_failures": 0,
        "total_successes": 0,
        "quarantined_payloads": (),
        "last_failure": None,
        "recent_failures": (),
    }
    defaults.update(kwargs)
    return FailureDomainSnapshot(**defaults)  # type: ignore[arg-type]


def test_clean_domain() -> None:
    assert check_domain(_domain()) == ()


def test_negative_counter_flagged() -> None:
    findings = check_domain(_domain(total_failures=-1))
    assert any(f.kind == "negative-counter" for f in findings)


def test_open_without_trip_flagged() -> None:
    findings = check_domain(
        _domain(breaker=_breaker(state=BreakerState.OPEN, trips=0)),
    )
    assert any(f.kind == "open-without-trip" for f in findings)


def test_supervisor_clean() -> None:
    snap = SupervisorSnapshot(
        subsystem="x",
        attempts=0,
        successes=0,
        failures=0,
        last_verdict=None,
        abandoned=False,
    )
    assert check_supervisor(snap) == ()


def test_supervisor_abandoned_without_attempts_flagged() -> None:
    snap = SupervisorSnapshot(
        subsystem="x",
        attempts=0,
        successes=0,
        failures=0,
        last_verdict=None,
        abandoned=True,
    )
    findings = check_supervisor(snap)
    assert any(f.kind == "history-inconsistent" for f in findings)


def test_assert_clean_passes() -> None:
    assert_isolation_clean((_domain(),))


def test_assert_clean_raises() -> None:
    with pytest.raises(IsolationIntegrityError):
        assert_isolation_clean(
            (_domain(breaker=_breaker(state=BreakerState.OPEN, trips=0)),),
        )
