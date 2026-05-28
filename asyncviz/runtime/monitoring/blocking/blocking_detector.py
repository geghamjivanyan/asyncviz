"""Canonical blocking-threshold detector.

Orchestrates:

* :class:`BlockingClassifier`            — lag severity → blocking severity.
* :class:`EscalationEngine`              — consecutive-violation pressure.
* :class:`BlockingWindowTracker`         — open/extend/close windows.
* :class:`BlockingCooldownPolicy`        — per-severity dedup.
* :class:`BlockingStatistics`            — lifetime window stats.
* :class:`BlockingMetrics`               — lifetime self-metrics.
* :class:`BlockingDetectorBackpressure`  — bounded emit.
* :class:`BlockingTracer`                — opt-in debug ring.

Public surface:

* :meth:`start` / :meth:`stop`              — lifecycle (mirrors monitor).
* :meth:`bind_to_monitor`                   — subscribe to lag monitor
  (returned id is usable for unsubscribe).
* :meth:`unbind_from_monitor`               — drop the subscription.
* :meth:`reconfigure`                       — atomic config swap.
* :meth:`process`                           — synchronous apply hook
  (used by both the monitor subscription and replay).
* :meth:`snapshot`                          — public observability view.
* :meth:`diagnostics_snapshot`              — debug-grade view.
* :meth:`subscribe` / :meth:`unsubscribe`   — local listener API.

Emission paths run through the configured ``event_emitter`` (typically
:meth:`EventBus.publish`). All three event categories honor backpressure
+ cooldowns + handler exceptions; metrics record the outcome either way.

The detector reads no clock for control flow — every cooldown / window
decision is driven by the *measurement's* ``actual_ns``. This keeps
the entire pipeline replay-safe.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Callable

from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.monitoring.blocking.blocking_backpressure import (
    BlockingDetectorBackpressure,
)
from asyncviz.runtime.monitoring.blocking.blocking_classifier import (
    BlockingClassification,
    BlockingClassifier,
    BlockingSeverity,
)
from asyncviz.runtime.monitoring.blocking.blocking_configuration import (
    BlockingDetectorConfiguration,
)
from asyncviz.runtime.monitoring.blocking.blocking_cooldown import (
    BlockingCooldownPolicy,
    CooldownDecision,
)
from asyncviz.runtime.monitoring.blocking.blocking_diagnostics import (
    BlockingDiagnostics,
    BlockingDiagnosticsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.blocking_escalation import (
    EscalationEngine,
    EscalationOutcome,
)
from asyncviz.runtime.monitoring.blocking.blocking_events import (
    build_blocking_escalation_event,
    build_blocking_violation_event,
    build_blocking_window_closed_event,
    build_blocking_window_opened_event,
)
from asyncviz.runtime.monitoring.blocking.blocking_metrics import BlockingMetrics
from asyncviz.runtime.monitoring.blocking.blocking_observability import BlockingSnapshot
from asyncviz.runtime.monitoring.blocking.blocking_state import (
    BlockingDetectorLifecycle,
    BlockingDetectorState,
)
from asyncviz.runtime.monitoring.blocking.blocking_statistics import BlockingStatistics
from asyncviz.runtime.monitoring.blocking.blocking_tracing import (
    BlockingTracer,
    BlockingTraceRecord,
)
from asyncviz.runtime.monitoring.blocking.blocking_windows import (
    BlockingWindowSnapshot,
    BlockingWindowTracker,
    WindowTransition,
)
from asyncviz.runtime.monitoring.event_loop.lag_measurement import LagMeasurement
from asyncviz.runtime.monitoring.event_loop.lag_monitor import EventLoopLagMonitor
from asyncviz.runtime.monitoring.event_loop.lag_thresholds import LagThresholdEvaluation
from asyncviz.utils.logging import get_logger

logger = get_logger("runtime.monitoring.blocking.detector")


#: Same shape as the lag monitor's emitter. The integration layer wires
#: this to ``EventBus.publish``; ``True`` means the bus accepted.
EventEmitter = Callable[[RuntimeEvent], bool]

#: Listener fired for every processed (measurement, evaluation) pair —
#: regardless of whether it was a violation. Receives the full
#: :class:`DetectionOutcome`. Listener exceptions are caught + counted.
DetectionListener = Callable[["DetectionOutcome"], None]


class DetectionOutcome:
    """The detector's per-sample report. Returned by :meth:`process`.

    A *value type* — fields are read-only after construction; callers
    can stash it in caches without aliasing risk. Mutable construction
    is fine because the orchestrator builds it on the stack.
    """

    __slots__ = (
        "classification",
        "cooldown",
        "is_violation",
        "outcome",
        "transition",
        "violation_emitted",
        "window_transition",
    )

    def __init__(
        self,
        *,
        classification: BlockingClassification,
        outcome: EscalationOutcome,
        is_violation: bool,
        cooldown: CooldownDecision,
        window_transition: WindowTransition,
        violation_emitted: bool,
    ) -> None:
        self.classification = classification
        self.outcome = outcome
        self.is_violation = is_violation
        self.cooldown = cooldown
        self.transition = window_transition  # legacy alias
        self.window_transition = window_transition
        self.violation_emitted = violation_emitted

    @property
    def effective_severity(self) -> BlockingSeverity:
        return self.outcome.effective_severity

    @property
    def escalated(self) -> bool:
        return self.outcome.escalated


class BlockingThresholdDetector:
    """Canonical blocking-detection orchestrator.

    Construct once per runtime, ``start`` from inside the asyncio loop
    once the lag monitor + bus are ready, ``stop`` from the shutdown
    coordinator.

    Integration:

    * Pass an ``event_emitter`` to publish onto the bus.
    * Pass a ``runtime_clock`` so emitted events get the right
      ``runtime_id``.
    * Call :meth:`bind_to_monitor` after both ``start()``s to wire the
      subscription. Future work may move this into ``start()`` itself
      once the bootstrap order is locked in.
    """

    def __init__(
        self,
        *,
        runtime_clock: RuntimeClock | None = None,
        configuration: BlockingDetectorConfiguration | None = None,
        event_emitter: EventEmitter | None = None,
    ) -> None:
        self._runtime_clock = runtime_clock or get_runtime_clock()
        self._configuration = configuration or BlockingDetectorConfiguration.default()
        self._event_emitter = event_emitter
        self._classifier = BlockingClassifier()
        self._escalation = EscalationEngine(self._configuration.thresholds)
        self._windows = BlockingWindowTracker(
            policy=self._configuration.thresholds,
            runtime_id=str(self._runtime_clock.runtime_id),
            history_capacity=self._configuration.window_history_capacity,
        )
        self._cooldowns = BlockingCooldownPolicy(
            warning_ns=self._configuration.cooldown_warning_ns,
            critical_ns=self._configuration.cooldown_critical_ns,
            freeze_ns=self._configuration.cooldown_freeze_ns,
        )
        self._statistics = BlockingStatistics()
        self._metrics = BlockingMetrics()
        self._backpressure = BlockingDetectorBackpressure(
            capacity=self._configuration.max_pending_events,
        )
        self._tracer = BlockingTracer(enabled=self._configuration.trace_enabled)
        self._lifecycle = BlockingDetectorLifecycle()
        self._monitor_subscription_id: int | None = None
        self._bound_monitor: EventLoopLagMonitor | None = None
        self._listeners_lock = threading.Lock()
        self._listeners: dict[int, DetectionListener] = {}
        self._listener_next_id = 0
        self._diagnostics = self._build_diagnostics()

    # ── helpers ──────────────────────────────────────────────────────────
    def _build_diagnostics(self) -> BlockingDiagnostics:
        return BlockingDiagnostics(
            statistics=self._statistics,
            metrics=self._metrics,
            backpressure=self._backpressure,
            tracer=self._tracer,
            windows=self._windows,
            state_getter=self._get_state,
            configuration_getter=self._get_configuration,
        )

    def _get_state(self) -> BlockingDetectorState:
        return self._lifecycle.state

    def _get_configuration(self) -> BlockingDetectorConfiguration:
        return self._configuration

    # ── reads ────────────────────────────────────────────────────────────
    @property
    def state(self) -> BlockingDetectorState:
        return self._lifecycle.state

    @property
    def is_running(self) -> bool:
        return self._lifecycle.is_running()

    @property
    def configuration(self) -> BlockingDetectorConfiguration:
        return self._configuration

    @property
    def runtime_id(self) -> uuid.UUID:
        return self._runtime_clock.runtime_id

    @property
    def bound_monitor(self) -> EventLoopLagMonitor | None:
        return self._bound_monitor

    # ── lifecycle ────────────────────────────────────────────────────────
    async def start(self) -> None:
        prev = self._lifecycle.mark(BlockingDetectorState.STARTING)
        if prev is BlockingDetectorState.RUNNING:
            self._lifecycle.mark(BlockingDetectorState.RUNNING)
            return
        try:
            self._lifecycle.mark(BlockingDetectorState.RUNNING)
            logger.debug("blocking detector started")
        except Exception:
            self._lifecycle.mark(BlockingDetectorState.FAILED)
            logger.exception("blocking detector failed to start")
            raise

    async def stop(self) -> None:
        prev = self._lifecycle.mark(BlockingDetectorState.STOPPING)
        if prev in (BlockingDetectorState.IDLE, BlockingDetectorState.STOPPED):
            self._lifecycle.mark(BlockingDetectorState.STOPPED)
            return
        try:
            # Unbind from the lag monitor so a late-arriving sample
            # doesn't try to enter a half-shut pipeline.
            self.unbind_from_monitor()
            # Close any open window at shutdown so the captured snapshot
            # reflects the final state (with a synthetic close timestamp
            # at the last violation's monotonic_ns).
            now_ns = self._runtime_clock.monotonic_ns()
            closed = self._windows.force_close(monotonic_ns=now_ns)
            if closed is not None:
                self._statistics.observe_window_closed(closed)
                self._metrics.record_window_closed()
                self._emit_window_closed(closed)
        finally:
            self._lifecycle.mark(BlockingDetectorState.STOPPED)
            logger.debug("blocking detector stopped")

    def reconfigure(self, configuration: BlockingDetectorConfiguration) -> None:
        """Atomically swap configuration.

        Sub-engines that own configuration-shaped state are replaced
        when their config changes:

        * ``window_history_capacity`` change → rebuild :class:`BlockingWindowTracker`
          (capacity is fixed at construction). Active window survives
          via :meth:`active_snapshot` re-feed *only* when the policy
          itself is unchanged; otherwise consumers re-read the new
          history via :meth:`snapshot`.
        * cooldowns / thresholds → in-place reconfigure on existing
          sub-engines (counters preserved).
        * trace / backpressure capacity → instance swap as needed.
        """
        previous = self._configuration
        if configuration is previous:
            return
        if configuration.window_history_capacity != previous.window_history_capacity:
            self._windows = BlockingWindowTracker(
                policy=configuration.thresholds,
                runtime_id=str(self._runtime_clock.runtime_id),
                history_capacity=configuration.window_history_capacity,
            )
        else:
            self._windows.configure(configuration.thresholds)
        if configuration.max_pending_events != previous.max_pending_events:
            self._backpressure = BlockingDetectorBackpressure(
                capacity=configuration.max_pending_events,
            )
        self._escalation.configure(configuration.thresholds)
        self._cooldowns.configure(
            warning_ns=configuration.cooldown_warning_ns,
            critical_ns=configuration.cooldown_critical_ns,
            freeze_ns=configuration.cooldown_freeze_ns,
        )
        if configuration.trace_enabled and not self._tracer.enabled:
            self._tracer.enable()
        elif not configuration.trace_enabled and self._tracer.enabled:
            self._tracer.disable()
        self._configuration = configuration
        self._diagnostics = self._build_diagnostics()
        self._metrics.record_reconfiguration()
        if self._tracer.enabled:
            self._tracer.record(
                BlockingTraceRecord(
                    kind="reconfigure",
                    sample_index=-1,
                    monotonic_ns=self._runtime_clock.monotonic_ns(),
                    detail="config_swapped",
                )
            )

    # ── monitor binding ──────────────────────────────────────────────────
    def bind_to_monitor(self, monitor: EventLoopLagMonitor) -> int:
        """Subscribe to ``monitor``'s measurement stream. Returns the sub id."""
        if self._monitor_subscription_id is not None:
            return self._monitor_subscription_id
        self._monitor_subscription_id = monitor.subscribe(self._on_monitor_measurement)
        self._bound_monitor = monitor
        return self._monitor_subscription_id

    def unbind_from_monitor(self) -> bool:
        if self._monitor_subscription_id is None or self._bound_monitor is None:
            return False
        try:
            removed = self._bound_monitor.unsubscribe(self._monitor_subscription_id)
        except Exception:
            removed = False
            logger.exception("blocking detector unbind raised; ignoring")
        self._monitor_subscription_id = None
        self._bound_monitor = None
        return removed

    def _on_monitor_measurement(
        self,
        measurement: LagMeasurement,
        evaluation: LagThresholdEvaluation,
    ) -> None:
        try:
            self.process(measurement, evaluation)
        except Exception:
            self._metrics.record_handler_failure()
            logger.exception("blocking detector process raised; continuing")

    # ── core pipeline ────────────────────────────────────────────────────
    def process(
        self,
        measurement: LagMeasurement,
        evaluation: LagThresholdEvaluation,
    ) -> DetectionOutcome:
        """Run the full pipeline on one (measurement, evaluation).

        Returns the :class:`DetectionOutcome` so test code + future
        replay drivers can assert on the per-sample decisions.
        """
        self._metrics.record_measurement()

        # 1. Classify (pure lookup today; future adaptive baselines hook here).
        classification = self._classifier.classify(measurement, evaluation)
        self._statistics.observe_peak_lag(classification.lag_ns)

        # 2. Escalation pressure.
        outcome = self._escalation.process(classification)

        # 3. Window lifecycle.
        transition = self._windows.process(outcome)
        if transition.opened is not None:
            self._statistics.observe_window_opened()
            self._metrics.record_window_opened()
            self._trace(
                "window_open",
                measurement=measurement,
                detail=transition.opened.window_id,
                severity=outcome.effective_severity,
            )
            self._emit_window_opened(transition.opened, classification)
        if transition.closed is not None:
            self._statistics.observe_window_closed(transition.closed)
            self._metrics.record_window_closed()
            self._trace(
                "window_close",
                measurement=measurement,
                detail=transition.closed.window_id,
            )
            self._emit_window_closed(transition.closed)
        if transition.extended is not None:
            self._trace(
                "window_extend",
                measurement=measurement,
                detail=transition.extended.window_id,
                severity=outcome.effective_severity,
            )

        # 4. Violation accounting + cooldown gating.
        is_violation = self._configuration.thresholds.is_violation(outcome.effective_severity)
        cooldown: CooldownDecision = CooldownDecision(
            severity=outcome.effective_severity,
            suppressed=False,
            remaining_ns=0,
        )
        violation_emitted = False
        if is_violation:
            self._metrics.record_violation(outcome.effective_severity)
            self._trace(
                "classify",
                measurement=measurement,
                detail=outcome.effective_severity.name,
                severity=outcome.effective_severity,
                lag_ns=classification.lag_ns,
            )
            # Escalation event bypasses cooldown — it's a transition,
            # not a sustained signal.
            if outcome.escalated:
                self._metrics.record_escalation(
                    from_severity=outcome.escalation_from,  # type: ignore[arg-type]
                    to_severity=outcome.escalation_to,  # type: ignore[arg-type]
                )
                self._trace(
                    "escalate",
                    measurement=measurement,
                    detail=f"{outcome.escalation_from.name}->{outcome.escalation_to.name}",  # type: ignore[union-attr]
                    severity=outcome.effective_severity,
                )
                self._emit_escalation(outcome, transition.active)
            cooldown = self._cooldowns.check_and_record(
                outcome.effective_severity,
                now_ns=measurement.actual_ns,
            )
            if cooldown.suppressed:
                self._metrics.record_cooldown_suppression(outcome.effective_severity)
                self._trace(
                    "cooldown_suppress",
                    measurement=measurement,
                    detail=f"remaining_ns={cooldown.remaining_ns}",
                    severity=outcome.effective_severity,
                )
            else:
                violation_emitted = self._emit_violation(classification, outcome, transition.active)

        detection = DetectionOutcome(
            classification=classification,
            outcome=outcome,
            is_violation=is_violation,
            cooldown=cooldown,
            window_transition=transition,
            violation_emitted=violation_emitted,
        )
        self._notify_listeners(detection)
        return detection

    # ── emission ─────────────────────────────────────────────────────────
    def _emit_violation(
        self,
        classification: BlockingClassification,
        outcome: EscalationOutcome,
        active_window: BlockingWindowSnapshot | None,
    ) -> bool:
        if not self._configuration.emit_violation_events or self._event_emitter is None:
            return False
        decision = self._backpressure.acquire()
        if not decision.accepted:
            self._metrics.record_violation_event(accepted=False)
            self._trace(
                "backpressure_denied",
                measurement=classification.measurement,
                detail="violation",
                severity=outcome.effective_severity,
            )
            return False
        try:
            event = build_blocking_violation_event(
                classification=classification,
                outcome=outcome,
                active_window=active_window,
                runtime_id=self._runtime_clock.runtime_id,
            )
            accepted = bool(self._event_emitter(event))
        except Exception:
            self._metrics.record_handler_failure()
            logger.exception("blocking violation emitter raised")
            accepted = False
        finally:
            self._backpressure.release()
        self._metrics.record_violation_event(accepted=accepted)
        return accepted

    def _emit_escalation(
        self,
        outcome: EscalationOutcome,
        active_window: BlockingWindowSnapshot | None,
    ) -> None:
        if not self._configuration.emit_escalation_events or self._event_emitter is None:
            return
        decision = self._backpressure.acquire()
        if not decision.accepted:
            self._metrics.record_escalation_event(accepted=False)
            return
        try:
            event = build_blocking_escalation_event(
                outcome=outcome,
                active_window=active_window,
                runtime_id=self._runtime_clock.runtime_id,
            )
            accepted = bool(self._event_emitter(event))
        except Exception:
            self._metrics.record_handler_failure()
            logger.exception("blocking escalation emitter raised")
            accepted = False
        finally:
            self._backpressure.release()
        self._metrics.record_escalation_event(accepted=accepted)

    def _emit_window_opened(
        self,
        window: BlockingWindowSnapshot,
        classification: BlockingClassification,
    ) -> None:
        if not self._configuration.emit_window_events or self._event_emitter is None:
            return
        decision = self._backpressure.acquire()
        if not decision.accepted:
            self._metrics.record_window_event(accepted=False)
            return
        try:
            event = build_blocking_window_opened_event(
                window=window,
                classification=classification,
                runtime_id=self._runtime_clock.runtime_id,
            )
            accepted = bool(self._event_emitter(event))
        except Exception:
            self._metrics.record_handler_failure()
            logger.exception("blocking window-opened emitter raised")
            accepted = False
        finally:
            self._backpressure.release()
        self._metrics.record_window_event(accepted=accepted)

    def _emit_window_closed(self, window: BlockingWindowSnapshot) -> None:
        if not self._configuration.emit_window_events or self._event_emitter is None:
            return
        decision = self._backpressure.acquire()
        if not decision.accepted:
            self._metrics.record_window_event(accepted=False)
            return
        try:
            event = build_blocking_window_closed_event(
                window=window,
                runtime_id=self._runtime_clock.runtime_id,
            )
            accepted = bool(self._event_emitter(event))
        except Exception:
            self._metrics.record_handler_failure()
            logger.exception("blocking window-closed emitter raised")
            accepted = False
        finally:
            self._backpressure.release()
        self._metrics.record_window_event(accepted=accepted)

    # ── listeners ────────────────────────────────────────────────────────
    def subscribe(self, listener: DetectionListener) -> int:
        with self._listeners_lock:
            self._listener_next_id += 1
            sid = self._listener_next_id
            self._listeners[sid] = listener
        return sid

    def unsubscribe(self, subscription_id: int) -> bool:
        with self._listeners_lock:
            return self._listeners.pop(subscription_id, None) is not None

    def _notify_listeners(self, detection: DetectionOutcome) -> None:
        with self._listeners_lock:
            listeners = list(self._listeners.values())
        for listener in listeners:
            try:
                listener(detection)
            except Exception:
                self._metrics.record_handler_failure()
                logger.exception("blocking detector listener raised; continuing")

    # ── snapshots ────────────────────────────────────────────────────────
    def snapshot(self) -> BlockingSnapshot:
        return BlockingSnapshot(
            runtime_id=str(self._runtime_clock.runtime_id),
            state=self._lifecycle.state,
            generated_at_monotonic_ns=self._runtime_clock.monotonic_ns(),
            configuration=self._configuration.to_dict(),
            statistics=self._statistics.snapshot(),
            metrics=self._metrics.snapshot(),
            active_window=self._windows.active_snapshot(),
            recent_windows=self._windows.history_snapshot(),
        )

    def diagnostics_snapshot(self) -> BlockingDiagnosticsSnapshot:
        return self._diagnostics.snapshot()

    def statistics_snapshot(self):
        return self._statistics.snapshot()

    def metrics_snapshot(self):
        return self._metrics.snapshot()

    # ── trace helper ─────────────────────────────────────────────────────
    def _trace(
        self,
        kind,
        *,
        measurement: LagMeasurement,
        detail: str,
        severity: BlockingSeverity | None = None,
        lag_ns: int = 0,
    ) -> None:
        if not self._tracer.enabled:
            return
        self._tracer.record(
            BlockingTraceRecord(
                kind=kind,
                sample_index=measurement.sample_index,
                monotonic_ns=measurement.actual_ns,
                detail=detail,
                severity="" if severity is None else severity.name,
                lag_ns=lag_ns,
            )
        )


async def run_blocking_detector_for(detector: BlockingThresholdDetector, *, seconds: float) -> None:
    """Test helper — run the detector for a bounded duration."""
    await detector.start()
    try:
        await asyncio.sleep(seconds)
    finally:
        await detector.stop()
