"""Canonical blocking stack-frame capture engine.

Orchestrates:

* :class:`StackCapturePolicy`       — when to capture.
* :class:`FrameProvider`            — where frames come from (live / static).
* :class:`StackSampler`             — frame walk + filter.
* :class:`TaskMetadataResolver`     — best-effort asyncio task context.
* :class:`ReentryGuard`             — per-thread recursion safety.
* :class:`StackSerializer`          — deterministic, bounded JSON.
* :class:`StackCaptureBackpressure` — emit-rate self-protection.
* :class:`StackCaptureStatistics`   — lifetime aggregates over captures.
* :class:`StackCaptureMetrics`      — lifetime self-counters.
* :class:`StackCaptureTracer`       — opt-in debug ring.

Public surface:

* :meth:`start` / :meth:`stop`              — lifecycle.
* :meth:`bind_to_detector`                  — subscribe to blocking
  detector outcomes; returns the subscription id.
* :meth:`unbind_from_detector`              — drop the subscription.
* :meth:`on_detection`                      — synchronous apply hook;
  invoked by the detector subscription and by replay tools.
* :meth:`capture_manual`                    — operator-triggered
  capture, bypasses the per-window policy.
* :meth:`reconfigure`                       — atomic config swap.
* :meth:`snapshot`                          — public observability view.
* :meth:`diagnostics_snapshot`              — debug-grade view.

Replay safety: every decision the engine makes is a pure function of
its inputs. The only non-deterministic step is the actual frame walk
(which depends on live runtime state); the engine treats that as a
black-box producer whose output we deterministically serialize.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Callable
from typing import Any

from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.monitoring.blocking.blocking_detector import (
    BlockingThresholdDetector,
    DetectionOutcome,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_backpressure import (
    StackCaptureBackpressure,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_configuration import (
    StackCaptureConfiguration,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_context import (
    ReentryGuard,
    TaskMetadataResolver,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_diagnostics import (
    StackCaptureDiagnostics,
    StackCaptureDiagnosticsSnapshot,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_events import (
    build_stack_capture_event,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_frames import (
    CapturedStack,
    CapturedTaskMetadata,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_metrics import (
    StackCaptureMetrics,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_observability import (
    StackCaptureSnapshot,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_policy import (
    CaptureDecision,
    StackCapturePolicy,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_sampler import (
    FrameProvider,
    LiveFrameProvider,
    StackSampler,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_serializer import (
    StackSerializer,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_statistics import (
    StackCaptureStatistics,
)
from asyncviz.runtime.monitoring.blocking.stack_capture.stack_capture_tracing import (
    StackCaptureTracer,
    StackCaptureTraceRecord,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("runtime.monitoring.blocking.stack_capture.engine")


#: Bus-shaped emitter. ``True`` means the bus accepted.
EventEmitter = Callable[[RuntimeEvent], bool]

#: Engine listener. Fires after the capture is built + stats/metrics
#: are updated; receives the :class:`CapturedStack`. Useful for tests
#: + future in-process consumers (e.g. an inspector panel that wants
#: captures without going through the bus).
CaptureListener = Callable[[CapturedStack], None]


# Engine lifecycle states — mirror the detector's pattern.
class _State:
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class BlockingStackCaptureEngine:
    """Canonical stack-frame capture orchestrator.

    Construct once per runtime, ``start`` after the blocking detector
    is up, ``stop`` from the shutdown coordinator. ``bind_to_detector``
    wires the subscription; ``unbind_from_detector`` is idempotent and
    is also called automatically at ``stop``.

    Frame provider:

    * Default → :class:`LiveFrameProvider` (walks ``sys._getframe``).
      The engine skips a fixed number of internal frames so the
      captured stack starts at the detector callback's caller.
    * Tests → pass a :class:`StaticFrameProvider` via
      ``frame_provider_factory`` to drive deterministic frame
      sequences. The factory is called once per capture to allow
      per-capture variation.
    """

    DEFAULT_SKIP_ENGINE_FRAMES: int = 4

    def __init__(
        self,
        *,
        runtime_clock: RuntimeClock | None = None,
        configuration: StackCaptureConfiguration | None = None,
        event_emitter: EventEmitter | None = None,
        frame_provider_factory: Callable[[], FrameProvider] | None = None,
        task_registry: Any | None = None,
    ) -> None:
        self._runtime_clock = runtime_clock or get_runtime_clock()
        self._configuration = configuration or StackCaptureConfiguration.default()
        self._event_emitter = event_emitter
        self._frame_provider_factory = frame_provider_factory or self._default_provider_factory
        self._task_registry = task_registry
        self._policy = StackCapturePolicy(
            min_severity=self._configuration.min_severity,
            always_capture_severity=self._configuration.always_capture_severity,
            max_captures_per_window=self._configuration.max_captures_per_window,
            capture_outside_windows=self._configuration.capture_outside_windows,
            capture_warning=self._configuration.capture_warning,
        )
        self._sampler = StackSampler(
            limits=self._configuration.limits,
            filters=self._configuration.filters,
        )
        self._serializer = StackSerializer(limits=self._configuration.limits)
        self._task_resolver = TaskMetadataResolver(registry=task_registry)
        self._reentry = ReentryGuard()
        self._statistics = StackCaptureStatistics(
            recent_capacity=self._configuration.recent_capacity,
            top_frame_limit=self._configuration.top_frame_limit,
        )
        self._metrics = StackCaptureMetrics()
        self._backpressure = StackCaptureBackpressure(
            capacity=self._configuration.max_pending_events,
        )
        self._tracer = StackCaptureTracer(enabled=self._configuration.trace_enabled)
        self._diagnostics = self._build_diagnostics()
        self._state = _State.IDLE
        self._state_lock = threading.Lock()
        self._capture_seq = 0
        self._capture_seq_lock = threading.Lock()
        self._detector: BlockingThresholdDetector | None = None
        self._detector_subscription_id: int | None = None
        self._listeners_lock = threading.Lock()
        self._listeners: dict[int, CaptureListener] = {}
        self._listener_next_id = 0
        self._thread_id_provider = threading.get_ident

    # ── helpers ──────────────────────────────────────────────────────────
    def _build_diagnostics(self) -> StackCaptureDiagnostics:
        return StackCaptureDiagnostics(
            statistics=self._statistics,
            metrics=self._metrics,
            backpressure=self._backpressure,
            tracer=self._tracer,
            state_getter=self._get_state,
            configuration_getter=self._get_configuration,
        )

    def _default_provider_factory(self) -> FrameProvider:
        # Skip engine frames so the captured stack starts at user code
        # rather than this method + the detector dispatch.
        return LiveFrameProvider(skip_engine_frames=self.DEFAULT_SKIP_ENGINE_FRAMES)

    def _get_state(self) -> str:
        with self._state_lock:
            return self._state

    def _get_configuration(self) -> StackCaptureConfiguration:
        return self._configuration

    def _next_capture_id(self) -> int:
        with self._capture_seq_lock:
            self._capture_seq += 1
            return self._capture_seq

    # ── reads ────────────────────────────────────────────────────────────
    @property
    def state(self) -> str:
        return self._get_state()

    @property
    def is_running(self) -> bool:
        return self._get_state() == _State.RUNNING

    @property
    def configuration(self) -> StackCaptureConfiguration:
        return self._configuration

    @property
    def runtime_id(self) -> uuid.UUID:
        return self._runtime_clock.runtime_id

    @property
    def bound_detector(self) -> BlockingThresholdDetector | None:
        return self._detector

    # ── lifecycle ────────────────────────────────────────────────────────
    async def start(self) -> None:
        with self._state_lock:
            prev = self._state
            if prev == _State.RUNNING:
                return
            self._state = _State.STARTING
        try:
            with self._state_lock:
                self._state = _State.RUNNING
            logger.debug(
                "stack-capture engine started (min_severity=%s, max_pp_window=%d)",
                self._configuration.min_severity.name,
                self._configuration.max_captures_per_window,
            )
        except Exception:
            with self._state_lock:
                self._state = _State.FAILED
            logger.exception("stack-capture engine failed to start")
            raise

    async def stop(self) -> None:
        with self._state_lock:
            prev = self._state
            if prev in (_State.IDLE, _State.STOPPED):
                self._state = _State.STOPPED
                return
            self._state = _State.STOPPING
        try:
            self.unbind_from_detector()
        finally:
            with self._state_lock:
                self._state = _State.STOPPED
            logger.debug("stack-capture engine stopped")

    def reconfigure(self, configuration: StackCaptureConfiguration) -> None:
        """Atomically swap configuration.

        Sub-engines that own configuration-shaped state are rebuilt
        (sampler/serializer for new limits or filters, statistics for
        new recent_capacity, backpressure for new max_pending_events,
        policy for new severity knobs). The detector subscription
        survives the swap — we never unbind/rebind on reconfigure.
        """
        previous = self._configuration
        if configuration is previous:
            return
        limits_changed = configuration.limits is not previous.limits
        filters_changed = configuration.filters is not previous.filters
        if limits_changed or filters_changed:
            self._sampler = StackSampler(limits=configuration.limits, filters=configuration.filters)
            self._serializer = StackSerializer(limits=configuration.limits)
        if (
            configuration.recent_capacity != previous.recent_capacity
            or configuration.top_frame_limit != previous.top_frame_limit
        ):
            self._statistics = StackCaptureStatistics(
                recent_capacity=configuration.recent_capacity,
                top_frame_limit=configuration.top_frame_limit,
            )
        if configuration.max_pending_events != previous.max_pending_events:
            self._backpressure = StackCaptureBackpressure(
                capacity=configuration.max_pending_events,
            )
        # Policy is replaced wholesale — it owns per-window counters and
        # the new config likely changes the cap, so a fresh instance is
        # the simplest correct choice.
        self._policy = StackCapturePolicy(
            min_severity=configuration.min_severity,
            always_capture_severity=configuration.always_capture_severity,
            max_captures_per_window=configuration.max_captures_per_window,
            capture_outside_windows=configuration.capture_outside_windows,
            capture_warning=configuration.capture_warning,
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
                StackCaptureTraceRecord(
                    kind="reconfigure",
                    monotonic_ns=self._runtime_clock.monotonic_ns(),
                    detail=f"min_severity={configuration.min_severity.name}",
                )
            )

    # ── detector binding ─────────────────────────────────────────────────
    def bind_to_detector(self, detector: BlockingThresholdDetector) -> int:
        if self._detector_subscription_id is not None:
            return self._detector_subscription_id
        self._detector_subscription_id = detector.subscribe(self.on_detection)
        self._detector = detector
        return self._detector_subscription_id

    def unbind_from_detector(self) -> bool:
        if self._detector_subscription_id is None or self._detector is None:
            return False
        try:
            removed = self._detector.unsubscribe(self._detector_subscription_id)
        except Exception:
            removed = False
            logger.exception("stack-capture engine unbind raised; ignoring")
        self._detector_subscription_id = None
        self._detector = None
        return removed

    # ── core pipeline ────────────────────────────────────────────────────
    def on_detection(self, outcome: DetectionOutcome) -> CapturedStack | None:
        """Engine entrypoint. Called once per :class:`DetectionOutcome`.

        Returns the :class:`CapturedStack` produced (or ``None`` when
        nothing was captured) so test code + future in-process consumers
        can react synchronously.
        """
        self._metrics.record_outcome()
        if not self._configuration.enabled:
            return None
        decision = self._policy.decide(outcome)
        if not decision.capture:
            self._metrics.record_capture_skipped_policy()
            self._trace(
                "skip_policy",
                detail=decision.reason,
                window_id=self._outcome_window_id(outcome),
            )
            return None
        return self._capture(
            decision=decision,
            sample_index=outcome.classification.measurement.sample_index,
            window_id=self._outcome_window_id(outcome),
            severity=outcome.effective_severity.name,
        )

    def capture_manual(
        self,
        *,
        trigger: str = "manual",
        severity: str = "NONE",
        window_id: str | None = None,
        sample_index: int | None = None,
    ) -> CapturedStack | None:
        """Take a capture outside the detector flow.

        Used by API endpoints / debugger overlays to demand a capture
        on operator request. Bypasses the policy entirely (the request
        itself is the policy decision).
        """
        if not self._configuration.enabled:
            return None
        decision = CaptureDecision(capture=True, trigger=trigger, reason="manual_request")
        return self._capture(
            decision=decision,
            sample_index=sample_index,
            window_id=window_id,
            severity=severity,
        )

    def _capture(
        self,
        *,
        decision: CaptureDecision,
        sample_index: int | None,
        window_id: str | None,
        severity: str,
    ) -> CapturedStack | None:
        with self._reentry.acquire() as allowed:
            if not allowed:
                self._metrics.record_capture_skipped_reentry()
                self._trace("skip_reentry", detail="re-entry blocked")
                return None
            self._metrics.record_capture_attempted()
            try:
                provider = self._frame_provider_factory()
                sample_outcome = self._sampler.sample(provider)
            except Exception:
                self._metrics.record_sampler_failure()
                logger.exception("stack-capture sampler raised; skipping capture")
                self._trace("sampler_failure", detail="sampler exception")
                return None

            task_meta: CapturedTaskMetadata = (
                self._task_resolver.resolve()
                if self._configuration.capture_task_metadata
                else CapturedTaskMetadata()
            )
            stack = CapturedStack(
                capture_id=self._next_capture_id(),
                runtime_id=str(self._runtime_clock.runtime_id),
                monotonic_ns=self._runtime_clock.monotonic_ns(),
                sample_index=sample_index,
                window_id=window_id,
                severity=severity,
                trigger=decision.trigger,
                frames=sample_outcome.frames,
                frames_total=sample_outcome.frames_total,
                filtered_count=sample_outcome.filtered_count,
                thread_id=self._thread_id_provider(),
                task=task_meta,
            )

            try:
                serialized = self._serializer.serialize(stack)
            except Exception:
                self._metrics.record_serializer_failure()
                logger.exception("stack-capture serializer raised; skipping capture")
                self._trace(
                    "serializer_failure",
                    detail="serializer exception",
                    capture_id=stack.capture_id,
                    window_id=stack.window_id,
                )
                return None

            emitted = self._emit(stack, serialized.payload, json_bytes=serialized.json_bytes)
            if emitted:
                self._metrics.record_capture_emitted(
                    payload_bytes=serialized.json_bytes,
                    frame_count=stack.frame_count,
                    filtered_count=stack.filtered_count,
                    trimmed=serialized.trimmed,
                )
                self._statistics.observe(stack)
                self._trace(
                    "capture",
                    detail=stack.trigger,
                    capture_id=stack.capture_id,
                    window_id=stack.window_id,
                )
                if serialized.trimmed:
                    self._trace(
                        "trim",
                        detail=f"frames {serialized.original_frame_count}->{stack.frame_count}",
                        capture_id=stack.capture_id,
                        window_id=stack.window_id,
                    )
                self._notify_listeners(stack)
            return stack if emitted else None

    def _emit(
        self,
        stack: CapturedStack,
        payload: dict[str, Any],
        *,
        json_bytes: int,
    ) -> bool:
        del json_bytes  # consumed by record_capture_emitted upstream
        if not self._configuration.emit_events or self._event_emitter is None:
            # No emitter wired — still considered a successful capture
            # for statistics + listener purposes. Tests that omit the
            # emitter still want the capture object.
            return True
        decision = self._backpressure.acquire()
        if not decision.accepted:
            self._metrics.record_capture_dropped_backpressure()
            self._trace(
                "backpressure_denied",
                detail=decision.reason,
                capture_id=stack.capture_id,
                window_id=stack.window_id,
            )
            return False
        try:
            event = build_stack_capture_event(
                payload=payload, runtime_id=self._runtime_clock.runtime_id
            )
            accepted = bool(self._event_emitter(event))
        except Exception:
            self._metrics.record_emitter_failure()
            logger.exception("stack-capture emitter raised")
            self._trace(
                "emitter_failure",
                detail="emitter exception",
                capture_id=stack.capture_id,
                window_id=stack.window_id,
            )
            accepted = False
        finally:
            self._backpressure.release()
        if not accepted:
            self._metrics.record_capture_dropped_emitter()
        return accepted

    @staticmethod
    def _outcome_window_id(outcome: DetectionOutcome) -> str | None:
        transition = outcome.window_transition
        win = transition.active or transition.opened or transition.closed
        return win.window_id if win is not None else None

    # ── listeners ────────────────────────────────────────────────────────
    def subscribe(self, listener: CaptureListener) -> int:
        with self._listeners_lock:
            self._listener_next_id += 1
            sid = self._listener_next_id
            self._listeners[sid] = listener
        return sid

    def unsubscribe(self, subscription_id: int) -> bool:
        with self._listeners_lock:
            return self._listeners.pop(subscription_id, None) is not None

    def _notify_listeners(self, stack: CapturedStack) -> None:
        with self._listeners_lock:
            listeners = list(self._listeners.values())
        for listener in listeners:
            try:
                listener(stack)
            except Exception:
                self._metrics.record_handler_failure()
                logger.exception("stack-capture listener raised; continuing")

    # ── snapshots ────────────────────────────────────────────────────────
    def snapshot(self) -> StackCaptureSnapshot:
        return StackCaptureSnapshot(
            runtime_id=str(self._runtime_clock.runtime_id),
            state=self._get_state(),
            generated_at_monotonic_ns=self._runtime_clock.monotonic_ns(),
            configuration=self._configuration.to_dict(),
            statistics=self._statistics.snapshot(),
            metrics=self._metrics.snapshot(),
            recent_captures=self._statistics.recent(),
        )

    def diagnostics_snapshot(self) -> StackCaptureDiagnosticsSnapshot:
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
        detail: str,
        capture_id: int = -1,
        window_id: str | None = None,
    ) -> None:
        if not self._tracer.enabled:
            return
        self._tracer.record(
            StackCaptureTraceRecord(
                kind=kind,
                monotonic_ns=self._runtime_clock.monotonic_ns(),
                detail=detail,
                capture_id=capture_id,
                window_id=window_id,
            )
        )


async def run_stack_capture_engine_for(
    engine: BlockingStackCaptureEngine, *, seconds: float
) -> None:
    """Test helper — run the engine for a bounded duration."""
    await engine.start()
    try:
        await asyncio.sleep(seconds)
    finally:
        await engine.stop()
