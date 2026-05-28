from __future__ import annotations

import asyncio

from asyncviz.runtime.monitoring.event_loop.lag_clock import LagClock
from asyncviz.runtime.monitoring.event_loop.lag_measurement import LagMeasurement
from asyncviz.runtime.monitoring.event_loop.lag_sampler import LagSampler
from asyncviz.runtime.monitoring.event_loop.lag_scheduler import LagScheduler


async def test_scheduler_dispatches_samples_to_sink() -> None:
    seen: list[LagMeasurement] = []
    drops: list[int] = []
    sched = LagScheduler(
        clock=LagClock(),
        sampler=LagSampler(LagClock()),
        sample_sink=seen.append,
        drop_sink=drops.append,
        runtime_id="r",
    )
    sched.configure(interval_ns=5_000_000)  # 5ms
    await sched.start()
    await asyncio.sleep(0.05)  # ~10 samples
    await sched.stop()
    assert len(seen) >= 3
    # Sample indices monotonically increase
    indices = [m.sample_index for m in seen]
    assert indices == sorted(indices)


async def test_double_start_is_idempotent() -> None:
    sched = LagScheduler(
        clock=LagClock(),
        sampler=LagSampler(LagClock()),
        sample_sink=lambda m: None,
        drop_sink=lambda c: None,
        runtime_id="r",
    )
    sched.configure(interval_ns=10_000_000)
    await sched.start()
    await sched.start()
    assert sched.is_running
    await sched.stop()


async def test_stop_without_start_is_safe() -> None:
    sched = LagScheduler(
        clock=LagClock(),
        sampler=LagSampler(LagClock()),
        sample_sink=lambda m: None,
        drop_sink=lambda c: None,
        runtime_id="r",
    )
    sched.configure(interval_ns=10_000_000)
    await sched.stop()  # should not raise


async def test_sample_sink_exception_does_not_kill_scheduler() -> None:
    seen: list[LagMeasurement] = []

    def raising_first_then_ok(m: LagMeasurement) -> None:
        seen.append(m)
        if len(seen) == 1:
            raise RuntimeError("first failure")

    sched = LagScheduler(
        clock=LagClock(),
        sampler=LagSampler(LagClock()),
        sample_sink=raising_first_then_ok,
        drop_sink=lambda c: None,
        runtime_id="r",
    )
    sched.configure(interval_ns=5_000_000)
    await sched.start()
    await asyncio.sleep(0.05)
    await sched.stop()
    assert len(seen) >= 2  # second sample still arrived


async def test_scheduler_must_configure_before_start() -> None:
    sched = LagScheduler(
        clock=LagClock(),
        sampler=LagSampler(LagClock()),
        sample_sink=lambda m: None,
        drop_sink=lambda c: None,
        runtime_id="r",
    )
    import pytest

    with pytest.raises(RuntimeError, match="configure"):
        await sched.start()
