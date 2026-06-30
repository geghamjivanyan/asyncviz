"""Canonical event-loop lag monitor.

Orchestrates the sub-engines:

* :class:`LagClock`         — monotonic time source.
* :class:`LagSampler`       — one-shot measurement maker.
* :class:`LagScheduler`     — asyncio cadence loop.
* :class:`LagThresholds`    — measurement → severity policy.
* :class:`LagStatistics`    — rolling-window aggregation.
* :class:`LagMetrics`       — lifetime counters.
* :class:`LagBackpressure`  — emit-rate self-protection.
* :class:`LagTracer`        — opt-in debug ring.

Public surface:

* :meth:`start` / :meth:`stop`           — lifecycle.
* :meth:`reconfigure`                    — atomic config swap.
* :meth:`apply_measurement`              — synchronous apply hook
  (used by both the scheduler and test code).
* :meth:`subscribe`                      — register a measurement listener.
* :meth:`snapshot`                       — public observability view.
* :meth:`diagnostics_snapshot`           — debug-grade view.

Emission paths:

* Per-sample event   → opt-in via ``emit_measurement_events``.
* Threshold breach  → on by default; cuts into the warning manager
  via the bus.

All emission honors backpressure: when the configured pending cap is
hit, the monitor drops new events and counts the drop in metrics
rather than enqueueing unboundedly.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Callable

from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.monitoring.event_loop.lag_backpressure import LagMonitorBackpressure
from asyncviz.runtime.monitoring.event_loop.lag_clock import (
    LagClock,
    MonotonicClockProtocol,
)
from asyncviz.runtime.monitoring.event_loop.lag_configuration import LagConfiguration
from asyncviz.runtime.monitoring.event_loop.lag_diagnostics import (
    LagDiagnostics,
    LagDiagnosticsSnapshot,
)
from asyncviz.runtime.monitoring.event_loop.lag_events import (
    build_lag_measurement_event,
    build_lag_threshold_breach_event,
)
from asyncviz.runtime.monitoring.event_loop.lag_measurement import LagMeasurement
from asyncviz.runtime.monitoring.event_loop.lag_metrics import LagMetrics
from asyncviz.runtime.monitoring.event_loop.lag_observability import LagSnapshot
from asyncviz.runtime.monitoring.event_loop.lag_sampler import LagSampler
from asyncviz.runtime.monitoring.event_loop.lag_scheduler import LagScheduler
from asyncviz.runtime.monitoring.event_loop.lag_state import (
    LagMonitorLifecycle,
    LagMonitorState,
)
from asyncviz.runtime.monitoring.event_loop.lag_statistics import LagStatistics
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import (
    LagSeverity,
    LagThresholdEvaluation,
)
from asyncviz.runtime.monitoring.event_loop.lag_tracing import LagTracer, LagTraceRecord
from asyncviz.utils.logging import get_logger

logger = get_logger("runtime.monitoring.event_loop.monitor")


#: Synchronous emit callback. The monitor calls this once per emittable
#: event; the integration layer is responsible for queueing it (bus,
#: in-memory ring, whatever). Returning ``True`` means the event was
#: accepted; ``False`` lets the monitor account for the drop without
#: forcing the caller to throw.
EventEmitter = Callable[[RuntimeEvent], bool]

#: Listener fired for every recorded measurement. Listeners are called
#: synchronously after statistics / metrics have been updated, so they
#: see consistent state. Exceptions are caught + logged.
MeasurementListener = Callable[[LagMeasurement, LagThresholdEvaluation], None]


class EventLoopLagMonitor:
    """Canonical runtime-latency detection engine.

    Construct once per runtime, ``start`` from inside the asyncio loop,
    ``stop`` from the shutdown coordinator. Thread-safe for snapshot /
    subscribe / reconfigure; lifecycle methods must be called from the
    monitor's owning loop.

    Integration points:

    * Pass an ``event_emitter`` to publish lag events onto the runtime
      bus / queue. The bootstrap layer wires this to the bus's
      synchronous ``publish``.
    * Pass an ``external_clock`` (the runtime's :class:`RuntimeClock`) so
      emitted events carry the runtime's ``runtime_id``.
    * Pass a ``monotonic_clock`` (defaults to system) so tests can
      inject deterministic time.
    """

    def __init__(
        self,
        *,
        runtime_clock: RuntimeClock | None = None,
        monotonic_clock: MonotonicClockProtocol | None = None,
        configuration: LagConfiguration | None = None,
        event_emitter: EventEmitter | None = None,
    ) -> None:
        self._runtime_clock = runtime_clock or get_runtime_clock()
        self._configuration = configuration or LagConfiguration.default()
        self._event_emitter = event_emitter
        self._lag_clock = LagClock(monotonic_clock)
        self._sampler = LagSampler(self._lag_clock)
        self._statistics = LagStatistics(window=self._configuration.statistics_window)
        self._metrics = LagMetrics()
        self._backpressure = LagMonitorBackpressure(
            capacity=self._configuration.max_pending_events,
        )
        self._tracer = LagTracer(enabled=self._configuration.trace_enabled)
        self._lifecycle = LagMonitorLifecycle()
        self._listeners_lock = threading.Lock()
        self._listeners: dict[int, MeasurementListener] = {}
        self._listener_next_id = 0
        self._last_measurement: LagMeasurement | None = None
        self._scheduler = LagScheduler(
            clock=self._lag_clock,
            sampler=self._sampler,
            sample_sink=self._on_scheduler_sample,
            drop_sink=self._on_scheduler_drops,
            runtime_id=str(self._runtime_clock.runtime_id),
        )
        self._diagnostics = LagDiagnostics(
            statistics=self._statistics,
            metrics=self._metrics,
            backpressure=self._backpressure,
            tracer=self._tracer,
            state_getter=self._get_state,
            configuration_getter=self._get_configuration,
        )

    # ── reads ────────────────────────────────────────────────────────────
    @property
    def state(self) -> LagMonitorState:
        return self._lifecycle.state

    @property
    def is_running(self) -> bool:
        return self._lifecycle.is_running()

    @property
    def configuration(self) -> LagConfiguration:
        return self._configuration

    @property
    def runtime_id(self) -> uuid.UUID:
        return self._runtime_clock.runtime_id

    def _get_state(self) -> LagMonitorState:
        return self._lifecycle.state

    def _get_configuration(self) -> LagConfiguration:
        return self._configuration

    # ── lifecycle ────────────────────────────────────────────────────────
    async def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Spin up the scheduler. Idempotent.

        ``loop`` selects the loop the cadence task lives on. Pass the
        loop you want to *observe* — the sampler measures schedule-to-
        execute latency on that loop, so it sees only that loop's
        blocking calls. When omitted, the scheduler binds to whatever
        loop is calling ``start()`` (legacy / same-loop tests).

        The CLI bootstrap uses the explicit form so the sampler
        observes the user's ``asyncio.run(main())`` loop, not the
        dashboard's uvicorn loop. See
        :func:`asyncviz.cli.runtime.bootstrap_entry` for the
        loop-discovery hook.
        """
        prev = self._lifecycle.mark(LagMonitorState.STARTING)
        if prev is LagMonitorState.RUNNING:
            self._lifecycle.mark(LagMonitorState.RUNNING)
            return
        try:
            interval_ns = self._lag_clock.seconds_to_ns(self._configuration.sample_interval_seconds)
            self._scheduler.configure(interval_ns=interval_ns)
            await self._scheduler.start(loop=loop)
            self._lifecycle.mark(LagMonitorState.RUNNING)
            target_loop_id = id(loop) if loop is not None else "current"
            logger.debug(
                "lag monitor started (interval=%.3fs, thresholds=%s, loop=%s)",
                self._configuration.sample_interval_seconds,
                self._configuration.thresholds.to_dict(),
                target_loop_id,
            )
        except Exception:
            self._lifecycle.mark(LagMonitorState.FAILED)
            logger.exception("lag monitor failed to start")
            raise

    def bind_to_loop_threadsafe(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the monitor against ``loop`` without blocking.

        Designed for the CLI bootstrap's loop-discovery hook. The hook
        fires inside ``asyncio.run``'s "loop construction" phase, which
        means the loop exists but is **not yet running** — any
        synchronous wait for a coroutine on that loop would deadlock.
        So we schedule the start as the first ``call_soon`` on the
        loop and return immediately; once ``run_until_complete`` spins
        the loop up, the scheduled task fires before user code (queued
        FIFO ahead of ``main()``).

        Idempotent at the lifecycle level: re-entry while already
        RUNNING is a no-op (handled inside :meth:`start`).
        """

        def _enqueue_start() -> None:
            # Now on ``loop``. Create the start task so the loop runs
            # it on its first tick.
            try:
                loop.create_task(self.start(loop=loop), name="asyncviz-lag-bootstrap")
            except Exception:
                logger.exception("failed to schedule lag monitor start on target loop")

        loop.call_soon_threadsafe(_enqueue_start)

    async def stop(self) -> None:
        """Stop the scheduler. Idempotent."""
        prev = self._lifecycle.mark(LagMonitorState.STOPPING)
        if prev in (LagMonitorState.IDLE, LagMonitorState.STOPPED):
            self._lifecycle.mark(LagMonitorState.STOPPED)
            return
        try:
            await self._scheduler.stop()
        finally:
            self._lifecycle.mark(LagMonitorState.STOPPED)
            logger.debug("lag monitor stopped")

    def reconfigure(self, configuration: LagConfiguration) -> None:
        """Atomically swap configuration.

        Statistics window and pending-events capacity require rebuild
        of their owning structures; threshold + cadence updates take
        effect on the next sample. Reconfiguring an unstarted monitor
        is fine; reconfiguring a running monitor honors the new
        cadence on the next deadline.
        """
        previous = self._configuration
        if configuration is previous:
            return
        if configuration.statistics_window != previous.statistics_window:
            self._statistics = LagStatistics(window=configuration.statistics_window)
            self._diagnostics = LagDiagnostics(
                statistics=self._statistics,
                metrics=self._metrics,
                backpressure=self._backpressure,
                tracer=self._tracer,
                state_getter=self._get_state,
                configuration_getter=self._get_configuration,
            )
        if configuration.max_pending_events != previous.max_pending_events:
            self._backpressure = LagMonitorBackpressure(
                capacity=configuration.max_pending_events,
            )
            self._diagnostics = LagDiagnostics(
                statistics=self._statistics,
                metrics=self._metrics,
                backpressure=self._backpressure,
                tracer=self._tracer,
                state_getter=self._get_state,
                configuration_getter=self._get_configuration,
            )
        if configuration.trace_enabled and not self._tracer.enabled:
            self._tracer.enable()
        elif not configuration.trace_enabled and self._tracer.enabled:
            self._tracer.disable()
        self._configuration = configuration
        self._metrics.record_reconfiguration()
        if self._scheduler.is_running:
            interval_ns = self._lag_clock.seconds_to_ns(configuration.sample_interval_seconds)
            self._scheduler.configure(interval_ns=interval_ns)
        if self._configuration.trace_enabled:
            self._tracer.record(
                LagTraceRecord(
                    kind="reconfigure",
                    sample_index=-1,
                    monotonic_ns=self._lag_clock.now_ns(),
                    detail=f"window={configuration.statistics_window},"
                    f"interval={configuration.sample_interval_seconds}",
                )
            )

    # ── synchronous apply hook ───────────────────────────────────────────
    def apply_measurement(self, measurement: LagMeasurement) -> LagThresholdEvaluation:
        """Record a measurement against statistics + thresholds.

        Returns the evaluation so test code can assert on it. The
        scheduler calls this synchronously after every sample.
        """
        self._metrics.record_sample_attempted()
        evaluation = self._configuration.thresholds.evaluate(measurement.lag_ns)
        self._statistics.observe(measurement, evaluation.severity)
        self._metrics.record_sample_recorded()
        if evaluation.severity > LagSeverity.NORMAL:
            self._metrics.record_threshold_hit(evaluation.severity)
        self._last_measurement = measurement
        if self._tracer.enabled:
            self._tracer.record(
                LagTraceRecord(
                    kind="sample",
                    sample_index=measurement.sample_index,
                    monotonic_ns=measurement.actual_ns,
                    detail=evaluation.severity.name,
                    lag_ns=measurement.lag_ns,
                )
            )
        self._emit_for_measurement(measurement, evaluation)
        self._notify_listeners(measurement, evaluation)
        return evaluation

    def _emit_for_measurement(
        self,
        measurement: LagMeasurement,
        evaluation: LagThresholdEvaluation,
    ) -> None:
        if self._event_emitter is None:
            return
        config = self._configuration
        if config.emit_measurement_events:
            self._emit_event(
                build_lag_measurement_event(measurement, runtime_id=self._runtime_clock.runtime_id),
                metric_emit=self._metrics.record_measurement_event,
                metric_drop=self._metrics.record_measurement_event_dropped,
                trace_kind="backpressure_denied",
                sample_index=measurement.sample_index,
                lag_ns=measurement.lag_ns,
            )
        if config.emit_threshold_breach_events and evaluation.breached:
            event = build_lag_threshold_breach_event(
                measurement, evaluation, runtime_id=self._runtime_clock.runtime_id
            )
            self._emit_event(
                event,
                metric_emit=self._metrics.record_threshold_breach_event,
                metric_drop=self._metrics.record_measurement_event_dropped,
                trace_kind="threshold_breach",
                sample_index=measurement.sample_index,
                lag_ns=measurement.lag_ns,
            )

    def _emit_event(
        self,
        event: RuntimeEvent,
        *,
        metric_emit: Callable[[], None],
        metric_drop: Callable[[], None],
        trace_kind: str,
        sample_index: int,
        lag_ns: int,
    ) -> None:
        decision = self._backpressure.acquire()
        if not decision.accepted:
            metric_drop()
            if self._tracer.enabled:
                self._tracer.record(
                    LagTraceRecord(
                        kind="backpressure_denied",
                        sample_index=sample_index,
                        monotonic_ns=self._lag_clock.now_ns(),
                        detail=decision.reason,
                        lag_ns=lag_ns,
                    )
                )
            return
        try:
            accepted = bool(self._event_emitter and self._event_emitter(event))
        except Exception:
            logger.exception("lag monitor event emitter raised")
            accepted = False
        finally:
            self._backpressure.release()
        if accepted:
            metric_emit()
            if self._tracer.enabled and trace_kind == "threshold_breach":
                self._tracer.record(
                    LagTraceRecord(
                        kind="threshold_breach",
                        sample_index=sample_index,
                        monotonic_ns=self._lag_clock.now_ns(),
                        detail="emitted",
                        lag_ns=lag_ns,
                    )
                )
        else:
            metric_drop()

    # ── scheduler callbacks ──────────────────────────────────────────────
    def _on_scheduler_sample(self, measurement: LagMeasurement) -> None:
        self._metrics.record_sampler_invocation()
        try:
            self.apply_measurement(measurement)
        except Exception:
            self._metrics.record_sampler_failure()
            logger.exception("lag monitor apply_measurement raised")

    def _on_scheduler_drops(self, count: int) -> None:
        for _ in range(count):
            self._metrics.record_sample_dropped()
            self._metrics.record_scheduler_drift(
                self._lag_clock.seconds_to_ns(self._configuration.sample_interval_seconds)
            )
            if self._tracer.enabled:
                self._tracer.record(
                    LagTraceRecord(
                        kind="drop",
                        sample_index=-1,
                        monotonic_ns=self._lag_clock.now_ns(),
                        detail="missed_deadline",
                    )
                )

    # ── listeners ────────────────────────────────────────────────────────
    def subscribe(self, listener: MeasurementListener) -> int:
        """Register ``listener``; returns an id usable with :meth:`unsubscribe`."""
        with self._listeners_lock:
            self._listener_next_id += 1
            sid = self._listener_next_id
            self._listeners[sid] = listener
        return sid

    def unsubscribe(self, subscription_id: int) -> bool:
        with self._listeners_lock:
            return self._listeners.pop(subscription_id, None) is not None

    def _notify_listeners(
        self,
        measurement: LagMeasurement,
        evaluation: LagThresholdEvaluation,
    ) -> None:
        with self._listeners_lock:
            listeners = list(self._listeners.values())
        for listener in listeners:
            try:
                listener(measurement, evaluation)
            except Exception:
                logger.exception("lag monitor listener raised; continuing")

    # ── snapshots ────────────────────────────────────────────────────────
    def snapshot(self) -> LagSnapshot:
        return LagSnapshot(
            runtime_id=str(self._runtime_clock.runtime_id),
            state=self._lifecycle.state,
            generated_at_monotonic_ns=self._lag_clock.now_ns(),
            statistics=self._statistics.snapshot(),
            metrics=self._metrics.snapshot(),
            last_measurement=self._last_measurement,
            configuration=self._configuration.to_dict(),
        )

    def diagnostics_snapshot(self) -> LagDiagnosticsSnapshot:
        return self._diagnostics.snapshot()

    def metrics_snapshot(self):
        return self._metrics.snapshot()

    def statistics_snapshot(self):
        return self._statistics.snapshot()

    # ── helpers for test code ────────────────────────────────────────────
    @property
    def scheduler(self) -> LagScheduler:
        return self._scheduler

    @property
    def sampler(self) -> LagSampler:
        return self._sampler

    @property
    def clock(self) -> LagClock:
        return self._lag_clock


async def run_monitor_for(monitor: EventLoopLagMonitor, *, seconds: float) -> None:
    """Test helper — run the monitor for a bounded duration."""
    await monitor.start()
    try:
        await asyncio.sleep(seconds)
    finally:
        await monitor.stop()
