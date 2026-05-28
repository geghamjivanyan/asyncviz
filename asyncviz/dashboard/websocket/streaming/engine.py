from __future__ import annotations

import asyncio
import contextlib
import threading
from typing import TYPE_CHECKING

from asyncviz.dashboard.websocket.protocol import (
    Envelope,
    metrics_delta as metrics_delta_envelope,
    timeline_delta as timeline_delta_envelope,
    warning_delta as warning_delta_envelope,
)
from asyncviz.dashboard.websocket.streaming.envelopes import (
    metrics_delta_payload,
    warning_delta_payload,
)
from asyncviz.dashboard.websocket.streaming.metrics import (
    StreamingMetrics,
    StreamingMetricsSnapshot,
)
from asyncviz.runtime.timeline.streaming import TimelineDelta
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.dashboard.websocket.manager import ConnectionManager
    from asyncviz.runtime.clock import RuntimeClock
    from asyncviz.runtime.metrics import MetricsDelta, RuntimeMetricsAggregator
    from asyncviz.runtime.timeline import TimelineSegmentEngine
    from asyncviz.runtime.warnings import RuntimeWarningManager, WarningDelta

logger = get_logger("dashboard.websocket.streaming.engine")


class RuntimeStreamingEngine:
    """Canonical realtime streaming layer.

    Subscribes to:

    * :class:`RuntimeMetricsAggregator` → emits ``metrics_delta`` envelopes.
    * :class:`RuntimeWarningManager` → emits ``warning_delta`` envelopes.
    * :class:`TimelineSegmentEngine` → emits ``timeline_delta`` envelopes.

    Each delta is wrapped in a typed :class:`Envelope` and broadcast via
    :class:`ConnectionManager.broadcast` — the same fanout the
    :class:`WebSocketBridge` uses for raw ``runtime_event`` envelopes.

    Lifecycle::

        engine = RuntimeStreamingEngine(...)
        engine.start()  # binds subscriptions
        ...
        engine.stop()   # tears down subscriptions
    """

    def __init__(
        self,
        *,
        manager: ConnectionManager,
        clock: RuntimeClock,
        metrics_aggregator: RuntimeMetricsAggregator | None = None,
        warning_manager: RuntimeWarningManager | None = None,
        timeline_engine: TimelineSegmentEngine | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._manager = manager
        self._clock = clock
        self._metrics_aggregator = metrics_aggregator
        self._warning_manager = warning_manager
        self._timeline_engine = timeline_engine
        self._loop = loop
        self._lock = threading.Lock()
        self._metrics = StreamingMetrics()
        self._metrics_subscription = None
        self._warning_subscription = None
        self._timeline_subscription = None
        self._running = False

    # ── identity ─────────────────────────────────────────────────────────
    @property
    def metrics(self) -> StreamingMetrics:
        return self._metrics

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    # ── lifecycle ────────────────────────────────────────────────────────
    def start(self, *, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Bind subscriptions to the configured runtime services.

        Call from the dashboard lifespan after the event bus is up.
        Idempotent — calling twice is a no-op.
        """
        with self._lock:
            if self._running:
                return
            self._loop = loop or self._loop or asyncio.get_event_loop()
            if self._metrics_aggregator is not None:
                self._metrics_subscription = self._metrics_aggregator.subscribe(
                    self._on_metrics_delta
                )
            if self._warning_manager is not None:
                self._warning_subscription = self._warning_manager.subscribe(self._on_warning_delta)
            if self._timeline_engine is not None:
                self._timeline_subscription = self._timeline_engine.subscribe(
                    self._on_timeline_delta
                )
            self._running = True
        logger.debug("streaming engine started")

    def stop(self) -> None:
        """Tear down every subscription. Idempotent."""
        with self._lock:
            if not self._running:
                return
            if self._metrics_subscription is not None and self._metrics_aggregator is not None:
                self._metrics_aggregator.unsubscribe(self._metrics_subscription)
            if self._warning_subscription is not None and self._warning_manager is not None:
                self._warning_manager.unsubscribe(self._warning_subscription)
            if self._timeline_subscription is not None and self._timeline_engine is not None:
                self._timeline_engine.unsubscribe(self._timeline_subscription)
            self._metrics_subscription = None
            self._warning_subscription = None
            self._timeline_subscription = None
            self._running = False
        logger.debug("streaming engine stopped")

    # ── delta entry points ──────────────────────────────────────────────
    def _on_metrics_delta(self, delta: MetricsDelta) -> None:
        try:
            payload = metrics_delta_payload(delta)
        except Exception as exc:
            logger.warning("metrics delta serialization failed: %s", exc)
            self._metrics.record_subscription_dispatch(failed=True)
            return
        envelope = metrics_delta_envelope(payload, sequence=delta.sequence)
        self._schedule_broadcast(envelope, kind="metrics")

    def _on_warning_delta(self, delta: WarningDelta) -> None:
        try:
            payload = warning_delta_payload(delta)
        except Exception as exc:
            logger.warning("warning delta serialization failed: %s", exc)
            self._metrics.record_subscription_dispatch(failed=True)
            return
        envelope = warning_delta_envelope(payload, sequence=delta.sequence)
        self._schedule_broadcast(envelope, kind="warning")

    def _on_timeline_delta(self, delta: TimelineDelta) -> None:
        try:
            payload = self._timeline_payload(delta)
        except Exception as exc:
            logger.warning("timeline delta serialization failed: %s", exc)
            self._metrics.record_subscription_dispatch(failed=True)
            return
        envelope = timeline_delta_envelope(payload, sequence=delta.sequence)
        self._schedule_broadcast(envelope, kind="timeline")

    # ── helpers ─────────────────────────────────────────────────────────
    def _schedule_broadcast(self, envelope: Envelope, *, kind: str) -> None:
        """Schedule a broadcast on the bound loop.

        Subscribers fire from the loop thread today (state-store + timeline
        engine + aggregator all run synchronously inside the queue's
        dispatcher), but the API is loop-thread-safe via
        ``call_soon_threadsafe`` to keep cross-thread test paths honest.
        """
        if self._loop is None:
            logger.warning("streaming engine has no loop; dropping %s envelope", kind)
            self._metrics.record_broadcast_failure()
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            self._loop.create_task(self._broadcast(envelope, kind=kind))
        else:
            self._loop.call_soon_threadsafe(
                lambda: (
                    self._loop.create_task(self._broadcast(envelope, kind=kind))
                    if self._loop is not None
                    else None
                )
            )

    async def _broadcast(self, envelope: Envelope, *, kind: str) -> None:
        try:
            delivered = await self._manager.broadcast(envelope)
        except Exception as exc:
            logger.warning("streaming broadcast failed for %s: %s", kind, exc)
            self._metrics.record_broadcast_failure()
            self._metrics.record_subscription_dispatch(failed=True)
            return
        # Count per-stream metrics + global dispatch.
        if kind == "metrics":
            self._metrics.record_metrics_delta()
        elif kind == "warning":
            self._metrics.record_warning_delta()
        elif kind == "timeline":
            self._metrics.record_timeline_delta()
        else:
            self._metrics.record_runtime_delta()
        self._metrics.record_subscription_dispatch()
        _ = delivered

    def _timeline_payload(self, delta: TimelineDelta) -> dict:
        out: dict = {
            "kind": delta.kind.value,
            "task_id": delta.task_id,
            "sequence": delta.sequence,
            "monotonic_ns": delta.monotonic_ns,
            "wall_seconds": delta.wall_seconds,
            "closed_a_segment": delta.closed_a_segment,
        }
        if delta.segment is not None:
            out["segment"] = delta.segment.model_dump(mode="json")
        if delta.open_segment is not None:
            out["open_segment"] = delta.open_segment.model_dump(mode="json")
        if delta.terminal_state is not None:
            out["terminal_state"] = delta.terminal_state
        return out

    # ── observability ───────────────────────────────────────────────────
    def metrics_snapshot(self) -> StreamingMetricsSnapshot:
        return self._metrics.snapshot()

    # ── manual broadcast (used for protocol errors / ad-hoc envelopes) ──
    async def emit(self, envelope: Envelope, *, kind: str = "runtime") -> None:
        """Direct broadcast — kept for protocol-error envelopes and tests."""
        with contextlib.suppress(Exception):
            await self._broadcast(envelope, kind=kind)
