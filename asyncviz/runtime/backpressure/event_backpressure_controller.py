"""Canonical EventBackpressureController.

Composes every backpressure piece into one cohesive public API:

    controller = EventBackpressureController(config=default_config())
    bus_channel = controller.register_channel("bus", capacity=8192)
    ws_registry = controller.attach_websocket_registry()
    recorder_adapter = controller.attach_recorder_adapter()
    reducer_adapter = controller.attach_reducer_adapter("tasks")

    # Periodic tick — call once per pressure-sampling interval.
    snapshot = controller.tick()
    if snapshot.emergency:
        ...
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable

from asyncviz.runtime.backpressure.adaptive_backpressure import (
    ActionListener,
    AdaptiveBackpressureController,
)
from asyncviz.runtime.backpressure.backpressure_budget import (
    BackpressureBudget,
)
from asyncviz.runtime.backpressure.backpressure_configuration import (
    BackpressureConfig,
    DropPolicy,
    default_config,
)
from asyncviz.runtime.backpressure.backpressure_diagnostics import (
    BackpressureDiagnostics,
    build_backpressure_diagnostics,
)
from asyncviz.runtime.backpressure.backpressure_observability import (
    get_backpressure_metrics,
)
from asyncviz.runtime.backpressure.backpressure_tracing import (
    record_backpressure_trace,
)
from asyncviz.runtime.backpressure.bounded_event_channel import (
    BoundedEventChannel,
    ChannelStats,
)
from asyncviz.runtime.backpressure.models.degradation_action import (
    DegradationAction,
)
from asyncviz.runtime.backpressure.models.overload_state import (
    OverloadSnapshot,
    OverloadState,
)
from asyncviz.runtime.backpressure.reducer_backpressure import (
    ReducerBackpressureAdapter,
)
from asyncviz.runtime.backpressure.replay_backpressure import (
    ReplayBackpressureAdapter,
)
from asyncviz.runtime.backpressure.topology_backpressure import (
    BoundedTopologyView,
)
from asyncviz.runtime.backpressure.websocket_backpressure import (
    WebsocketBackpressureRegistry,
)


class EventBackpressureController:
    """Top-level overload-protection façade."""

    __slots__ = (
        "_adaptive",
        "_budget",
        "_channels",
        "_config",
        "_lock",
        "_recorder_adapter",
        "_reducer_adapters",
        "_topology_view",
        "_unsubscribe_actions",
        "_websocket_registry",
    )

    def __init__(self, config: BackpressureConfig | None = None) -> None:
        cfg = config or default_config()
        self._config = cfg
        self._adaptive = AdaptiveBackpressureController(config=cfg)
        self._budget = BackpressureBudget()
        self._channels: dict[str, BoundedEventChannel] = {}
        self._reducer_adapters: dict[str, ReducerBackpressureAdapter] = {}
        self._websocket_registry: WebsocketBackpressureRegistry | None = None
        self._recorder_adapter: ReplayBackpressureAdapter | None = None
        self._topology_view: BoundedTopologyView | None = None
        self._lock = threading.RLock()

        get_backpressure_metrics().record_controller_started()
        record_backpressure_trace(
            "controller-started",
            f"config_capacity={cfg.bus_capacity}",
        )
        # Wire the action listener into our own metrics layer.
        self._unsubscribe_actions = self._adaptive.subscribe_actions(
            self._on_action,
        )

    # ── channel registration ──────────────────────────────────────

    def register_channel(
        self,
        name: str,
        *,
        capacity: int | None = None,
        policy: DropPolicy | None = None,
    ) -> BoundedEventChannel:
        """Register + wire a bounded channel as a pressure source."""
        with self._lock:
            if name in self._channels:
                return self._channels[name]
            channel: BoundedEventChannel = BoundedEventChannel(
                name,
                capacity=capacity or self._config.bus_capacity,
                policy=policy or self._config.bus_drop_policy,
            )
            self._channels[name] = channel
        # Register as a pressure source so the controller's tick
        # samples its depth.
        self._adaptive.register_source(
            name,
            lambda c=channel: c.depth,
            capacity=channel.capacity,
        )
        return channel

    def channel(self, name: str) -> BoundedEventChannel | None:
        with self._lock:
            return self._channels.get(name)

    def channels(self) -> tuple[BoundedEventChannel, ...]:
        with self._lock:
            return tuple(self._channels.values())

    # ── per-subsystem adapters ────────────────────────────────────

    def attach_websocket_registry(
        self,
        *,
        policy: DropPolicy | None = None,
    ) -> WebsocketBackpressureRegistry:
        with self._lock:
            if self._websocket_registry is None:
                self._websocket_registry = WebsocketBackpressureRegistry(
                    self._config,
                    policy=policy,
                )
                # Aggregate websocket-side pressure as max across all
                # subscribers.
                registry = self._websocket_registry
                self._adaptive.register_source(
                    "websocket",
                    lambda r=registry: int(r.max_pressure_ratio() * 100),
                    capacity=100,
                )
            return self._websocket_registry

    def attach_recorder_adapter(
        self,
        *,
        policy: DropPolicy | None = None,
    ) -> ReplayBackpressureAdapter:
        with self._lock:
            if self._recorder_adapter is None:
                self._recorder_adapter = ReplayBackpressureAdapter(
                    self._config,
                    policy=policy,
                )
                adapter = self._recorder_adapter
                self._adaptive.register_source(
                    "recorder",
                    lambda a=adapter: a.channel.depth,
                    capacity=adapter.channel.capacity,
                )
            return self._recorder_adapter

    def attach_reducer_adapter(
        self,
        name: str,
        *,
        capacity: int | None = None,
        policy: DropPolicy | None = None,
    ) -> ReducerBackpressureAdapter:
        with self._lock:
            adapter = self._reducer_adapters.get(name)
            if adapter is not None:
                return adapter
            adapter = ReducerBackpressureAdapter(
                name,
                self._config,
                capacity=capacity,
                policy=policy,
            )
            self._reducer_adapters[name] = adapter
        self._adaptive.register_source(
            f"reducer:{name}",
            lambda a=adapter: a.channel.depth,
            capacity=adapter.channel.capacity,
        )
        return adapter

    def attach_topology_view(
        self,
        *,
        capacity: int = 65_536,
    ) -> BoundedTopologyView:
        with self._lock:
            if self._topology_view is None:
                self._topology_view = BoundedTopologyView(capacity=capacity)
            return self._topology_view

    # ── control surface ──────────────────────────────────────────

    def tick(self) -> OverloadSnapshot:
        return self._adaptive.tick()

    @property
    def state(self) -> OverloadState:
        return self._adaptive.state

    def subscribe_actions(
        self,
        listener: ActionListener,
    ) -> Callable[[], None]:
        return self._adaptive.subscribe_actions(listener)

    # ── recording helpers ────────────────────────────────────────

    def record_event_outcome(
        self,
        *,
        accepted: bool,
        evicted: bool,
    ) -> None:
        metrics = get_backpressure_metrics()
        if accepted:
            self._budget.record_accepted()
            metrics.record_event_accepted()
            if evicted:
                self._budget.record_overflowed()
                metrics.record_event_evicted()
                record_backpressure_trace(
                    "event-evicted",
                    f"state={self.state.name}",
                )
        else:
            self._budget.record_rejected()
            metrics.record_event_rejected()
            record_backpressure_trace(
                "event-rejected",
                f"state={self.state.name}",
            )

    # ── diagnostics ──────────────────────────────────────────────

    def diagnostics(self, *, trace_limit: int = 32) -> BackpressureDiagnostics:
        snap = self._adaptive.detector.snapshot()
        channel_stats: list[ChannelStats] = [ch.stats() for ch in self.channels()]
        if self._websocket_registry is not None:
            for ch in self._websocket_registry.all():
                channel_stats.append(ch.channel.stats())
        if self._recorder_adapter is not None:
            channel_stats.append(self._recorder_adapter.channel.stats())
        for adapter in tuple(self._reducer_adapters.values()):
            channel_stats.append(adapter.channel.stats())
        return build_backpressure_diagnostics(
            overload=snap,
            channels=tuple(channel_stats),
            notes={
                "budget_snapshot": str(self._budget.snapshot()),
            },
            trace_limit=trace_limit,
        )

    # ── lifecycle ────────────────────────────────────────────────

    def reset(self) -> None:
        with self._lock:
            for channel in self._channels.values():
                channel.clear()
            self._channels.clear()
            for adapter in self._reducer_adapters.values():
                adapter.reset()
            self._reducer_adapters.clear()
            if self._websocket_registry is not None:
                self._websocket_registry.reset()
            if self._recorder_adapter is not None:
                self._recorder_adapter.reset()
            if self._topology_view is not None:
                self._topology_view.clear()
            self._budget.reset()
        self._adaptive.reset()
        get_backpressure_metrics().record_controller_reset()
        record_backpressure_trace("controller-reset", "")

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._unsubscribe_actions()

    # ── internals ────────────────────────────────────────────────

    def _on_action(
        self,
        action: DegradationAction,
        snapshot: OverloadSnapshot,
    ) -> None:
        metrics = get_backpressure_metrics()
        metrics.record_action_dispatched()
        record_backpressure_trace(
            "action-dispatched",
            f"kind={action.kind} state={snapshot.state.name}",
        )
        # State-transition bookkeeping.
        emergency = snapshot.state == OverloadState.EMERGENCY
        metrics.record_state_transition(emergency=emergency)
        # When emergency action is "disconnect-slow-clients", apply it.
        if action.kind == "disconnect-slow-clients" and self._websocket_registry is not None:
            disconnected = self._websocket_registry.disconnect_slow_clients()
            for _ in range(disconnected):
                metrics.record_websocket_disconnect()
                record_backpressure_trace(
                    "subscriber-disconnected",
                    f"state={snapshot.state.name}",
                )

    @property
    def adaptive(self) -> AdaptiveBackpressureController:
        return self._adaptive

    @property
    def budget(self) -> BackpressureBudget:
        return self._budget

    @property
    def config(self) -> BackpressureConfig:
        return self._config
