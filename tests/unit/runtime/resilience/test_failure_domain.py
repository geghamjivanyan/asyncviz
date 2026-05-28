"""Failure-domain tests."""

from __future__ import annotations

import time

from asyncviz.runtime.resilience import (
    BreakerState,
    FailureDomain,
    FailureEvent,
    FailureKind,
    SubsystemPolicy,
)


def _event(
    name: str,
    kind: FailureKind,
    *,
    payload: str = "",
    recoverable: bool = True,
) -> FailureEvent:
    return FailureEvent(
        subsystem=name,
        kind=kind,
        detail="test",
        at_ns=time.monotonic_ns(),
        payload_kind=payload,
        recoverable=recoverable,
    )


def test_domain_records_failure() -> None:
    domain = FailureDomain("x", SubsystemPolicy(failure_threshold=2))
    state = domain.record_failure(_event("x", FailureKind.TRANSIENT))
    assert state == BreakerState.CLOSED
    assert domain.snapshot().total_failures == 1


def test_domain_records_success() -> None:
    domain = FailureDomain("x", SubsystemPolicy())
    domain.record_success()
    assert domain.snapshot().total_successes == 1


def test_quarantine_persists_until_released() -> None:
    domain = FailureDomain("x", SubsystemPolicy(quarantine_payload_kind=True))
    domain.record_failure(
        _event("x", FailureKind.CORRUPTION, payload="frame-1", recoverable=False),
    )
    assert domain.is_quarantined("frame-1")
    assert domain.release_quarantine("frame-1") is True
    assert domain.is_quarantined("frame-1") is False
    assert domain.release_quarantine("frame-1") is False


def test_quarantine_only_when_recoverable_is_false() -> None:
    domain = FailureDomain("x", SubsystemPolicy(quarantine_payload_kind=True))
    domain.record_failure(
        _event("x", FailureKind.TRANSIENT, payload="frame-1", recoverable=True),
    )
    assert domain.is_quarantined("frame-1") is False


def test_listener_observes_failure_and_state() -> None:
    domain = FailureDomain("x", SubsystemPolicy(failure_threshold=1))
    observed: list[tuple[BreakerState, BreakerState]] = []
    domain.subscribe(lambda _e, prev, new: observed.append((prev, new)))
    domain.record_failure(_event("x", FailureKind.TRANSIENT))
    assert observed == [(BreakerState.CLOSED, BreakerState.OPEN)]


def test_listener_unsubscribe() -> None:
    domain = FailureDomain("x", SubsystemPolicy())
    called = []
    unsub = domain.subscribe(lambda *_args: called.append(1))
    unsub()
    domain.record_failure(_event("x", FailureKind.TRANSIENT))
    assert called == []


def test_listener_exception_is_isolated() -> None:
    domain = FailureDomain("x", SubsystemPolicy())

    def _bad(*_args: object) -> None:
        raise RuntimeError("listener failure")

    domain.subscribe(_bad)
    # Must not raise.
    state = domain.record_failure(_event("x", FailureKind.TRANSIENT))
    assert state == BreakerState.CLOSED


def test_allow_request_respects_quarantine_first() -> None:
    domain = FailureDomain("x", SubsystemPolicy(quarantine_payload_kind=True))
    domain.record_failure(
        _event("x", FailureKind.CORRUPTION, payload="frame-1", recoverable=False),
    )
    assert domain.allow_request(payload_kind="frame-1") is False
    assert domain.allow_request(payload_kind="frame-2") is True


def test_reset_clears_state() -> None:
    domain = FailureDomain("x", SubsystemPolicy(failure_threshold=1, quarantine_payload_kind=True))
    domain.record_failure(_event("x", FailureKind.CORRUPTION, payload="f", recoverable=False))
    domain.reset()
    snap = domain.snapshot()
    assert snap.total_failures == 0
    assert snap.quarantined_payloads == ()
    assert snap.breaker.state == BreakerState.CLOSED
