"""Cadence loop for the lag monitor.

Owns the asyncio task that wakes up on the configured interval, calls
the sampler, and feeds the measurement to the monitor's apply hook.

Design notes:

* **Drift-correct**: deadlines advance by ``interval`` from the *target*,
  not from ``now``. A late wake-up doesn't smear successive samples.
* **Overflow-tolerant**: if a sample runs more than one full interval
  late, the scheduler counts each missed deadline once and advances
  past them. This stops the scheduler from spamming the loop with
  back-to-back catch-up samples after a freeze.
* **Cancellation-safe**: ``stop()`` cancels the task and awaits its
  completion. The loop catches ``asyncio.CancelledError`` and re-raises
  so the task transitions to ``DONE`` cleanly.
* **Lock-free hot path**: per-sample state is local to the loop. The
  monitor's apply hook is a synchronous callable invoked from the loop.

The scheduler doesn't know about thresholds, events, or backpressure —
it only schedules and dispatches. Higher-level behavior lives in
:class:`EventLoopLagMonitor`.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable

from asyncviz.runtime.monitoring.event_loop.lag_clock import LagClock
from asyncviz.runtime.monitoring.event_loop.lag_measurement import LagMeasurement
from asyncviz.runtime.monitoring.event_loop.lag_sampler import LagSampler, SampleRequest
from asyncviz.utils.logging import get_logger

logger = get_logger("runtime.monitoring.event_loop.scheduler")


#: Callback signature the scheduler invokes once per recorded sample.
#: Returning anything is ignored. Exceptions are caught + logged so a
#: misbehaving apply hook never kills the scheduler.
SampleSink = Callable[[LagMeasurement], None]

#: Callback invoked when the scheduler observes one or more dropped
#: deadlines (a sample that ran > 1 interval late). The argument is the
#: count of *additional* missed intervals (≥1).
DropSink = Callable[[int], None]


class LagScheduler:
    """Asyncio-driven cadence loop.

    Construct → start() → … → stop(). Re-startable: after stop(), a
    fresh start() spins up a new task with a reset sample index.
    """

    def __init__(
        self,
        *,
        clock: LagClock,
        sampler: LagSampler,
        sample_sink: SampleSink,
        drop_sink: DropSink,
        runtime_id: str,
    ) -> None:
        self._clock = clock
        self._sampler = sampler
        self._sample_sink = sample_sink
        self._drop_sink = drop_sink
        self._runtime_id = runtime_id
        self._interval_ns: int = 0
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._sample_index: int = 0

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def configure(self, *, interval_ns: int) -> None:
        """Update the cadence. Takes effect on the next loop iteration.

        If the scheduler isn't running this just stashes the value for
        the next ``start()``.
        """
        if interval_ns <= 0:
            raise ValueError(f"interval_ns must be > 0 (got {interval_ns})")
        self._interval_ns = interval_ns

    async def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Spin up the cadence task on the supplied loop. Idempotent.

        If ``loop`` is ``None`` the scheduler binds to the loop that
        called ``start()`` (legacy behavior — tests + same-loop setups).

        If ``loop`` is provided and is **not** the current running loop,
        the cadence task is scheduled onto the target loop via
        :meth:`AbstractEventLoop.call_soon_threadsafe`. This is the
        case the CLI bootstrap uses: the dashboard server lives on one
        loop, the user's ``asyncio.run(main())`` lives on another, and
        the sampler must observe the latter — that's where the
        ``time.sleep`` blocks the user cares about happen.

        The async signature is preserved (no API churn for existing
        callers), but the actual await yields immediately when binding
        to a foreign loop — the cadence task spins up on the target's
        next tick, not while this coroutine is still running.
        """
        if self.is_running:
            return
        if self._interval_ns <= 0:
            raise RuntimeError("LagScheduler.configure() must be called before start()")
        target_loop = loop or asyncio.get_running_loop()

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop is target_loop:
            # Same-loop path — no thread bridging needed.
            self._stop_event = asyncio.Event()
            self._sample_index = 0
            self._task = target_loop.create_task(
                self._run(),
                name="asyncviz-lag-scheduler",
            )
            return

        # Cross-loop / cross-thread bind. ``asyncio.Event`` and
        # ``create_task`` are both loop-bound — they MUST be created
        # on the target loop, not on the caller's loop. We hop over via
        # ``call_soon_threadsafe`` and synchronize via a
        # :class:`concurrent.futures.Future` so the caller knows when
        # the cadence task is live.
        import concurrent.futures

        ready: concurrent.futures.Future[None] = concurrent.futures.Future()

        def _create_on_target_loop() -> None:
            try:
                self._stop_event = asyncio.Event()
                self._sample_index = 0
                self._task = target_loop.create_task(
                    self._run(),
                    name="asyncviz-lag-scheduler",
                )
                ready.set_result(None)
            except BaseException as exc:
                ready.set_exception(exc)

        target_loop.call_soon_threadsafe(_create_on_target_loop)
        # Block briefly for the create to complete. We can't ``await``
        # a ``concurrent.futures.Future`` from an unknown caller loop
        # without bridging adapters; wrap with ``asyncio.wrap_future``
        # if we're inside an asyncio context, else block synchronously.
        if current_loop is not None:
            await asyncio.wrap_future(ready)
        else:
            ready.result(timeout=5.0)

    async def stop(self) -> None:
        """Cancel the cadence task and await its completion. Idempotent.

        Handles the cross-loop case introduced by ``start(loop=...)``:
        when the cadence task lives on a different loop than the
        caller, both ``Event.set`` and ``Task.cancel`` must be invoked
        on the cadence task's loop via ``call_soon_threadsafe``. The
        await uses :func:`asyncio.wrap_future` to bridge back to the
        caller's loop.
        """
        if self._task is None:
            return

        task = self._task
        stop_event = self._stop_event
        task_loop = task.get_loop()
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        same_loop = current_loop is task_loop

        if same_loop:
            if stop_event is not None:
                stop_event.set()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        else:
            import concurrent.futures

            done: concurrent.futures.Future[None] = concurrent.futures.Future()

            def _cancel_on_task_loop() -> None:
                if stop_event is not None:
                    stop_event.set()
                task.cancel()
                # ``add_done_callback`` fires after the task transitions
                # to DONE on its own loop. We surface that to the caller
                # via the bridging future.
                task.add_done_callback(lambda _t: done.set_result(None))

            task_loop.call_soon_threadsafe(_cancel_on_task_loop)
            if current_loop is not None:
                await asyncio.wrap_future(done)
            else:
                done.result(timeout=5.0)

        self._task = None
        self._stop_event = None

    async def _run(self) -> None:
        """The cadence loop.

        Each iteration:
          1. compute next deadline = previous + interval.
          2. sleep until now == deadline (using monotonic-derived delay).
          3. sample once.
          4. if the sample is more than one interval late, account for
             the missed deadlines + advance past them.
        """
        assert self._stop_event is not None  # set in start()
        # Anchor the first deadline at "one interval from now". This
        # gives the loop a sane starting point and matches the test
        # fakes' semantics (first wake = interval after start).
        previous_deadline = self._clock.now_ns() + self._interval_ns

        try:
            while not self._stop_event.is_set():
                interval_ns = self._interval_ns  # snapshot for reconfigure-safety
                # ``previous_deadline`` is the target for *this* iteration.
                # Sleep until then (monotonic-corrected).
                now_ns = self._clock.now_ns()
                wait_ns = previous_deadline - now_ns
                if wait_ns > 0:
                    # asyncio.sleep accepts seconds; convert from ns.
                    wait_seconds = wait_ns / 1_000_000_000
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(),
                            timeout=wait_seconds,
                        )
                        # Stop event fired during sleep — exit cleanly.
                        return
                    except TimeoutError:
                        pass  # expected — sleep finished

                request = SampleRequest(
                    sample_index=self._sample_index,
                    scheduled_ns=previous_deadline,
                    interval_ns=interval_ns,
                    runtime_id=self._runtime_id,
                )
                try:
                    measurement = self._sampler.sample(request)
                except Exception:
                    logger.exception("lag sampler raised; skipping sample")
                else:
                    try:
                        self._sample_sink(measurement)
                    except Exception:
                        logger.exception("lag sample sink raised; continuing")
                self._sample_index += 1

                # Account for missed deadlines. If the sample completed
                # well after the next deadline, jump forward and report
                # the gap so observability surfaces the overrun.
                next_deadline = previous_deadline + interval_ns
                overshoot_ns = self._clock.now_ns() - next_deadline
                if overshoot_ns > 0 and interval_ns > 0:
                    missed = overshoot_ns // interval_ns
                    if missed > 0:
                        try:
                            self._drop_sink(int(missed))
                        except Exception:
                            logger.exception("lag drop sink raised; continuing")
                        next_deadline = next_deadline + missed * interval_ns
                previous_deadline = next_deadline
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("lag scheduler crashed")
            raise
