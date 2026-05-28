"""Canonical blocking warning emission orchestrator.

Sits on top of the blocking detector + stack-capture engine and turns
their event streams into operator-focused warning groups + lifecycle
transitions.

The emitter is the *authoritative* source of grouped blocking warning
events on the bus — distinct from the older per-event
:class:`BlockingViolationDetector` in
:mod:`asyncviz.runtime.warnings.detectors`, which fires one warning
per blocking event. This emitter aggregates that stream into one
:class:`WarningGroup` per freeze window with full lifecycle.

Public surface:

* :meth:`start` / :meth:`stop`           — lifecycle.
* :meth:`bind_to_detector`               — subscribe to detector outcomes.
* :meth:`bind_to_capture_engine`         — subscribe to capture events.
* :meth:`on_detection`                   — synchronous apply hook.
* :meth:`on_capture`                     — synchronous capture hook.
* :meth:`sweep_expirations`              — finalize stale recovered
  groups; call from a heartbeat or periodic task.
* :meth:`reconfigure`                    — atomic config swap.
* :meth:`snapshot` / :meth:`diagnostics_snapshot` — observability.

Replay safety: every state transition is a pure function of the input
streams. No clock reads inside the pipeline — every timestamp comes
from the outcome's ``actual_ns``. Identical input sequences produce
identical group state + identical emitted events.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Callable

from asyncviz.runtime.clock import RuntimeClock, get_runtime_clock
from asyncviz.runtime.monitoring.blocking import (
    BlockingStackCaptureEngine,
    BlockingThresholdDetector,
    CapturedStack,
    DetectionOutcome,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_backpressure import (
    WarningEmitterBackpressure,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_configuration import (
    BlockingWarningConfiguration,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_correlation import (
    CaptureCorrelator,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_deduplication import (
    TransitionDeduplicator,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_diagnostics import (
    BlockingWarningDiagnostics,
    BlockingWarningDiagnosticsSnapshot,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_events import (
    build_blocking_warning_event,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_grouping import (
    WarningGroup,
    WarningGroupRegistry,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_metrics import (
    BlockingWarningMetrics,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_observability import (
    BlockingWarningEmitterSnapshot,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_payloads import (
    BlockingWarningPayload,
    build_payload,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_policy import (
    BlockingWarningPolicy,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_router import (
    EventEmitter,
    PayloadListener,
    WarningRouter,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_state import (
    BlockingWarningEmitterLifecycle,
    BlockingWarningEmitterState,
    BlockingWarningGroupState,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_statistics import (
    BlockingWarningStatistics,
)
from asyncviz.runtime.warnings.blocking.blocking_warning_tracing import (
    BlockingWarningTracer,
    BlockingWarningTraceRecord,
)
from asyncviz.utils.logging import get_logger

logger = get_logger("runtime.warnings.blocking.emitter")


_NO_WINDOW_KEY = "_no_window_"


class BlockingWarningEmitter:
    """Aggregate detector + capture streams into grouped warning events.

    Construct once per runtime; ``start`` after the detector + capture
    engine come up; ``bind_to_detector`` / ``bind_to_capture_engine``
    wire the subscriptions explicitly so the upstream engines don't
    need to know about the emitter at construction time.
    """

    def __init__(
        self,
        *,
        runtime_clock: RuntimeClock | None = None,
        configuration: BlockingWarningConfiguration | None = None,
        event_emitter: EventEmitter | None = None,
    ) -> None:
        self._runtime_clock = runtime_clock or get_runtime_clock()
        self._configuration = configuration or BlockingWarningConfiguration.default()
        self._policy = BlockingWarningPolicy(
            min_severity=self._configuration.min_severity,
            include_no_window=self._configuration.include_no_window,
            escalations_only=self._configuration.escalations_only,
        )
        self._registry = WarningGroupRegistry(
            recent_capacity=self._configuration.recent_capacity,
        )
        self._dedup = TransitionDeduplicator(
            opened_ns=self._configuration.opened_cooldown_ns,
            escalated_ns=self._configuration.escalated_cooldown_ns,
            active_ns=self._configuration.active_cooldown_ns,
            recovered_ns=self._configuration.recovered_cooldown_ns,
            expired_ns=self._configuration.expired_cooldown_ns,
        )
        self._correlator = CaptureCorrelator(self._registry)
        self._statistics = BlockingWarningStatistics(
            top_coroutine_limit=self._configuration.top_coroutine_limit,
        )
        self._metrics = BlockingWarningMetrics()
        self._backpressure = WarningEmitterBackpressure(
            capacity=self._configuration.max_pending_events,
        )
        self._tracer = BlockingWarningTracer(enabled=self._configuration.trace_enabled)
        self._router = WarningRouter(emitter=event_emitter)
        self._diagnostics = self._build_diagnostics()
        self._lifecycle = BlockingWarningEmitterLifecycle()
        self._detector: BlockingThresholdDetector | None = None
        self._detector_subscription_id: int | None = None
        self._capture_engine: BlockingStackCaptureEngine | None = None
        self._capture_subscription_id: int | None = None
        self._reentry_lock = threading.local()
        self._latest_monotonic_ns = 0
        self._latest_lock = threading.Lock()

    # ── helpers ──────────────────────────────────────────────────────────
    def _build_diagnostics(self) -> BlockingWarningDiagnostics:
        return BlockingWarningDiagnostics(
            statistics=self._statistics,
            metrics=self._metrics,
            backpressure=self._backpressure,
            tracer=self._tracer,
            registry=self._registry,
            state_getter=self._get_state_str,
            configuration_getter=self._get_configuration,
        )

    def _get_state_str(self) -> str:
        return self._lifecycle.state.value

    def _get_configuration(self) -> BlockingWarningConfiguration:
        return self._configuration

    def _update_latest_ns(self, ns: int) -> None:
        with self._latest_lock:
            if ns > self._latest_monotonic_ns:
                self._latest_monotonic_ns = ns

    def _get_latest_ns(self) -> int:
        with self._latest_lock:
            return self._latest_monotonic_ns

    # ── reads ────────────────────────────────────────────────────────────
    @property
    def state(self) -> BlockingWarningEmitterState:
        return self._lifecycle.state

    @property
    def is_running(self) -> bool:
        return self._lifecycle.is_running()

    @property
    def configuration(self) -> BlockingWarningConfiguration:
        return self._configuration

    @property
    def runtime_id(self) -> uuid.UUID:
        return self._runtime_clock.runtime_id

    @property
    def bound_detector(self) -> BlockingThresholdDetector | None:
        return self._detector

    @property
    def bound_capture_engine(self) -> BlockingStackCaptureEngine | None:
        return self._capture_engine

    @property
    def router(self) -> WarningRouter:
        return self._router

    # ── lifecycle ────────────────────────────────────────────────────────
    async def start(self) -> None:
        prev = self._lifecycle.mark(BlockingWarningEmitterState.STARTING)
        if prev is BlockingWarningEmitterState.RUNNING:
            self._lifecycle.mark(BlockingWarningEmitterState.RUNNING)
            return
        try:
            self._lifecycle.mark(BlockingWarningEmitterState.RUNNING)
            logger.debug(
                "blocking warning emitter started (min_severity=%s)",
                self._configuration.min_severity.name,
            )
        except Exception:
            self._lifecycle.mark(BlockingWarningEmitterState.FAILED)
            logger.exception("blocking warning emitter failed to start")
            raise

    async def stop(self) -> None:
        prev = self._lifecycle.mark(BlockingWarningEmitterState.STOPPING)
        if prev in (BlockingWarningEmitterState.IDLE, BlockingWarningEmitterState.STOPPED):
            self._lifecycle.mark(BlockingWarningEmitterState.STOPPED)
            return
        try:
            self.unbind_from_detector()
            self.unbind_from_capture_engine()
            # Close any still-open groups so the captured snapshot
            # reflects a clean shutdown rather than dangling state.
            now_ns = self._runtime_clock.monotonic_ns()
            for group_snap in self._registry.active_snapshots():
                group = self._registry.find_by_group_id(group_snap.group_id)
                if group is None:
                    continue
                self._finalize_recovered(group, monotonic_ns=now_ns, trigger="shutdown")
        finally:
            self._lifecycle.mark(BlockingWarningEmitterState.STOPPED)
            logger.debug("blocking warning emitter stopped")

    def reconfigure(self, configuration: BlockingWarningConfiguration) -> None:
        """Atomically swap configuration.

        Sub-engines that own configuration-shaped state are rebuilt
        (registry for ``recent_capacity``, statistics for
        ``top_coroutine_limit``, backpressure for ``max_pending_events``,
        dedup for cooldowns, policy for severity knobs). Active groups
        survive a reconfigure as long as ``recent_capacity`` is
        unchanged.
        """
        previous = self._configuration
        if configuration is previous:
            return
        if configuration.recent_capacity != previous.recent_capacity:
            new_registry = WarningGroupRegistry(
                recent_capacity=configuration.recent_capacity,
            )
            # Preserve active groups across the swap; recent_groups is
            # acceptable to drop — the wire log still has them.
            for snap in self._registry.active_snapshots():
                live = self._registry.find_by_group_id(snap.group_id)
                if live is not None:
                    new_registry.add(live)
            self._registry = new_registry
            self._correlator = CaptureCorrelator(self._registry)
        if configuration.top_coroutine_limit != previous.top_coroutine_limit:
            # Statistics is incremental — rebuild loses lifetime
            # counts, but the alternative is a stale top-N list. The
            # operator opted in to a reconfigure; surface that cost.
            self._statistics = BlockingWarningStatistics(
                top_coroutine_limit=configuration.top_coroutine_limit,
            )
        if configuration.max_pending_events != previous.max_pending_events:
            self._backpressure = WarningEmitterBackpressure(
                capacity=configuration.max_pending_events,
            )
        if (
            configuration.opened_cooldown_ns != previous.opened_cooldown_ns
            or configuration.escalated_cooldown_ns != previous.escalated_cooldown_ns
            or configuration.active_cooldown_ns != previous.active_cooldown_ns
            or configuration.recovered_cooldown_ns != previous.recovered_cooldown_ns
            or configuration.expired_cooldown_ns != previous.expired_cooldown_ns
        ):
            self._dedup = TransitionDeduplicator(
                opened_ns=configuration.opened_cooldown_ns,
                escalated_ns=configuration.escalated_cooldown_ns,
                active_ns=configuration.active_cooldown_ns,
                recovered_ns=configuration.recovered_cooldown_ns,
                expired_ns=configuration.expired_cooldown_ns,
            )
        self._policy = BlockingWarningPolicy(
            min_severity=configuration.min_severity,
            include_no_window=configuration.include_no_window,
            escalations_only=configuration.escalations_only,
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
                BlockingWarningTraceRecord(
                    kind="reconfigure",
                    monotonic_ns=self._runtime_clock.monotonic_ns(),
                    detail="config_swapped",
                )
            )

    # ── detector / capture binding ───────────────────────────────────────
    def bind_to_detector(self, detector: BlockingThresholdDetector) -> int:
        if self._detector_subscription_id is not None:
            return self._detector_subscription_id
        self._detector_subscription_id = detector.subscribe(self._on_detection_safe)
        self._detector = detector
        return self._detector_subscription_id

    def unbind_from_detector(self) -> bool:
        if self._detector is None or self._detector_subscription_id is None:
            return False
        try:
            removed = self._detector.unsubscribe(self._detector_subscription_id)
        except Exception:
            removed = False
            logger.exception("emitter unbind_from_detector raised; ignoring")
        self._detector_subscription_id = None
        self._detector = None
        return removed

    def bind_to_capture_engine(self, engine: BlockingStackCaptureEngine) -> int:
        if self._capture_subscription_id is not None:
            return self._capture_subscription_id
        self._capture_subscription_id = engine.subscribe(self._on_capture_safe)
        self._capture_engine = engine
        return self._capture_subscription_id

    def unbind_from_capture_engine(self) -> bool:
        if self._capture_engine is None or self._capture_subscription_id is None:
            return False
        try:
            removed = self._capture_engine.unsubscribe(self._capture_subscription_id)
        except Exception:
            removed = False
            logger.exception("emitter unbind_from_capture_engine raised; ignoring")
        self._capture_subscription_id = None
        self._capture_engine = None
        return removed

    def _on_detection_safe(self, outcome: DetectionOutcome) -> None:
        try:
            self.on_detection(outcome)
        except Exception:
            self._metrics.record_handler_failure()
            logger.exception("emitter on_detection raised; continuing")

    def _on_capture_safe(self, stack: CapturedStack) -> None:
        try:
            self.on_capture(stack)
        except Exception:
            self._metrics.record_handler_failure()
            logger.exception("emitter on_capture raised; continuing")

    # ── re-entry guard helpers ───────────────────────────────────────────
    def _is_in_dispatch(self) -> bool:
        return bool(getattr(self._reentry_lock, "active", False))

    def _set_in_dispatch(self, active: bool) -> None:
        self._reentry_lock.active = active

    # ── public hooks ─────────────────────────────────────────────────────
    def on_detection(self, outcome: DetectionOutcome) -> BlockingWarningPayload | None:
        """Process one detector outcome. Returns the emitted payload (or None)."""
        self._metrics.record_outcome()
        if not self._configuration.enabled:
            return None
        if self._is_in_dispatch():
            # Re-entry from a listener — refuse silently to avoid
            # recursive emission spirals.
            self._trace_record("emitter_failure", detail="reentry_blocked")
            return None
        ns = outcome.classification.measurement.actual_ns
        self._update_latest_ns(ns)

        # Window-close ⇒ recover the corresponding group (if any) up
        # front. This runs even when the policy rejects the same
        # outcome — closes shouldn't be missed because of a policy
        # filter.
        closed_window = outcome.window_transition.closed
        if closed_window is not None:
            existing = self._registry.find_by_window_id(closed_window.window_id)
            if existing is not None:
                self._finalize_recovered(
                    existing,
                    monotonic_ns=ns,
                    trigger="window_closed",
                )

        policy_decision = self._policy.evaluate(outcome)
        window_key = self._window_key(outcome)
        existing = self._registry.find_by_window_id(window_key)

        # If the policy rejects the outcome, the only path forward is
        # the escalations_only-mode silent open. Everything else exits:
        # close + correlation paths already ran above, and refusing
        # here stops a NONE-severity close event from falling through
        # to the refresh branch as a spurious "active".
        if not policy_decision.accept:
            if (
                existing is None
                and self._policy.escalations_only
                and outcome.effective_severity >= self._configuration.min_severity
            ):
                group = self._open_group(outcome, window_key=window_key, ns=ns)
                self._metrics.record_suppressed_by_policy()
                self._trace_record(
                    "suppressed_policy",
                    detail="escalations_only_open",
                    group_id=group.group_id,
                )
                return None
            self._metrics.record_suppressed_by_policy()
            self._trace_record(
                "suppressed_policy",
                detail=policy_decision.reason,
            )
            return None

        if existing is None:
            group = self._open_group(outcome, window_key=window_key, ns=ns)
            return self._emit_transition(group, transition="opened", monotonic_ns=ns)
        # A RECOVERED group still in the registry (waiting for TTL) does
        # not accept new observations — refusing here avoids zombie
        # transitions after a clean recovery.
        if existing.state.is_terminal:
            self._metrics.record_suppressed_by_policy()
            self._trace_record(
                "suppressed_policy",
                detail="group_terminal",
                group_id=existing.group_id,
            )
            return None
        # Refresh path.
        new_state = existing.record_observation(
            severity=outcome.effective_severity,
            lag_ns=outcome.classification.lag_ns,
            monotonic_ns=ns,
            sample_index=outcome.classification.measurement.sample_index,
        )
        if new_state is BlockingWarningGroupState.ESCALATING:
            return self._emit_transition(existing, transition="escalated", monotonic_ns=ns)
        # ACTIVE refresh — rate-limited by dedup.
        return self._emit_transition(existing, transition="active", monotonic_ns=ns)

    def on_capture(self, stack: CapturedStack) -> bool:
        """Correlate a stack capture with its warning group. Returns True on match."""
        self._metrics.record_capture()
        if not self._configuration.enabled:
            return False
        result = self._correlator.correlate(stack)
        if result.group is None:
            self._metrics.record_capture_uncorrelated()
            self._trace_record(
                "capture_uncorrelated",
                detail=result.window_id or "no_window",
            )
            return False
        self._metrics.record_capture_correlated()
        self._statistics.observe_capture_correlated()
        self._statistics.observe_coroutine(stack.task.coroutine_name)
        self._trace_record(
            "capture_correlated",
            detail=stack.task.coroutine_name or "",
            group_id=result.group.group_id,
        )
        return True

    def sweep_expirations(self, *, now_monotonic_ns: int | None = None) -> int:
        """Expire stale recovered groups. Returns the count expired.

        Called from a heartbeat or periodic task. The TTL is
        ``configuration.expiration_ttl_ns``; a recovered group whose
        ``recovered_ns`` is older than ``now - TTL`` is moved to the
        finalized ring.

        We DON'T expire active groups — they're still in progress.
        Operators rely on the recovered → expired transition for
        archival cleanup; active groups stay open until the detector
        reports their window closing.
        """
        ttl = self._configuration.expiration_ttl_ns
        if ttl <= 0:
            return 0
        now_ns = now_monotonic_ns if now_monotonic_ns is not None else self._get_latest_ns()
        if now_ns <= 0:
            return 0
        expired = 0
        # Note: active_snapshots is a copy — safe to iterate while
        # mutating the live registry.
        for snap in self._registry.active_snapshots():
            if snap.state is not BlockingWarningGroupState.RECOVERED:
                continue
            recovered_ns = snap.recovered_ns or 0
            if recovered_ns == 0 or (now_ns - recovered_ns) < ttl:
                continue
            live = self._registry.find_by_group_id(snap.group_id)
            if live is None:
                continue
            live.mark_expired(monotonic_ns=now_ns)
            self._statistics.observe_group_expired(live.snapshot())
            self._metrics.record_group_expired()
            self._dedup.forget_group(live.group_id)
            payload = self._emit_transition(live, transition="expired", monotonic_ns=now_ns)
            self._registry.finalize(live)
            del payload
            expired += 1
        return expired

    # ── pipeline internals ───────────────────────────────────────────────
    def _open_group(
        self,
        outcome: DetectionOutcome,
        *,
        window_key: str,
        ns: int,
    ) -> WarningGroup:
        sequence = self._registry.next_sequence()
        warning_id = f"bw:{self._runtime_clock.runtime_id}:{sequence}"
        group_id = warning_id
        window_id = self._effective_window_id(outcome)
        severity = outcome.effective_severity.name
        group = WarningGroup(
            group_id=group_id,
            warning_id=warning_id,
            runtime_id=str(self._runtime_clock.runtime_id),
            window_id=window_id,
            state=BlockingWarningGroupState.OPENED,
            severity=severity,
            peak_severity=severity,
            first_seen_ns=ns,
            last_seen_ns=ns,
            peak_lag_ns=outcome.classification.lag_ns,
            last_lag_ns=outcome.classification.lag_ns,
            violation_count=1,
            escalation_count=0,
        )
        # Use the window_key (which may be "_no_window_") as the
        # registry lookup so subsequent outcomes find this group.
        # The registry indexes by window_id; we override window_id for
        # the lookup but keep the real value on the group for display.
        group.window_id = window_key
        self._registry.add(group)
        # Restore the user-visible window_id for downstream consumers.
        # (Same as window_key when window_id was provided; differs only
        # for the no-window bucket where window_id is None on the wire.)
        if window_key == _NO_WINDOW_KEY:
            group.window_id = None
        self._metrics.record_group_opened()
        self._statistics.observe_group_opened(group.snapshot())
        self._trace_record(
            "opened",
            detail=window_key,
            group_id=group_id,
            severity=severity,
        )
        return group

    def _finalize_recovered(
        self,
        group: WarningGroup,
        *,
        monotonic_ns: int,
        trigger: str,
    ) -> None:
        if group.state is BlockingWarningGroupState.RECOVERED:
            return
        group.mark_recovered(monotonic_ns=monotonic_ns)
        self._statistics.observe_group_recovered(group.snapshot())
        self._metrics.record_group_recovered()
        self._emit_transition(group, transition="recovered", monotonic_ns=monotonic_ns)
        # Recovered groups stay in the active registry until expire so
        # operators can still query their final state, but they no
        # longer accept new observations.
        self._trace_record(
            "recovered",
            detail=trigger,
            group_id=group.group_id,
        )

    def _emit_transition(
        self,
        group: WarningGroup,
        *,
        transition: str,
        monotonic_ns: int,
    ) -> BlockingWarningPayload | None:
        self._metrics.record_transition(transition)
        decision = self._dedup.check_and_record(
            group_id=group.group_id,
            transition=transition,
            now_ns=monotonic_ns,
        )
        if decision.suppressed:
            self._metrics.record_suppressed_by_dedup()
            self._trace_record(
                "suppressed_dedup",
                detail=f"remaining_ns={decision.remaining_ns}",
                group_id=group.group_id,
                transition=transition,
            )
            return None
        sequence = self._registry.next_sequence()
        snap = group.snapshot()
        payload = build_payload(snapshot=snap, transition=transition, sequence=sequence)
        bp = self._backpressure.acquire()
        if not bp.accepted:
            self._metrics.record_event_dropped_backpressure()
            self._trace_record(
                "backpressure_denied",
                detail=bp.reason,
                group_id=group.group_id,
                transition=transition,
            )
            return None
        event = (
            build_blocking_warning_event(payload=payload, runtime_id=self._runtime_clock.runtime_id)
            if self._configuration.emit_events
            else None
        )
        self._set_in_dispatch(True)
        accepted = False
        try:
            outcome = self._router.dispatch(event=event, payload=payload)
            accepted = outcome.accepted
            if outcome.listener_errors:
                self._metrics.record_listener_failure()
        except Exception:
            self._metrics.record_emitter_failure()
            self._trace_record(
                "emitter_failure",
                detail="dispatch_exception",
                group_id=group.group_id,
                transition=transition,
            )
            return None
        finally:
            self._set_in_dispatch(False)
            self._backpressure.release()
        if accepted:
            self._metrics.record_event_emitted()
            self._trace_record(
                transition,  # type: ignore[arg-type]
                detail="emitted",
                group_id=group.group_id,
                transition=transition,
                severity=group.severity,
            )
        else:
            self._metrics.record_event_dropped_emitter()
        return payload

    def _window_key(self, outcome: DetectionOutcome) -> str:
        active = outcome.window_transition.active or outcome.window_transition.opened
        if active is not None:
            return active.window_id
        # closed-only outcomes can correlate with their closed window_id
        closed = outcome.window_transition.closed
        if closed is not None:
            return closed.window_id
        return _NO_WINDOW_KEY

    def _effective_window_id(self, outcome: DetectionOutcome) -> str | None:
        active = outcome.window_transition.active or outcome.window_transition.opened
        if active is not None:
            return active.window_id
        closed = outcome.window_transition.closed
        if closed is not None:
            return closed.window_id
        return None

    # ── router pass-through ──────────────────────────────────────────────
    def subscribe(self, listener: PayloadListener) -> int:
        return self._router.subscribe(listener)

    def unsubscribe(self, subscription_id: int) -> bool:
        return self._router.unsubscribe(subscription_id)

    # ── snapshots ────────────────────────────────────────────────────────
    def snapshot(self) -> BlockingWarningEmitterSnapshot:
        return BlockingWarningEmitterSnapshot(
            runtime_id=str(self._runtime_clock.runtime_id),
            state=self._lifecycle.state.value,
            generated_at_monotonic_ns=self._runtime_clock.monotonic_ns(),
            configuration=self._configuration.to_dict(),
            statistics=self._statistics.snapshot(),
            metrics=self._metrics.snapshot(),
            active_groups=self._registry.active_snapshots(),
            recent_groups=self._registry.recent_snapshots(),
        )

    def diagnostics_snapshot(self) -> BlockingWarningDiagnosticsSnapshot:
        return self._diagnostics.snapshot()

    def statistics_snapshot(self):
        return self._statistics.snapshot()

    def metrics_snapshot(self):
        return self._metrics.snapshot()

    # ── trace helper ─────────────────────────────────────────────────────
    def _trace_record(
        self,
        kind,
        *,
        detail: str,
        group_id: str | None = None,
        transition: str | None = None,
        severity: str | None = None,
    ) -> None:
        if not self._tracer.enabled:
            return
        self._tracer.record(
            BlockingWarningTraceRecord(
                kind=kind,
                monotonic_ns=self._runtime_clock.monotonic_ns(),
                detail=detail,
                group_id=group_id,
                transition=transition,
                severity=severity,
            )
        )


async def run_blocking_warning_emitter_for(
    emitter: BlockingWarningEmitter, *, seconds: float
) -> None:
    """Test helper — run the emitter for a bounded duration."""
    await emitter.start()
    try:
        await asyncio.sleep(seconds)
    finally:
        await emitter.stop()


# Re-export the listener type for convenience.
ListenerCallback = Callable[[BlockingWarningPayload], None]
