"""Canonical runtime shutdown orchestrator.

The :class:`RuntimeShutdownCoordinator` is the single place where the
dashboard's teardown sequence lives. Previously this logic was spread
across the lifespan's ``finally`` block; centralizing it gives us:

* deterministic phase ordering with observable transitions
* per-step timeout escalation with a global budget cap
* websocket-friendly notification + drain
* replay-safe final checkpoint + snapshot capture
* a structured :class:`ShutdownReport` for postmortem inspection

The coordinator is async — it runs on the dashboard's event loop and
hands off control between phases via ``asyncio.wait_for``. Each phase
catches its own exceptions and records them in the report rather than
escalating, so a misbehaving subsystem doesn't take down the rest of
the sequence.
"""

from __future__ import annotations

import asyncio
import contextlib
from time import monotonic_ns
from typing import TYPE_CHECKING

from asyncviz.dashboard.websocket.protocol import system_status
from asyncviz.dashboard.websocket.shutdown_filter import (
    install_shutdown_exception_filter,
)
from asyncviz.runtime.shutdown.exceptions import (
    ShutdownAlreadyRunningError,
    ShutdownNotCompletedError,
)
from asyncviz.runtime.shutdown.metrics import (
    PhaseTiming,
    ShutdownMetrics,
    ShutdownReport,
)
from asyncviz.runtime.shutdown.status import ShutdownPhase, is_in_progress, is_terminal
from asyncviz.runtime.shutdown.timeouts import ShutdownTimeouts
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.dashboard.snapshots import SnapshotService
    from asyncviz.dashboard.state.runtime_state import RuntimeState
    from asyncviz.dashboard.websocket.bridge import WebSocketBridge
    from asyncviz.dashboard.websocket.manager import ConnectionManager
    from asyncviz.dashboard.websocket.streaming import RuntimeStreamingEngine
    from asyncviz.instrumentation.asyncio import AsyncioPatcher
    from asyncviz.runtime.events import EventBus
    from asyncviz.runtime.monitoring import (
        BlockingStackCaptureEngine,
        BlockingThresholdDetector,
        EventLoopLagMonitor,
    )
    from asyncviz.runtime.queue import InternalEventQueue
    from asyncviz.runtime.replay import EventReplayBuffer
    from asyncviz.runtime.state import RuntimeStateStore
    from asyncviz.runtime.tasks import TaskRegistry
    from asyncviz.runtime.warnings.blocking import BlockingWarningEmitter

logger = get_logger("runtime.shutdown.coordinator")


