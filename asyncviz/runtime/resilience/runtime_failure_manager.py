"""Canonical RuntimeFailureManager.

Top-level façade that composes every resilience piece into one
coherent API:

    manager = RuntimeFailureManager()
    replay = manager.register("replay")
    # subsystem code:
    with replay.isolate_decode(payload_kind="frame-42") as boundary:
        ...

The manager owns:

* a :class:`FailureDomain` per registered subsystem,
* a :class:`RecoverySupervisor` per domain,
* the singleton :class:`IsolationMetrics`,
* the bridge to the backpressure layer,
* the current runtime :class:`EmergencyMode`.

The manager never crashes the host process: every internal hook is
guarded, every listener invocation is isolated, every breaker is
bounded.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.runtime.resilience.degradation_policy import derive_runtime_mode
from asyncviz.runtime.resilience.failure_classifier import (
    classify_exception,
    classify_marker,
)
from asyncviz.runtime.resilience.failure_domain import (
    FailureDomain,
    FailureDomainSnapshot,
)
from asyncviz.runtime.resilience.isolation_backpressure import (
    BackpressureSuggestion,
    IsolationBackpressureBridge,
)
from asyncviz.runtime.resilience.isolation_configuration import (
    EmergencyMode,
    IsolationConfig,
    SubsystemPolicy,
    default_config,
)
from asyncviz.runtime.resilience.isolation_diagnostics import (
    IsolationDiagnostics,
    IsolationDiagnosticsInputs,
    build_isolation_diagnostics,
)
from asyncviz.runtime.resilience.isolation_integrity import (
    IntegrityFinding,
    check_domain,
    check_supervisor,
)
from asyncviz.runtime.resilience.isolation_observability import (
    IsolationMetrics,
    get_isolation_metrics,
)
from asyncviz.runtime.resilience.isolation_tracing import (
    record_isolation_trace,
    set_isolation_trace_enabled,
)
from asyncviz.runtime.resilience.models.breaker_state import BreakerState
from asyncviz.runtime.resilience.models.failure_event import FailureEvent
from asyncviz.runtime.resilience.models.failure_kind import (
    DO_NOT_RETRY,
    FailureKind,
)
from asyncviz.runtime.resilience.models.recovery_outcome import RecoveryOutcome
from asyncviz.runtime.resilience.models.subsystem_id import SubsystemId
from asyncviz.runtime.resilience.recorder_failure_isolation import (
    RecorderFailureIsolation,
)
from asyncviz.runtime.resilience.recovery_supervisor import (
    AsyncRecoveryHook,
    RecoverySupervisor,
    SupervisorSnapshot,
    SyncRecoveryHook,
)
from asyncviz.runtime.resilience.reducer_failure_isolation import (
    ReducerFailureIsolation,
)
from asyncviz.runtime.resilience.render_failure_isolation import (
    RenderFailureIsolation,
)
from asyncviz.runtime.resilience.replay_failure_isolation import (
    ReplayFailureIsolation,
)
from asyncviz.runtime.resilience.subsystem_boundary import (
    AsyncSubsystemBoundary,
    SubsystemBoundary,
)
from asyncviz.runtime.resilience.websocket_failure_isolation import (
    WebsocketFailureIsolation,
)

ModeListener = Callable[[EmergencyMode], None]


@dataclass(slots=True)
class _SubsystemEntry:
    domain: FailureDomain
    supervisor: RecoverySupervisor


class RuntimeFailureManager:
    """Production failure-isolation façade."""

    __slots__ = (
        "_config",
        "_isolation_backpressure",
        "_lock",
        "_metrics",
        "_mode",
        "_mode_listeners",
        "_recorder_adapter",
        "_reducer_adapter",
        "_render_adapter",
        "_replay_adapter",
        "_subsystems",
        "_websocket_adapter",
    )

    def __init__(
        self,
        *,
        config: IsolationConfig | None = None,
        metrics: IsolationMetrics | None = None,
    ) -> None:
        self._config = config if config is not None else default_config()
        self._metrics = metrics if metrics is not None else get_isolation_metrics()
        self._lock = threading.RLock()
        self._subsystems: dict[str, _SubsystemEntry] = {}
        self._mode: EmergencyMode = "normal"
        self._mode_listeners: list[ModeListener] = []
        self._isolation_backpressure = IsolationBackpressureBridge()
        self._replay_adapter: ReplayFailureIsolation | None = None
        self._websocket_adapter: WebsocketFailureIsolation | None = None
        self._reducer_adapter: ReducerFailureIsolation | None = None
        self._render_adapter: RenderFailureIsolation | None = None
        self._recorder_adapter: RecorderFailureIsolation | None = None
        if self._config.enable_tracing:
            set_isolation_trace_enabled(True, capacity=self._config.trace_capacity)

    # ── registration ────────────────────────────────────────────

    def register(
        self,
        subsystem: str,
        *,
        policy: SubsystemPolicy | None = None,
    ) -> FailureDomain:
        with self._lock:
            entry = self._subsystems.get(subsystem)
            if entry is not None:
                return entry.domain
            resolved_policy = (
                policy
                if policy is not None
                else self._config.per_subsystem.get(subsystem, self._config.default_policy)
            )
            domain = FailureDomain(subsystem, resolved_policy)
            supervisor = RecoverySupervisor(domain)
            self._subsystems[subsystem] = _SubsystemEntry(domain=domain, supervisor=supervisor)
        domain.subscribe(self._on_domain_failure)
        self._metrics.record_subsystem_registered()
        record_isolation_trace("subsystem-registered", subsystem)
        return domain

    def supervisor(self, subsystem: str) -> RecoverySupervisor:
        with self._lock:
            entry = self._subsystems[subsystem]
            return entry.supervisor

    def domain(self, subsystem: str) -> FailureDomain:
        with self._lock:
            return self._subsystems[subsystem].domain

    # ── canonical subsystem adapters ─────────────────────────────

    def replay(self) -> ReplayFailureIsolation:
        with self._lock:
            if self._replay_adapter is None:
                self._replay_adapter = ReplayFailureIsolation(
                    self.register(SubsystemId.REPLAY.value),
                )
            return self._replay_adapter

    def websocket(self) -> WebsocketFailureIsolation:
        with self._lock:
            if self._websocket_adapter is None:
                self._websocket_adapter = WebsocketFailureIsolation(
                    self.register(SubsystemId.WEBSOCKET.value),
                )
            return self._websocket_adapter

    def reducer(self) -> ReducerFailureIsolation:
        with self._lock:
            if self._reducer_adapter is None:
                self._reducer_adapter = ReducerFailureIsolation(
                    self.register(SubsystemId.REDUCER.value),
                )
            return self._reducer_adapter

    def render(self) -> RenderFailureIsolation:
        with self._lock:
            if self._render_adapter is None:
                self._render_adapter = RenderFailureIsolation(
                    self.register(SubsystemId.RENDER.value),
                )
            return self._render_adapter

    def recorder(self) -> RecorderFailureIsolation:
        with self._lock:
            if self._recorder_adapter is None:
                self._recorder_adapter = RecorderFailureIsolation(
                    self.register(SubsystemId.RECORDER.value),
                )
            return self._recorder_adapter

    # ── boundary helpers ─────────────────────────────────────────

    def boundary(
        self,
        subsystem: str,
        *,
        payload_kind: str = "",
        suppress: bool = True,
        swallow_unavailable: bool = True,
    ) -> SubsystemBoundary:
        """Sync boundary suitable for ``with manager.boundary("x"):``.

        ``swallow_unavailable=True`` (default) means the boundary
        silently no-ops when the breaker is open. ``False`` makes
        :class:`SubsystemUnavailable` propagate to the caller —
        useful for session-loop boundaries that should exit when
        the subsystem is unavailable."""
        domain = self.register(subsystem)
        return SubsystemBoundary(
            domain,
            payload_kind=payload_kind,
            suppress=suppress,
            on_failure=None,
            swallow_unavailable=swallow_unavailable,
        )

    def async_boundary(
        self,
        subsystem: str,
        *,
        payload_kind: str = "",
        suppress: bool = False,
        swallow_unavailable: bool = False,
    ) -> AsyncSubsystemBoundary:
        domain = self.register(subsystem)
        return AsyncSubsystemBoundary(
            domain,
            payload_kind=payload_kind,
            suppress=suppress,
            on_failure=None,
            swallow_unavailable=swallow_unavailable,
        )

    # ── explicit failure reporting ───────────────────────────────

    def report_exception(
        self,
        subsystem: str,
        exc: BaseException,
        *,
        payload_kind: str = "",
    ) -> FailureEvent:
        kind = classify_exception(exc)
        event = FailureEvent(
            subsystem=subsystem,
            kind=kind,
            detail=f"{type(exc).__name__}: {str(exc)[:200]}",
            at_ns=time.monotonic_ns(),
            payload_kind=payload_kind,
            recoverable=kind not in DO_NOT_RETRY,
        )
        self._submit_failure(event)
        return event

    def report_marker(
        self,
        subsystem: str,
        marker: str,
        *,
        payload_kind: str = "",
    ) -> FailureEvent:
        kind = classify_marker(marker)
        event = FailureEvent(
            subsystem=subsystem,
            kind=kind,
            detail=marker,
            at_ns=time.monotonic_ns(),
            payload_kind=payload_kind,
            recoverable=kind not in DO_NOT_RETRY,
        )
        self._submit_failure(event)
        return event

    # ── recovery ─────────────────────────────────────────────────

    def register_recovery(self, subsystem: str, hook: SyncRecoveryHook) -> None:
        self.supervisor(subsystem).register(hook)

    def register_async_recovery(
        self,
        subsystem: str,
        hook: AsyncRecoveryHook,
    ) -> None:
        self.supervisor(subsystem).register_async(hook)

    def attempt_recovery(self, subsystem: str) -> RecoveryOutcome:
        outcome = self.supervisor(subsystem).attempt()
        self._metrics.record_recovery_attempt(outcome.verdict)
        record_isolation_trace(
            "recovery-outcome",
            f"{subsystem}: {outcome.verdict}",
        )
        self._reevaluate_mode()
        return outcome

    async def attempt_recovery_async(self, subsystem: str) -> RecoveryOutcome:
        outcome = await self.supervisor(subsystem).attempt_async()
        self._metrics.record_recovery_attempt(outcome.verdict)
        record_isolation_trace(
            "recovery-outcome",
            f"{subsystem}: {outcome.verdict}",
        )
        self._reevaluate_mode()
        return outcome

    # ── mode ─────────────────────────────────────────────────────

    def mode(self) -> EmergencyMode:
        with self._lock:
            return self._mode

    def force_mode(self, mode: EmergencyMode) -> None:
        self._transition_mode(mode, forced=True)

    def subscribe_mode(self, listener: ModeListener) -> Callable[[], None]:
        with self._lock:
            self._mode_listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._mode_listeners:
                    self._mode_listeners.remove(listener)

        return _unsubscribe

    def backpressure_suggestion(self) -> BackpressureSuggestion:
        return self._isolation_backpressure.current_suggestion()

    def backpressure_bridge(self) -> IsolationBackpressureBridge:
        return self._isolation_backpressure

    # ── diagnostics ──────────────────────────────────────────────

    def diagnostics(self, *, trace_limit: int = 64) -> IsolationDiagnostics:
        with self._lock:
            domains = tuple(entry.domain.snapshot() for entry in self._subsystems.values())
            supervisors = tuple(entry.supervisor.snapshot() for entry in self._subsystems.values())
            mode = self._mode
        findings: list[IntegrityFinding] = []
        for snapshot in domains:
            findings.extend(check_domain(snapshot))
        for snapshot in supervisors:
            findings.extend(check_supervisor(snapshot))
        return build_isolation_diagnostics(
            IsolationDiagnosticsInputs(
                mode=mode,
                metrics=self._metrics.snapshot(),
                domains=domains,
                supervisors=supervisors,
                suggestion=self._isolation_backpressure.current_suggestion(),
                integrity_findings=tuple(findings),
                trace_limit=trace_limit,
            ),
        )

    # ── lifecycle ────────────────────────────────────────────────

    def reset(self) -> None:
        with self._lock:
            for entry in self._subsystems.values():
                entry.domain.reset()
                entry.supervisor.clear_hooks()
                entry.supervisor.reset_abandoned()
            self._mode = "normal"
        self._isolation_backpressure.on_mode_change("normal")
        record_isolation_trace("diagnostic", "manager-reset")

    # ── internals ────────────────────────────────────────────────

    def _submit_failure(self, event: FailureEvent) -> None:
        """Explicit failure reporting (used by
        :meth:`report_exception` + :meth:`report_marker`). Hands off
        to the domain; the domain-level listener performs the
        bookkeeping."""
        domain = self.register(event.subsystem)
        domain.record_failure(event)

    def _on_domain_failure(
        self,
        event: FailureEvent,
        previous_state: BreakerState,
        new_state: BreakerState,
    ) -> None:
        """Single source of truth for failure bookkeeping —
        registered with every domain at construction time."""
        self._metrics.record_failure(event.subsystem, event.kind.value)
        record_isolation_trace(
            "failure-observed",
            f"{event.subsystem}:{event.kind.value}:{event.detail[:80]}",
        )
        if previous_state != BreakerState.OPEN and new_state == BreakerState.OPEN:
            self._metrics.record_breaker_trip()
            record_isolation_trace("breaker-trip", event.subsystem)
        elif previous_state == BreakerState.OPEN and new_state != BreakerState.OPEN:
            self._metrics.record_breaker_close()
            record_isolation_trace("breaker-close", event.subsystem)
        if event.payload_kind and event.kind == FailureKind.CORRUPTION:
            self._metrics.record_payload_quarantine()
            record_isolation_trace(
                "payload-quarantined",
                f"{event.subsystem}:{event.payload_kind}",
            )
        self._reevaluate_mode()

    def _reevaluate_mode(self) -> None:
        with self._lock:
            states = {name: entry.domain.breaker.state for name, entry in self._subsystems.items()}
            new_mode = derive_runtime_mode(
                states=states,
                halt_on_critical=self._config.halt_on_critical_subsystem,
            )
        self._transition_mode(new_mode)

    def _transition_mode(self, target: EmergencyMode, *, forced: bool = False) -> None:
        with self._lock:
            if self._mode == target and not forced:
                return
            self._mode = target
            listeners = tuple(self._mode_listeners)
        self._metrics.record_mode_transition(target)
        record_isolation_trace("mode-transition", target)
        self._isolation_backpressure.on_mode_change(target)
        for listener in listeners:
            with contextlib.suppress(Exception):
                listener(target)


def _domain_snapshots(manager: RuntimeFailureManager) -> tuple[FailureDomainSnapshot, ...]:
    """Test helper — returns every domain snapshot in a stable order."""
    return tuple(entry.domain.snapshot() for entry in manager._subsystems.values())


def _supervisor_snapshots(manager: RuntimeFailureManager) -> tuple[SupervisorSnapshot, ...]:
    """Test helper — returns every supervisor snapshot."""
    return tuple(entry.supervisor.snapshot() for entry in manager._subsystems.values())
