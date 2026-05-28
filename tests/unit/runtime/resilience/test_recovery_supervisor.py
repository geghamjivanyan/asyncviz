"""Recovery-supervisor tests."""

from __future__ import annotations

from asyncviz.runtime.resilience import (
    FailureDomain,
    FailureEvent,
    FailureKind,
    RecoverySupervisor,
    SubsystemPolicy,
)
from asyncviz.runtime.resilience.models.breaker_state import BreakerState


def _domain() -> FailureDomain:
    return FailureDomain(
        "x",
        SubsystemPolicy(failure_threshold=1, max_recovery_attempts=3),
    )


def _trip(domain: FailureDomain) -> None:
    domain.record_failure(
        FailureEvent(
            subsystem="x",
            kind=FailureKind.TRANSIENT,
            detail="boom",
            at_ns=1,
        ),
    )
    assert domain.breaker.state == BreakerState.OPEN


def test_skipped_when_breaker_closed() -> None:
    domain = _domain()
    supervisor = RecoverySupervisor(domain)
    supervisor.register(lambda _d: True)
    outcome = supervisor.attempt()
    assert outcome.verdict == "skipped"


def test_deferred_when_no_hook_registered() -> None:
    domain = _domain()
    _trip(domain)
    supervisor = RecoverySupervisor(domain)
    outcome = supervisor.attempt()
    assert outcome.verdict == "deferred"


def test_succeeded_closes_breaker() -> None:
    domain = _domain()
    _trip(domain)
    supervisor = RecoverySupervisor(domain)
    supervisor.register(lambda _d: True)
    outcome = supervisor.attempt()
    assert outcome.verdict == "succeeded"
    assert domain.breaker.state == BreakerState.CLOSED


def test_failed_records_attempt() -> None:
    domain = _domain()
    _trip(domain)
    supervisor = RecoverySupervisor(domain)
    supervisor.register(lambda _d: False)
    outcome = supervisor.attempt()
    assert outcome.verdict == "failed"
    assert supervisor.snapshot().failures == 1


def test_hook_exception_records_failure() -> None:
    domain = _domain()
    _trip(domain)
    supervisor = RecoverySupervisor(domain)

    def _bad(_d: FailureDomain) -> bool:
        raise RuntimeError("hook bug")

    supervisor.register(_bad)
    outcome = supervisor.attempt()
    assert outcome.verdict == "failed"


def test_abandoned_after_max_attempts() -> None:
    domain = _domain()
    _trip(domain)
    supervisor = RecoverySupervisor(domain)
    supervisor.register(lambda _d: False)
    outcomes = [supervisor.attempt() for _ in range(5)]
    assert outcomes[-1].verdict == "abandoned"
    assert supervisor.abandoned() is True


def test_reset_abandoned() -> None:
    domain = _domain()
    _trip(domain)
    supervisor = RecoverySupervisor(domain)
    supervisor.register(lambda _d: False)
    for _ in range(5):
        supervisor.attempt()
    assert supervisor.abandoned() is True
    supervisor.reset_abandoned()
    assert supervisor.abandoned() is False


async def test_async_attempt_uses_async_hook() -> None:
    domain = _domain()
    _trip(domain)
    supervisor = RecoverySupervisor(domain)
    called = []

    async def _hook(d: FailureDomain) -> bool:
        called.append(d.name)
        return True

    supervisor.register_async(_hook)
    outcome = await supervisor.attempt_async()
    assert outcome.verdict == "succeeded"
    assert called == ["x"]


async def test_async_attempt_falls_back_to_sync_hook() -> None:
    domain = _domain()
    _trip(domain)
    supervisor = RecoverySupervisor(domain)
    supervisor.register(lambda _d: True)
    outcome = await supervisor.attempt_async()
    assert outcome.verdict == "succeeded"
