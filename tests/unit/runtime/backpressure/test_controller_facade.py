"""End-to-end controller tests."""

from __future__ import annotations

from asyncviz.runtime.backpressure import (
    DegradationAction,
    EventBackpressureController,
    OverloadState,
    get_backpressure_metrics_snapshot,
)


def test_controller_starts_in_normal_state(
    controller: EventBackpressureController,
) -> None:
    assert controller.state == OverloadState.NORMAL


def test_controller_registers_channel(
    controller: EventBackpressureController,
) -> None:
    channel = controller.register_channel("bus")
    assert channel.name == "bus"
    again = controller.register_channel("bus")
    assert again is channel


def test_controller_detects_overload(
    controller: EventBackpressureController,
) -> None:
    channel = controller.register_channel(
        "bus",
        capacity=4,
        policy="drop-newest",
    )
    for i in range(4):
        channel.offer(i)
    # Channel is at 100% capacity; tick should escalate.
    snap = controller.tick()
    assert snap.state >= OverloadState.OVERLOAD


def test_controller_recovers_after_drain(
    controller: EventBackpressureController,
) -> None:
    channel = controller.register_channel("bus", capacity=4, policy="drop-newest")
    for i in range(4):
        channel.offer(i)
    controller.tick()
    assert controller.state >= OverloadState.OVERLOAD
    channel.drain()
    for _ in range(10):
        controller.tick()
    assert controller.state == OverloadState.NORMAL


def test_action_listener_receives_degradation(
    controller: EventBackpressureController,
) -> None:
    received: list[DegradationAction] = []
    controller.subscribe_actions(lambda action, snap: received.append(action))
    channel = controller.register_channel("bus", capacity=4, policy="drop-newest")
    for i in range(4):
        channel.offer(i)
    controller.tick()
    assert len(received) > 0
    kinds = {action.kind for action in received}
    assert "tighten-sampling" in kinds


def test_websocket_registry_attached_and_used(
    controller: EventBackpressureController,
) -> None:
    registry = controller.attach_websocket_registry()
    sub = registry.attach("sub-a")
    assert sub.subscriber_id == "sub-a"


def test_recorder_adapter_attached_and_records_drops(
    controller: EventBackpressureController,
) -> None:
    adapter = controller.attach_recorder_adapter()
    # Emit enough drops to trigger a marker.
    for i in range(1, adapter._marker_window + 1):
        marker = adapter.record_drop(sequence=i, state=OverloadState.OVERLOAD)
    assert marker is not None
    assert marker.dropped == adapter._marker_window
    assert marker.subsystem == "recorder"


def test_reducer_adapter_attached(
    controller: EventBackpressureController,
) -> None:
    adapter = controller.attach_reducer_adapter("tasks")
    verdict = adapter.offer("payload", priority=10)
    assert verdict.accepted


def test_topology_view_caps_growth(
    controller: EventBackpressureController,
) -> None:
    view = controller.attach_topology_view(capacity=2)
    view.upsert("a", {"x": 1})
    view.upsert("b", {"x": 2})
    view.upsert("c", {"x": 3})
    assert len(view) == 2
    assert view.stats().evicted_total == 1


def test_diagnostics_returns_combined_view(
    controller: EventBackpressureController,
) -> None:
    controller.register_channel("bus")
    diag = controller.diagnostics()
    assert diag.metrics is not None
    assert diag.overload is not None
    assert len(diag.channels) >= 1


def test_metrics_track_lifecycle(
    controller: EventBackpressureController,
) -> None:
    snap = get_backpressure_metrics_snapshot()
    assert snap.controllers_started >= 1


def test_reset_clears_state(
    controller: EventBackpressureController,
) -> None:
    channel = controller.register_channel("bus", capacity=4)
    channel.offer("x")
    controller.reset()
    assert controller.state == OverloadState.NORMAL
