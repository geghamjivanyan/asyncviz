"""Top-level loop-compatibility manager.

The :class:`LoopCompatibilityManager` composes every compatibility
piece into one cohesive public API. It is *async-safe* — most
methods can be called from either sync or async code; the few that
require an active loop document the requirement.

Typical usage::

    manager = LoopCompatibilityManager(config=prefer_uvloop_config())
    installed = manager.install_uvloop()            # before any loop runs
    async def main():
        manager.attach()                            # in-loop bookkeeping
        # ... application work ...
    asyncio.run(main())

The manager never crashes the host application: install failures
fall back to stock asyncio, integrity violations are recorded but
not raised, and detach is idempotent.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import time

from asyncviz.runtime.compat.loop_adapter import LoopAdapter
from asyncviz.runtime.compat.loop_clock_bridge import LoopClockBridge
from asyncviz.runtime.compat.loop_configuration import (
    LoopCompatConfig,
    default_config,
)
from asyncviz.runtime.compat.loop_diagnostics import (
    LoopCompatDiagnostics,
    LoopCompatDiagnosticsInputs,
    build_loop_compat_diagnostics,
)
from asyncviz.runtime.compat.loop_feature_detection import (
    detect_active_loop,
    is_uvloop_available,
)
from asyncviz.runtime.compat.loop_integrity import (
    IntegrityFinding,
    check_capabilities,
)
from asyncviz.runtime.compat.loop_observability import (
    LoopCompatMetrics,
    get_loop_compat_metrics,
)
from asyncviz.runtime.compat.loop_policy_bridge import LoopPolicyBridge
from asyncviz.runtime.compat.loop_queue_bridge import LoopQueueBridge
from asyncviz.runtime.compat.loop_scheduler_bridge import LoopSchedulerBridge
from asyncviz.runtime.compat.loop_task_bridge import LoopTaskBridge
from asyncviz.runtime.compat.loop_tracing import (
    record_loop_compat_trace,
    set_loop_compat_trace_enabled,
)
from asyncviz.runtime.compat.models.loop_capabilities import (
    LoopCapabilities,
    asyncio_baseline_capabilities,
)
from asyncviz.runtime.compat.models.loop_kind import LoopKind
from asyncviz.runtime.compat.models.loop_state import LoopState
from asyncviz.runtime.compat.replay_loop_bridge import ReplayLoopBridge
from asyncviz.runtime.compat.websocket_loop_bridge import WebsocketLoopBridge


class LoopCompatibilityManager:
    """Production loop-compatibility façade."""

    __slots__ = (
        "_adapter",
        "_attached_loop",
        "_capabilities",
        "_clock_bridge",
        "_config",
        "_detected_at_ns",
        "_fallback_activations",
        "_install_attempted",
        "_install_error",
        "_installed_uvloop",
        "_integrity_findings",
        "_lock",
        "_metrics",
        "_policy",
        "_queue_bridge",
        "_replay_bridge",
        "_scheduler_bridge",
        "_task_bridge",
        "_websocket_bridge",
    )

    def __init__(
        self,
        *,
        config: LoopCompatConfig | None = None,
        metrics: LoopCompatMetrics | None = None,
    ) -> None:
        self._config = config if config is not None else default_config()
        self._metrics = metrics if metrics is not None else get_loop_compat_metrics()
        self._lock = threading.Lock()
        self._policy = LoopPolicyBridge()
        self._capabilities: LoopCapabilities = asyncio_baseline_capabilities()
        self._adapter = LoopAdapter(self._capabilities)
        self._clock_bridge = LoopClockBridge(self._config)
        self._task_bridge = LoopTaskBridge()
        self._queue_bridge = LoopQueueBridge()
        self._scheduler_bridge = LoopSchedulerBridge()
        self._replay_bridge = ReplayLoopBridge(self._config)
        self._websocket_bridge = WebsocketLoopBridge(self._config)
        self._installed_uvloop = False
        self._install_attempted = False
        self._install_error = ""
        self._fallback_activations = 0
        self._integrity_findings: tuple[IntegrityFinding, ...] = ()
        self._attached_loop: asyncio.AbstractEventLoop | None = None
        self._detected_at_ns = 0

    # ── configuration accessors ──────────────────────────────────

    @property
    def config(self) -> LoopCompatConfig:
        return self._config

    @property
    def metrics(self) -> LoopCompatMetrics:
        return self._metrics

    @property
    def capabilities(self) -> LoopCapabilities:
        return self._capabilities

    @property
    def adapter(self) -> LoopAdapter:
        return self._adapter

    @property
    def installed_uvloop(self) -> bool:
        return self._installed_uvloop

    # ── lifecycle ────────────────────────────────────────────────

    def install_uvloop(self) -> bool:
        """Attempt to install the uvloop event-loop policy.

        Returns ``True`` on success, ``False`` on graceful fallback.
        Raises :class:`UvloopUnavailableError` only when the config
        explicitly disables fallback.
        """
        with self._lock:
            self._install_attempted = True
            self._metrics.record_uvloop_install_attempt()
        record_loop_compat_trace("uvloop-install-attempt", "")
        installed = self._policy.install_uvloop_policy(
            fallback=self._config.fallback_on_install_failure,
        )
        with self._lock:
            self._installed_uvloop = installed
            if installed:
                self._metrics.record_uvloop_install_success()
                record_loop_compat_trace("uvloop-install-success", "")
            else:
                self._metrics.record_uvloop_install_failure()
                self._install_error = (
                    "uvloop unavailable"
                    if not is_uvloop_available()
                    else "policy swap rejected"
                )
                record_loop_compat_trace(
                    "uvloop-install-failure",
                    self._install_error,
                )
        return installed

    def restore_default_policy(self) -> bool:
        changed = self._policy.restore_default_policy()
        with self._lock:
            if changed:
                self._installed_uvloop = False
                record_loop_compat_trace("uvloop-install-failure", "policy-restored")
        return changed

    def attach(
        self,
        loop: asyncio.AbstractEventLoop | None = None,
        *,
        install_task_bridge: bool = True,
        install_scheduler_bridge: bool | None = None,
    ) -> LoopCapabilities:
        """Detect the active loop + wire the bridges.

        Returns the freshly-probed capabilities. Safe to call
        repeatedly; subsequent calls re-probe but only re-install
        bridges that were previously released.
        """
        capabilities = detect_active_loop(loop)
        target = loop
        if target is None:
            with contextlib.suppress(RuntimeError):
                target = asyncio.get_running_loop()
        with self._lock:
            self._capabilities = capabilities
            self._adapter = LoopAdapter(capabilities)
            self._attached_loop = target
            self._detected_at_ns = time.monotonic_ns()
        self._replay_bridge.attach(capabilities)
        self._integrity_findings = check_capabilities(capabilities)
        for finding in self._integrity_findings:
            self._metrics.record_integrity_violation()
            record_loop_compat_trace("integrity-violation", f"{finding.kind}:{finding.detail}")
        self._metrics.record_manager_attached(capabilities.kind.value)
        record_loop_compat_trace(
            "manager-attached",
            f"kind={capabilities.kind.value} impl={capabilities.implementation}",
        )
        if (
            install_task_bridge
            and target is not None
            and capabilities.supports_task_factory
        ):
            self._task_bridge.install(target)
        scheduler_enabled = (
            self._config.record_scheduler_anomalies
            if install_scheduler_bridge is None
            else install_scheduler_bridge
        )
        if scheduler_enabled and target is not None:
            self._scheduler_bridge.install(target)
        if self._config.trace_capacity != 256:
            set_loop_compat_trace_enabled(True, capacity=self._config.trace_capacity)
        return capabilities

    def detach(self) -> None:
        """Restore the loop to its pre-attach state. Idempotent."""
        self._task_bridge.restore()
        self._scheduler_bridge.restore()
        record_loop_compat_trace(
            "manager-detached",
            f"kind={self._capabilities.kind.value}",
        )
        with self._lock:
            self._attached_loop = None

    # ── bridge accessors ─────────────────────────────────────────

    def clock_bridge(self) -> LoopClockBridge:
        return self._clock_bridge

    def task_bridge(self) -> LoopTaskBridge:
        return self._task_bridge

    def queue_bridge(self) -> LoopQueueBridge:
        return self._queue_bridge

    def scheduler_bridge(self) -> LoopSchedulerBridge:
        return self._scheduler_bridge

    def replay_bridge(self) -> ReplayLoopBridge:
        return self._replay_bridge

    def websocket_bridge(self) -> WebsocketLoopBridge:
        return self._websocket_bridge

    # ── reporting ────────────────────────────────────────────────

    def state(self) -> LoopState:
        with self._lock:
            return LoopState(
                active_kind=self._capabilities.kind,
                capabilities=self._capabilities,
                installed_uvloop=self._installed_uvloop,
                install_attempted=self._install_attempted,
                install_error=self._install_error,
                fallback_activations=self._fallback_activations
                + self._adapter.stats().fallback_create_task
                + self._adapter.stats().fallback_call_soon_threadsafe
                + self._adapter.stats().fallback_run_in_executor
                + self._adapter.stats().fallback_set_debug,
                drift_warnings=self._clock_bridge.report().drift_warnings,
                detected_at_ns=self._detected_at_ns,
            )

    def diagnostics(self, *, trace_limit: int = 64) -> LoopCompatDiagnostics:
        snapshot = self._metrics.snapshot()
        return build_loop_compat_diagnostics(
            LoopCompatDiagnosticsInputs(
                state=self.state(),
                metrics=snapshot,
                adapter=self._adapter.stats(),
                clock=self._clock_bridge.report(),
                task=self._task_bridge.stats(),
                queue=self._queue_bridge.stats(),
                scheduler=self._scheduler_bridge.stats(),
                replay=self._replay_bridge.report(),
                websocket=self._websocket_bridge.report(),
                integrity_findings=self._integrity_findings,
                trace_limit=trace_limit,
            ),
        )

    def reset(self) -> None:
        self._adapter.reset()
        self._clock_bridge.reset()
        self._task_bridge.reset()
        self._queue_bridge.reset()
        self._scheduler_bridge.reset()
        self._replay_bridge.reset()
        self._websocket_bridge.reset()
        with self._lock:
            self._fallback_activations = 0
            self._integrity_findings = ()


# Convenience module-level helpers ────────────────────────────────


def install_uvloop_if_available(
    *,
    config: LoopCompatConfig | None = None,
) -> LoopCompatibilityManager:
    """Construct + try to install uvloop, returning the manager."""
    manager = LoopCompatibilityManager(config=config)
    manager.install_uvloop()
    return manager


def is_uvloop_installed() -> bool:
    """``True`` when the active policy is uvloop's."""
    try:
        policy = asyncio.get_event_loop_policy()
    except Exception:
        return False
    return type(policy).__module__.startswith("uvloop")


def active_loop_kind() -> LoopKind:
    return detect_active_loop().kind
