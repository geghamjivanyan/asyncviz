"""Event router + websocket bridge + projection tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.runtime import (
    CollectingSink,
    NullSink,
    Projection,
    ProjectionRegistry,
    ReplayEventRouter,
    ReplayWebsocketBridge,
    VirtualRuntimeState,
    default_projection_registry,
    project_counters,
    project_domain,
    project_domain_names,
)


def _frame(seq: int, payload_type: str = "asyncio.task.created") -> ReplayFrame:
    return ReplayFrame.for_runtime_event(
        sequence=seq, monotonic_ns=seq, payload_type=payload_type, payload={"x": 1},
    )


def test_router_wildcard_receives_all_frames() -> None:
    router = ReplayEventRouter()
    received = []
    router.subscribe("*", lambda f: received.append(f.sequence))
    router.publish(_frame(1))
    router.publish(_frame(2, payload_type="asyncio.task.completed"))
    assert received == [1, 2]


def test_router_specific_topic_only_receives_matching() -> None:
    router = ReplayEventRouter()
    received = []
    router.subscribe("asyncio.task.created", lambda f: received.append(f.sequence))
    router.publish(_frame(1))
    router.publish(_frame(2, payload_type="asyncio.task.completed"))
    assert received == [1]


def test_router_unsubscribe_stops_callbacks() -> None:
    router = ReplayEventRouter()
    received = []
    unsub = router.subscribe("*", lambda f: received.append(f.sequence))
    router.publish(_frame(1))
    unsub()
    router.publish(_frame(2))
    assert received == [1]


def test_router_isolates_subscriber_exceptions() -> None:
    router = ReplayEventRouter()
    survived = []

    def boom(_f):
        raise RuntimeError("oh no")

    router.subscribe("*", boom)
    router.subscribe("*", lambda f: survived.append(f.sequence))
    router.publish(_frame(1))
    assert survived == [1]


@pytest.mark.asyncio
async def test_websocket_bridge_pushes_frames_and_state() -> None:
    sink = CollectingSink()
    bridge = ReplayWebsocketBridge(sink)
    await bridge.emit_frame(_frame(1))
    await bridge.emit_state(VirtualRuntimeState(last_sequence=1))
    assert len(sink.frames) == 1
    assert len(sink.states) == 1


@pytest.mark.asyncio
async def test_websocket_null_sink_drops_silently() -> None:
    sink = NullSink()
    bridge = ReplayWebsocketBridge(sink)
    await bridge.emit_frame(_frame(1))
    await bridge.emit_state(VirtualRuntimeState())
    # No assertion needed — must not raise.


def test_project_counters_reports_domain_sizes() -> None:
    state = VirtualRuntimeState(
        last_sequence=5,
        frames_applied=5,
        domains={"tasks": {"t-1": True, "t-2": True}, "queues": {"q-1": True}},
    )
    out = project_counters(state)
    assert out["last_sequence"] == 5
    assert out["frames_applied"] == 5
    assert out["domain_counts"] == {"tasks": 2, "queues": 1}


def test_project_domain_returns_copy() -> None:
    state = VirtualRuntimeState(domains={"tasks": {"t-1": True}})
    proj = project_domain("tasks")
    out = proj(state)
    out["t-2"] = True  # mutate the projection — must not leak
    assert state.domains["tasks"] == {"t-1": True}


def test_project_domain_names_sorted() -> None:
    state = VirtualRuntimeState(domains={"queues": {}, "tasks": {}, "executors": {}})
    assert project_domain_names(state) == ("executors", "queues", "tasks")


def test_projection_registry_compute_all_emits_views() -> None:
    registry = ProjectionRegistry()
    registry.register(Projection(name="seq", project=lambda s: s.last_sequence))
    registry.register(Projection(name="applied", project=lambda s: s.frames_applied))
    views = registry.compute_all(VirtualRuntimeState(last_sequence=3, frames_applied=3))
    assert [(v.name, v.value) for v in views] == [("seq", 3), ("applied", 3)]


def test_default_projection_registry_has_counters_and_names() -> None:
    registry = default_projection_registry()
    names = registry.names()
    assert "counters" in names
    assert "domain_names" in names