class RuntimeShutdownCoordinator:
    """Centralized teardown sequencer for the dashboard runtime.

    Usage:

        coordinator = RuntimeShutdownCoordinator(...)
        # ...lifespan runs the runtime...
        await coordinator.run(reason="lifespan")

    Public surface:

    * :meth:`request_shutdown` — idempotent; sets phase to ``DRAINING``
      and records the trigger reason. Used by signal handlers /
      programmatic shutdown.
    * :meth:`run` — async; executes every phase in order. Safe to call
      multiple times only when the prior call has reached a terminal
      phase; otherwise raises :class:`ShutdownAlreadyRunningError`.
    * :attr:`phase` — current :class:`ShutdownPhase`.
    * :meth:`metrics_snapshot` — live counter snapshot.
    * :meth:`report` — final report (raises before terminal phase).
    """

    def __init__(
        self,
        *,
        runtime_state: RuntimeState,
        websocket_manager: ConnectionManager,
        websocket_bridge: WebSocketBridge,
        streaming_engine: RuntimeStreamingEngine,
        event_bus: EventBus,
        event_queue: InternalEventQueue,
        task_registry: TaskRegistry,
        state_store: RuntimeStateStore,
        replay_buffer: EventReplayBuffer,
        snapshot_service: SnapshotService,
        patcher: AsyncioPatcher,
        lag_monitor: EventLoopLagMonitor | None = None,
        blocking_detector: BlockingThresholdDetector | None = None,
        stack_capture_engine: BlockingStackCaptureEngine | None = None,
        blocking_warning_emitter: BlockingWarningEmitter | None = None,
        timeouts: ShutdownTimeouts | None = None,
    ) -> None:
        self._runtime_state = runtime_state
        self._ws_manager = websocket_manager
        self._bridge = websocket_bridge
        self._streaming = streaming_engine
        self._event_bus = event_bus
        self._event_queue = event_queue
        self._task_registry = task_registry
        self._state_store = state_store
        self._replay_buffer = replay_buffer
        self._snapshot_service = snapshot_service
        self._patcher = patcher
        self._lag_monitor = lag_monitor
        self._blocking_detector = blocking_detector
        self._stack_capture_engine = stack_capture_engine
        self._blocking_warning_emitter = blocking_warning_emitter
        self._timeouts = timeouts or ShutdownTimeouts()

        self._phase: ShutdownPhase = ShutdownPhase.IDLE
        self._metrics = ShutdownMetrics()
        self._lock = asyncio.Lock()
        self._reason: str | None = None
        self._triggered_at_monotonic_ns: int = 0
        self._report: ShutdownReport | None = None
        self._running: bool = False

        # Step-result accumulators. Reset on each ``run()``; visible in
        # the final report.
        self._phase_timings: list[PhaseTiming] = []
        self._timeouts_total: int = 0
        self._forced_disconnects: int = 0
        self._forced_cancellations: int = 0
        self._checkpoint_id: str | None = None
        self._snapshot_id: str | None = None
        self._final_sequence: int | None = None
        self._errors: list[str] = []

    # ── identity ─────────────────────────────────────────────────────
    @property
    def phase(self) -> ShutdownPhase:
        return self._phase

    @property
    def is_requested(self) -> bool:
        return self._phase is not ShutdownPhase.IDLE

    @property
    def is_in_progress(self) -> bool:
        return is_in_progress(self._phase)

    @property
    def is_completed(self) -> bool:
        return is_terminal(self._phase)

    @property
    def timeouts(self) -> ShutdownTimeouts:
        return self._timeouts

    def metrics_snapshot(self):
        return self._metrics.snapshot()

    def report(self) -> ShutdownReport:
        """Return the final :class:`ShutdownReport`.

        Raises :class:`ShutdownNotCompletedError` until the coordinator
        reaches ``STOPPED`` or ``FAILED``.
        """
        if self._report is None:
            raise ShutdownNotCompletedError(
                f"shutdown report unavailable in phase {self._phase.value!r}"
            )
        return self._report

    def maybe_report(self) -> ShutdownReport | None:
        """Like :meth:`report` but returns ``None`` instead of raising.

        Used by the status endpoint, which has to handle mid-shutdown
        states gracefully.
        """
        return self._report

    # ── external triggering ──────────────────────────────────────────
    def request_shutdown(self, *, reason: str = "external") -> None:
        """Record a shutdown request. Idempotent.

        Sets the trigger reason + timestamp the first time it's called.
        Subsequent calls during an active shutdown are silently
        ignored — orchestrators that send SIGTERM twice should not
        cause a double-teardown.
        """
        if self._phase is not ShutdownPhase.IDLE:
            logger.debug(
                "shutdown already requested (phase=%s); ignoring duplicate trigger",
                self._phase.value,
            )
            return
        self._reason = reason
        self._triggered_at_monotonic_ns = monotonic_ns()
        self._set_phase(ShutdownPhase.DRAINING)
        self._metrics.record_request()
        logger.info("shutdown requested (reason=%s)", reason)

    # ── core run loop ────────────────────────────────────────────────
    async def run(self, *, reason: str = "lifespan") -> ShutdownReport:
        """Run the full shutdown sequence.

        Safe to call exactly once per coordinator instance. Re-entry
        while a previous ``run`` is in flight raises
        :class:`ShutdownAlreadyRunningError`. After a terminal phase,
        the coordinator becomes read-only.
        """
        if self._running:
            raise ShutdownAlreadyRunningError("shutdown is already in progress")
        if self.is_completed:
            assert self._report is not None
            return self._report

        # Claim the flag synchronously BEFORE awaiting the lock. Two
        # concurrent ``run`` calls would otherwise both pass the check
        # above and only serialize on the lock.
        self._running = True
        async with self._lock:
            try:
                if self._phase is ShutdownPhase.IDLE:
                    self.request_shutdown(reason=reason)

                # Begin shutdown attribution so any cancellations
                # fired by the phases below get tagged as ``"shutdown"``
                # rather than ``"explicit"``.
                self._patcher.cancellation_context.begin_shutdown()
                # The websocket layer has inherent close-race noise
                # during teardown — uvicorn's transfer-data task can
                # collect a ``ConnectionClosedError`` after the route
                # handler has already returned, asyncio reports it as
                # "Task exception was never retrieved", and stderr
                # gets a traceback that worries operators who did
                # nothing wrong. The filter swallows the recognized
                # graceful-close artefacts; anything outside that set
                # still hits the default handler. Scoped to the
                # shutdown window so normal operation is unaffected.
                with install_shutdown_exception_filter() as ws_filter:
                    try:
                        if self._timeouts.total_seconds is not None:
                            await asyncio.wait_for(
                                self._run_phases(),
                                timeout=self._timeouts.total_seconds,
                            )
                        else:
                            await self._run_phases()
                        final_phase = ShutdownPhase.STOPPED
                    except TimeoutError:
                        self._timeouts_total += 1
                        self._errors.append("total shutdown budget exceeded")
                        logger.warning(
                            "shutdown exceeded total budget of %.2fs; finalizing as FAILED",
                            self._timeouts.total_seconds,
                        )
                        final_phase = ShutdownPhase.FAILED
                    except Exception as exc:
                        self._errors.append(f"unexpected: {type(exc).__name__}: {exc}")
                        logger.exception("shutdown raised unexpectedly")
                        final_phase = ShutdownPhase.FAILED
                    finally:
                        # ``end_shutdown`` ALWAYS fires; otherwise future
                        # task cancellations would still be tagged as
                        # ``"shutdown"``.
                        with contextlib.suppress(Exception):
                            self._patcher.cancellation_context.end_shutdown()
                logger.debug(
                    "websocket shutdown filter: suppressed=%d forwarded=%d",
                    ws_filter.suppressed,
                    ws_filter.forwarded,
                )

                self._finalize(final_phase)
                assert self._report is not None
                return self._report
            finally:
                self._running = False

    async def _run_phases(self) -> None:
        """Execute the canonical phase sequence."""
        await self._drain_phase()
        await self._finalize_phase()
        await self._stopping_phase()

    # ── phase 1: DRAINING ────────────────────────────────────────────
    async def _drain_phase(self) -> None:
        """Notify websocket clients + flush in-flight events.

        Sends one ``system_status`` envelope with
        ``runtime_status="shutting_down"``, waits a short notification
        window so connected clients can read it, then drives the
        event-bus / queue / bridge to a quiescent state.
        """
        self._set_phase(ShutdownPhase.DRAINING)
        started_ns = monotonic_ns()
        timed_out = False

        try:
            await asyncio.wait_for(
                self._notify_and_drain(),
                timeout=self._timeouts.drain_seconds,
            )
        except TimeoutError:
            timed_out = True
            self._timeouts_total += 1
            logger.warning(
                "drain phase hit %.2fs timeout; escalating to forced disconnect",
                self._timeouts.drain_seconds,
            )

        self._phase_timings.append(
            PhaseTiming(
                phase=ShutdownPhase.DRAINING,
                duration_ns=monotonic_ns() - started_ns,
                timed_out=timed_out,
            )
        )

    async def _notify_and_drain(self) -> None:
        # Skip the notification + sleep when there's nothing listening.
        # Tests + scripts that exit immediately without ever opening a
        # websocket should not pay the notification-window latency.
        client_count = self._ws_manager.client_count
        if client_count > 0:
            envelope = system_status(runtime_status="shutting_down", debug=False)
            try:
                await self._ws_manager.broadcast(envelope)
            except Exception as exc:
                logger.warning("shutdown notification broadcast failed: %s", exc)
                self._errors.append(f"notify: {exc}")
            # Brief window so connected clients can render the notice
            # before the bridge stops sending.
            await asyncio.sleep(self._timeouts.notification_window_seconds)

        # Drain in-flight events. ``join()`` waits for the dispatcher
        # to clear the queue. We attempt it before stopping the queue
        # so retained-window semantics stay consistent.
        with contextlib.suppress(Exception):
            await self._event_queue.join()

    # ── phase 2: FINALIZING ──────────────────────────────────────────
    async def _finalize_phase(self) -> None:
        """Capture a final replay checkpoint + snapshot.

        Done after drain so the captured artifacts reflect every
        event that made it through. Used by reconnecting clients and
        offline debugging tools to bootstrap from the last known
        clean state.
        """
        self._set_phase(ShutdownPhase.FINALIZING)
        started_ns = monotonic_ns()
        timed_out = False

        try:
            await asyncio.wait_for(
                self._capture_final_artifacts(),
                timeout=self._timeouts.finalize_seconds,
            )
        except TimeoutError:
            timed_out = True
            self._timeouts_total += 1
            self._errors.append("finalize: timeout")
            logger.warning(
                "finalize phase hit %.2fs timeout; skipping final artifacts",
                self._timeouts.finalize_seconds,
            )

        self._phase_timings.append(
            PhaseTiming(
                phase=ShutdownPhase.FINALIZING,
                duration_ns=monotonic_ns() - started_ns,
                timed_out=timed_out,
            )
        )

    async def _capture_final_artifacts(self) -> None:
        # Replay checkpoint pins the current sequence cursor and
        # carries the full state snapshot, so a reconnecting client
        # can fast-forward from anywhere inside retention.
        try:
            checkpoint = self._replay_buffer.create_checkpoint(
                label="shutdown",
                state_store=self._state_store,
            )
            self._checkpoint_id = checkpoint.checkpoint_id
            self._final_sequence = checkpoint.sequence
        except Exception as exc:
            logger.warning("final checkpoint capture failed: %s", exc)
            self._errors.append(f"checkpoint: {exc}")

        # Final canonical snapshot — same shape ``/api/runtime/snapshot``
        # serves, captured here so post-shutdown tools can read it.
        try:
            snapshot = self._snapshot_service.capture()
            self._snapshot_id = snapshot.metadata.snapshot_id
            if self._final_sequence is None:
                self._final_sequence = snapshot.consistency.last_sequence
        except Exception as exc:
            logger.warning("final snapshot capture failed: %s", exc)
            self._errors.append(f"snapshot: {exc}")

    # ── phase 3: STOPPING ────────────────────────────────────────────
    async def _stopping_phase(self) -> None:
        """Tear down services in the canonical order.

        Order matters and reflects dependency directions:

        1. Unpatch instrumentation — stops new events from being
           produced. The cancellation context is still in
           ``begin_shutdown`` so any task that cancels right now is
           attributed correctly.
        2. Stop the streaming engine + websocket bridge — stops
           outgoing fanout before the queue stops draining.
        3. Unsubscribe state-store listeners — replay, warnings,
           metrics, timeline. Done before stopping the bus so any
           still-queued ``StateChange`` notifications drain through
           a registered handler.
        4. Stop the event bus, then the queue, then the task
           registry — bus delegates to the queue, so the queue must
           outlive the bus by one beat.
        5. Disconnect websocket clients — graceful close after every
           upstream is quiet.
        """
        self._set_phase(ShutdownPhase.STOPPING)
        started_ns = monotonic_ns()
        timed_out = False

        try:
            await asyncio.wait_for(
                self._stop_services(),
                timeout=self._timeouts.stop_seconds,
            )
        except TimeoutError:
            timed_out = True
            self._timeouts_total += 1
            self._errors.append("stop: timeout")
            logger.warning(
                "stop phase hit %.2fs timeout; forcing client disconnect",
                self._timeouts.stop_seconds,
            )
            await self._force_disconnect_all()

        self._phase_timings.append(
            PhaseTiming(
                phase=ShutdownPhase.STOPPING,
                duration_ns=monotonic_ns() - started_ns,
                timed_out=timed_out,
            )
        )

    async def _stop_services(self) -> None:
        """Run the deterministic service-stop sequence."""
        # Unpatch first — no new events.
        with contextlib.suppress(Exception):
            if self._patcher.is_patched:
                self._patcher.unpatch()
        # Queue patcher (best-effort; may not be registered on every shape).
        queue_patcher = getattr(self, "_queue_patcher", None)
        if queue_patcher is not None:
            with contextlib.suppress(Exception):
                if queue_patcher.is_patched:
                    queue_patcher.unpatch()

        # Semaphore patcher — best-effort, same pattern as the queue one.
        semaphore_patcher = getattr(self, "_semaphore_patcher", None)
        if semaphore_patcher is not None:
            with contextlib.suppress(Exception):
                if semaphore_patcher.is_patched:
                    semaphore_patcher.unpatch()

        # Gather patcher — restore ``asyncio.gather`` before the bus
        # stops so the dispatcher's own gather call no longer sees the
        # instrumented wrapper during the final drain.
        gather_patcher = getattr(self, "_gather_patcher", None)
        if gather_patcher is not None:
            with contextlib.suppress(Exception):
                if gather_patcher.is_patched:
                    gather_patcher.unpatch()

        # Executor patcher — restore ``BaseEventLoop.run_in_executor``
        # before the bus stops so in-flight done callbacks no longer
        # try to emit events on the way down.
        executor_patcher = getattr(self, "_executor_patcher", None)
        if executor_patcher is not None:
            with contextlib.suppress(Exception):
                if executor_patcher.is_patched:
                    executor_patcher.unpatch()

        # Queue metrics engine — unsubscribe before the bus stops so the
        # dispatcher doesn't hand it a final event after teardown began.
        queue_metrics_engine = getattr(self, "_queue_metrics_engine", None)
        if queue_metrics_engine is not None:
            with contextlib.suppress(Exception):
                queue_metrics_engine.stop()

        # Executor metrics engine — same pattern as the queue metrics
        # engine. Stop unsubscribes from the bus.
        executor_metrics_engine = getattr(self, "_executor_metrics_engine", None)
        if executor_metrics_engine is not None:
            with contextlib.suppress(Exception):
                executor_metrics_engine.stop()

        # Stop the blocking warning emitter first — it subscribes to
        # the detector + capture engine and publishes through the bus.
        # Closing it first means downstream engines stop receiving its
        # listener callbacks before they themselves shut down.
        if self._blocking_warning_emitter is not None:
            with contextlib.suppress(Exception):
                await self._blocking_warning_emitter.stop()

        # Stop the stack-capture engine next — it subscribes to the
        # blocking detector and emits through the bus. Once the
        # detector / bus stop, late captures would otherwise log
        # spurious "publish failed" lines.
        if self._stack_capture_engine is not None:
            with contextlib.suppress(Exception):
                await self._stack_capture_engine.stop()

        # Stop the blocking detector next so it stops consuming the lag
        # monitor's samples (and emitting violation events) before either
        # of those subsystems goes away. ``stop()`` also unbinds the
        # monitor subscription and closes any open window.
        if self._blocking_detector is not None:
            with contextlib.suppress(Exception):
                await self._blocking_detector.stop()

        # Stop the lag monitor before anything else that produces events.
        # The monitor publishes through the bus; once the bus stops we'd
        # see spurious "publish failed" counters.
        if self._lag_monitor is not None:
            with contextlib.suppress(Exception):
                await self._lag_monitor.stop()

        # Outgoing fanout off.
        with contextlib.suppress(Exception):
            self._streaming.stop()

        with contextlib.suppress(Exception):
            await self._bridge.stop()

        # Event bus + queue.
        with contextlib.suppress(Exception):
            await self._event_bus.stop()
        with contextlib.suppress(Exception):
            await self._event_queue.stop()
        with contextlib.suppress(Exception):
            await self._task_registry.stop()

        # Final disconnect — best-effort.
        await self._force_disconnect_all()

    async def _force_disconnect_all(self) -> None:
        client_count = self._ws_manager.client_count
        with contextlib.suppress(Exception):
            await self._ws_manager.disconnect_all()
        if client_count:
            self._forced_disconnects += client_count

    # ── finalize ─────────────────────────────────────────────────────
    def _finalize(self, final_phase: ShutdownPhase) -> None:
        """Record the terminal phase + assemble the report."""
        self._set_phase(final_phase)
        finished_at = monotonic_ns()
        report = ShutdownReport(
            final_phase=final_phase,
            reason=self._reason or "unknown",
            triggered_at_monotonic_ns=self._triggered_at_monotonic_ns,
            finished_at_monotonic_ns=finished_at,
            total_duration_ns=finished_at - (self._triggered_at_monotonic_ns or finished_at),
            phase_timings=tuple(self._phase_timings),
            timeouts_total=self._timeouts_total,
            forced_disconnects=self._forced_disconnects,
            forced_cancellations=self._forced_cancellations,
            checkpoint_id=self._checkpoint_id,
            snapshot_id=self._snapshot_id,
            final_sequence=self._final_sequence,
            errors=tuple(self._errors),
        )
        self._report = report
        self._metrics.record_completion(report)
        # ``RuntimeState`` lifecycle — mark stopped as the absolute
        # last side effect so the readiness probe transitions cleanly.
        with contextlib.suppress(Exception):
            self._runtime_state.mark_stopped()
        logger.info(
            "shutdown finished phase=%s duration_ns=%d errors=%d",
            final_phase.value,
            report.total_duration_ns,
            len(report.errors),
        )

    # ── internals ────────────────────────────────────────────────────
    def _set_phase(self, phase: ShutdownPhase) -> None:
        self._phase = phase
        self._metrics.set_phase(phase)
