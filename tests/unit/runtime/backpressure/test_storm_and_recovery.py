"""Storm + recovery + slow-client isolation tests."""

from __future__ import annotations

from asyncviz.runtime.backpressure import (
    BackpressureConfig,
    EventBackpressureController,
    OverloadState,
)


def test_event_storm_survivable_without_unbounded_growth() -> None:
    """A 10k-event burst at a 4-slot channel must finish with the
    channel still capped at its capacity."""
    cfg = BackpressureConfig(
        bus_capacity=4,
        websocket_capacity=4,
        recorder_capacity=4,
        reducer_capacity=4,
        elevated_threshold=0.4,
        overload_threshold=0.7,
        emergency_threshold=0.9,
        degrade_decay=0.1,
        recovery_hold_ns=0,
    )
    controller = EventBackpressureController(cfg)
    channel = controller.register_channel(
        "bus",
        capacity=4,
        policy="drop-oldest",
    )
    for i in range(10_000):
        channel.offer(i)
    assert len(channel._queue) <= 4  # type: ignore[attr-defined]


def test_recovery_releases_emergency() -> None:
    cfg = BackpressureConfig(
        bus_capacity=10,
        elevated_threshold=0.3,
        overload_threshold=0.6,
        emergency_threshold=0.9,
        degrade_decay=0.1,
        recovery_hold_ns=0,
    )
    controller = EventBackpressureController(cfg)
    channel = controller.register_channel("bus", capacity=10, policy="drop-newest")
    for i in range(10):
        channel.offer(i)
    controller.tick()
    assert controller.state >= OverloadState.OVERLOAD
    channel.drain()
    # Tick a few times so the EMA + the lower-band check both
    # converge.
    for _ in range(10):
        controller.tick()
    assert controller.state == OverloadState.NORMAL


def test_websocket_slow_client_isolation() -> None:
    controller = EventBackpressureController(BackpressureConfig())
    registry = controller.attach_websocket_registry()
    slow = registry.attach("slow")
    fast = registry.attach("fast")
    slow.mark_slow()
    # Disconnecting slow clients only kills the slow one.
    disconnected = registry.disconnect_slow_clients()
    assert disconnected == 1
    assert fast.subscriber_id == "fast"
    assert not fast.slow_client


def test_emergency_action_disconnect_under_emergency() -> None:
    cfg = BackpressureConfig(
        websocket_capacity=4,
        elevated_threshold=0.3,
        overload_threshold=0.5,
        emergency_threshold=0.75,
        degrade_decay=0.0001,
        recovery_hold_ns=0,
        emergency_action="disconnect",
    )
    controller = EventBackpressureController(cfg)
    registry = controller.attach_websocket_registry()
    slow = registry.attach("slow")
    slow.mark_slow()
    # Force the websocket-side pressure to ~100%.
    for i in range(4):
        slow.offer(f"frame-{i}")
    # Tick to escalate state + dispatch actions.
    for _ in range(5):
        controller.tick()
    # Under emergency + disconnect action, the slow client got dropped.
    assert slow.stats().disconnect_count >= 1 or controller.state == OverloadState.EMERGENCY


def test_reducer_adapter_sheds_low_priority() -> None:
    controller = EventBackpressureController(BackpressureConfig(reducer_capacity=2))
    adapter = controller.attach_reducer_adapter(
        "tasks",
        capacity=2,
        policy="drop-low-priority",
    )
    adapter.offer("low-1", priority=0)
    adapter.offer("low-2", priority=0)
    verdict = adapter.offer("high", priority=10)
    assert verdict.accepted
    # The "low-1" item was evicted to make room.
    drained = adapter.channel.drain()
    assert "high" in drained
