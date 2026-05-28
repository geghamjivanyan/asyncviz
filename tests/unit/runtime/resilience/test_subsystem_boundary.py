"""Subsystem-boundary tests."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.runtime.resilience import (
    BreakerState,
    FailureDomain,
    SubsystemBoundary,
    SubsystemPolicy,
    SubsystemUnavailable,
)
from asyncviz.runtime.resilience.subsystem_boundary import AsyncSubsystemBoundary


def _make_domain(**kwargs: object) -> FailureDomain:
    return FailureDomain("x", SubsystemPolicy(**kwargs))  # type: ignore[arg-type]


def test_boundary_records_success_on_clean_exit() -> None:
    domain = _make_domain()
    with SubsystemBoundary(
        domain,
        payload_kind="",
        suppress=True,
        on_failure=None,
        swallow_unavailable=True,
    ):
        pass
    assert domain.snapshot().total_successes == 1


def test_boundary_records_failure_and_suppresses() -> None:
    domain = _make_domain()
    with SubsystemBoundary(
        domain,
        payload_kind="",
        suppress=True,
        on_failure=None,
        swallow_unavailable=True,
    ):
        raise TimeoutError("transient")
    assert domain.snapshot().total_failures == 1


def test_boundary_propagates_do_not_retry_exceptions() -> None:
    domain = _make_domain()
    with pytest.raises(AssertionError), SubsystemBoundary(
        domain,
        payload_kind="",
        suppress=True,
        on_failure=None,
        swallow_unavailable=True,
    ):
        raise AssertionError("logic bug")


def test_boundary_propagates_corruption() -> None:
    domain = _make_domain(quarantine_payload_kind=True)
    with pytest.raises(ValueError), SubsystemBoundary(
        domain,
        payload_kind="frame-1",
        suppress=True,
        on_failure=None,
        swallow_unavailable=True,
    ):
        raise ValueError("corrupted-frame: bad checksum")
    assert "frame-1" in domain.quarantined()


def test_boundary_skips_silently_when_open_and_swallow() -> None:
    domain = _make_domain(failure_threshold=1)
    domain.breaker.force_open()
    executed = []
    with SubsystemBoundary(
        domain,
        payload_kind="",
        suppress=True,
        on_failure=None,
        swallow_unavailable=True,
    ) as b:
        executed.append(b.admitted)
        raise TimeoutError("should be swallowed")
    assert executed == [False]
    # Failure recorded against the breaker is NOT double-counted —
    # only the original force_open contributed to trips.
    assert domain.snapshot().total_failures == 0


def test_boundary_raises_unavailable_when_strict() -> None:
    domain = _make_domain(failure_threshold=1)
    domain.breaker.force_open()
    with pytest.raises(SubsystemUnavailable), SubsystemBoundary(
        domain,
        payload_kind="",
        suppress=True,
        on_failure=None,
        swallow_unavailable=False,
    ):
        pass


def test_boundary_does_not_treat_cancelled_as_failure_by_default() -> None:
    domain = _make_domain()
    with pytest.raises(asyncio.CancelledError), SubsystemBoundary(
        domain,
        payload_kind="",
        suppress=True,
        on_failure=None,
        swallow_unavailable=True,
    ):
        raise asyncio.CancelledError()
    assert domain.snapshot().total_failures == 0


def test_boundary_treats_cancelled_as_failure_when_configured() -> None:
    domain = _make_domain(treat_cancelled_as_failure=True)
    with pytest.raises(asyncio.CancelledError), SubsystemBoundary(
        domain,
        payload_kind="",
        suppress=False,
        on_failure=None,
        swallow_unavailable=True,
    ):
        raise asyncio.CancelledError()
    assert domain.snapshot().total_failures == 1


def test_boundary_on_failure_hook_runs() -> None:
    domain = _make_domain()
    captured: list[str] = []
    with SubsystemBoundary(
        domain,
        payload_kind="frame-1",
        suppress=True,
        on_failure=lambda event: captured.append(event.payload_kind),
        swallow_unavailable=True,
    ):
        raise TimeoutError("x")
    assert captured == ["frame-1"]


def test_boundary_on_failure_hook_isolated() -> None:
    domain = _make_domain()

    def _bad(_event: object) -> None:
        raise RuntimeError("hook bug")

    # Must not raise.
    with SubsystemBoundary(
        domain,
        payload_kind="",
        suppress=True,
        on_failure=_bad,
        swallow_unavailable=True,
    ):
        raise TimeoutError("x")
    assert domain.snapshot().total_failures == 1


async def test_async_boundary_records_success() -> None:
    domain = _make_domain()
    async with AsyncSubsystemBoundary(
        domain,
        payload_kind="",
        suppress=True,
        on_failure=None,
        swallow_unavailable=True,
    ):
        await asyncio.sleep(0)
    assert domain.snapshot().total_successes == 1


async def test_async_boundary_records_failure() -> None:
    domain = _make_domain()
    async with AsyncSubsystemBoundary(
        domain,
        payload_kind="",
        suppress=True,
        on_failure=None,
        swallow_unavailable=True,
    ):
        await asyncio.sleep(0)
        raise TimeoutError("x")
    assert domain.snapshot().total_failures == 1


async def test_async_boundary_passes_through_cancellation() -> None:
    domain = _make_domain()
    with pytest.raises(asyncio.CancelledError):
        async with AsyncSubsystemBoundary(
            domain,
            payload_kind="",
            suppress=True,
            on_failure=None,
            swallow_unavailable=True,
        ):
            await asyncio.sleep(0)
            raise asyncio.CancelledError()
    # State change of breaker: cancellation didn't penalize.
    assert domain.breaker.state == BreakerState.CLOSED
