"""Cross-loop binding tests for the lag scheduler / monitor.

Regression suite for the architectural fix: the lag sampler must
observe the loop the caller designates, not the loop ``start()``
happens to be called on. The CLI bootstrap uses this to bind the
sampler to the user's ``asyncio.run(main())`` loop while the
dashboard server runs on its own daemon-thread loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import time

import pytest

from asyncviz.runtime.monitoring.event_loop.lag_clock import LagClock
from asyncviz.runtime.monitoring.event_loop.lag_configuration import LagConfiguration
from asyncviz.runtime.monitoring.event_loop.lag_measurement import LagMeasurement
from asyncviz.runtime.monitoring.event_loop.lag_monitor import EventLoopLagMonitor
from asyncviz.runtime.monitoring.event_loop.lag_sampler import LagSampler
from asyncviz.runtime.monitoring.event_loop.lag_scheduler import LagScheduler
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import LagThresholds


def _run_loop_in_thread(loop: asyncio.AbstractEventLoop, ready: threading.Event) -> None:
    asyncio.set_event_loop(loop)
    ready.set()
    try:
        loop.run_forever()
    finally:
        loop.close()


async def test_scheduler_start_binds_cadence_task_to_explicit_loop() -> None:
    """When ``loop=`` is supplied, the cadence task lives on that loop.

    Verifies via :meth:`asyncio.Task.get_loop` — the production code
    is loop-bound through ``loop.create_task``, so this is a direct
    assertion on the binding contract.
    """
    target_loop = asyncio.new_event_loop()
    ready = threading.Event()
    thread = threading.Thread(
        target=_run_loop_in_thread,
        args=(target_loop, ready),
        name="cross-loop-target",
        daemon=True,
    )
    thread.start()
    assert ready.wait(timeout=1.0)

    seen: list[LagMeasurement] = []
    sched = LagScheduler(
        clock=LagClock(),
        sampler=LagSampler(LagClock()),
        sample_sink=seen.append,
        drop_sink=lambda _c: None,
        runtime_id="cross-loop-test",
    )
    sched.configure(interval_ns=5_000_000)  # 5 ms
    try:
        await sched.start(loop=target_loop)
        # ``_task`` is created on the target loop via call_soon_threadsafe;
        # the task object itself is loop-bound.
        assert sched._task is not None  # type: ignore[attr-defined]
        assert sched._task.get_loop() is target_loop  # type: ignore[attr-defined]
        # Let the cadence run on the target loop for a bit.
        await asyncio.sleep(0.08)
        assert len(seen) >= 3
    finally:
        await sched.stop()
        target_loop.call_soon_threadsafe(target_loop.stop)
        thread.join(timeout=1.0)


def test_blocking_the_dashboard_loop_does_not_emit_warnings_for_target_loop() -> None:
    """The sampler must NOT see blocking on a loop it is not bound to.

    Mirrors the production bug: two loops, sampler bound to loop A.
    Block loop B aggressively. Detector must not fire any
    above-warning outcome.
    """
    # The "target" loop is the one we observe; the "noise" loop is the
    # dashboard analogue — we block it heavily, and assert the sampler
    # bound to the target loop reports near-zero lag.
    target_loop = asyncio.new_event_loop()
    noise_loop = asyncio.new_event_loop()

    target_ready = threading.Event()
    noise_ready = threading.Event()
    target_thread = threading.Thread(
        target=_run_loop_in_thread,
        args=(target_loop, target_ready),
        name="target",
        daemon=True,
    )
    noise_thread = threading.Thread(
        target=_run_loop_in_thread,
        args=(noise_loop, noise_ready),
        name="noise",
        daemon=True,
    )
    target_thread.start()
    noise_thread.start()
    assert target_ready.wait(timeout=1.0)
    assert noise_ready.wait(timeout=1.0)

    monitor = EventLoopLagMonitor(
        configuration=LagConfiguration(
            sample_interval_seconds=0.05,
            thresholds=LagThresholds(
                warning_seconds=0.05,
                critical_seconds=0.20,
                freeze_seconds=1.0,
            ),
        ),
        event_emitter=None,
    )
    # ``LagThresholdEvaluation.severity`` is the actual classification —
    # ``LagMeasurement`` itself carries the raw lag value. We're
    # checking the threshold-trip case, so NORMAL doesn't count.
    breach_names = {"WARNING", "CRITICAL", "FREEZE"}
    breaches: list[str] = []

    def _record_breach(_m: LagMeasurement, evaluation: object) -> None:
        sev = getattr(evaluation, "severity", None)
        name = getattr(sev, "name", "NONE")
        if name in breach_names:
            breaches.append(name)

    monitor.subscribe(_record_breach)

    try:
        monitor.bind_to_loop_threadsafe(target_loop)

        # Block the *noise* loop hard while the sampler runs on the
        # *target* loop.
        def _block_noise() -> None:
            time.sleep(0.4)

        for _ in range(3):
            noise_loop.call_soon_threadsafe(_block_noise)
            time.sleep(0.5)

        # Give the sampler time to observe several quiet ticks on the
        # target loop.
        time.sleep(0.4)
    finally:
        # Stop the monitor from the noise loop (some other loop) — the
        # monitor's stop handles the cross-loop case.
        async def _stop() -> None:
            await monitor.stop()

        fut = asyncio.run_coroutine_threadsafe(_stop(), noise_loop)
        with contextlib.suppress(Exception):
            fut.result(timeout=2.0)
        target_loop.call_soon_threadsafe(target_loop.stop)
        noise_loop.call_soon_threadsafe(noise_loop.stop)
        target_thread.join(timeout=2.0)
        noise_thread.join(timeout=2.0)

    # The target loop never blocked; no breaches should have fired.
    assert breaches == [], f"unexpected lag breaches: {breaches}"


def test_blocking_the_target_loop_emits_critical_measurements() -> None:
    """Symmetric to the previous test: blocking the OBSERVED loop fires.

    This is the positive case — once the sampler is bound to the
    user's loop, blocking that loop must produce CRITICAL-severity
    measurements that the downstream detector can turn into warnings.
    """
    target_loop = asyncio.new_event_loop()
    ready = threading.Event()
    thread = threading.Thread(
        target=_run_loop_in_thread,
        args=(target_loop, ready),
        name="blocking-target",
        daemon=True,
    )
    thread.start()
    assert ready.wait(timeout=1.0)

    monitor = EventLoopLagMonitor(
        configuration=LagConfiguration(
            sample_interval_seconds=0.05,
            thresholds=LagThresholds(
                warning_seconds=0.05,
                critical_seconds=0.20,
                freeze_seconds=1.0,
            ),
        ),
        event_emitter=None,
    )
    severities: list[str] = []

    def _record(_m: LagMeasurement, evaluation: object) -> None:
        sev = getattr(evaluation, "severity", None)
        name = getattr(sev, "name", "NONE")
        severities.append(name)

    monitor.subscribe(_record)

    try:
        monitor.bind_to_loop_threadsafe(target_loop)

        def _block_target() -> None:
            # Hard sync block inside the target loop — exactly what
            # the user's time.sleep() inside an async task does.
            time.sleep(0.4)

        # Block the target loop a couple of times.
        for _ in range(3):
            target_loop.call_soon_threadsafe(_block_target)
            # Give the sampler a chance to observe + recover between
            # blocks.
            time.sleep(0.6)

    finally:
        # Stop via a temporary helper loop so we exercise the
        # cross-loop stop path.
        helper_loop = asyncio.new_event_loop()
        helper_ready = threading.Event()
        helper_thread = threading.Thread(
            target=_run_loop_in_thread,
            args=(helper_loop, helper_ready),
            name="helper-stop",
            daemon=True,
        )
        helper_thread.start()
        assert helper_ready.wait(timeout=1.0)

        async def _stop_monitor() -> None:
            await monitor.stop()

        with contextlib.suppress(Exception):
            asyncio.run_coroutine_threadsafe(_stop_monitor(), helper_loop).result(timeout=2.0)

        target_loop.call_soon_threadsafe(target_loop.stop)
        helper_loop.call_soon_threadsafe(helper_loop.stop)
        thread.join(timeout=2.0)
        helper_thread.join(timeout=2.0)

    # At least one CRITICAL-severity measurement should have landed.
    assert "CRITICAL" in severities or "FREEZE" in severities, (
        f"expected CRITICAL lag from blocking target loop, got {severities!r}"
    )


@pytest.mark.parametrize("loop_arg", [None])
async def test_scheduler_legacy_no_loop_argument_still_works(loop_arg) -> None:
    """The no-argument path must remain identical to the prior behavior.

    A None ``loop=`` argument means "bind to the calling loop" — the
    contract the entire existing test suite + every non-CLI caller
    relies on.
    """
    seen: list[LagMeasurement] = []
    sched = LagScheduler(
        clock=LagClock(),
        sampler=LagSampler(LagClock()),
        sample_sink=seen.append,
        drop_sink=lambda _c: None,
        runtime_id="r",
    )
    sched.configure(interval_ns=5_000_000)
    await sched.start(loop=loop_arg)
    assert sched._task is not None  # type: ignore[attr-defined]
    assert sched._task.get_loop() is asyncio.get_running_loop()  # type: ignore[attr-defined]
    await asyncio.sleep(0.05)
    await sched.stop()
    assert len(seen) >= 3
