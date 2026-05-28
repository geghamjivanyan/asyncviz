"""Integration tests — RuntimeClock flowing through events, envelopes, bridge."""

from __future__ import annotations

import asyncio
import itertools
import json
from collections.abc import AsyncIterator

import pytest_asyncio

from asyncviz.dashboard.state.metrics_state import MetricsState
from asyncviz.dashboard.websocket.bridge import WebSocketBridge
from asyncviz.dashboard.websocket.manager import ConnectionManager
from asyncviz.dashboard.websocket.protocol import Envelope, runtime_snapshot
from asyncviz.runtime.clock import (
    RuntimeClock,
    get_runtime_clock,
    reset_runtime_clock,
    set_default_runtime_clock,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models import (
    TaskCreatedEvent,
    from_dict,
    to_dict,
)
from asyncviz.runtime.tasks import TaskRegistry

# ── Event timing fields come from the clock ───────────────────────────────


def test_event_timestamps_originate_from_runtime_clock() -> None:
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    try:
        evt = TaskCreatedEvent(task_id="t1")
        # All timing fields must match the clock's identity / domain.
        assert evt.runtime_id == clock.runtime_id
        assert evt.monotonic_ns > 0
        # monotonic_timestamp and monotonic_ns refer to the same instant ±1ms.
        # They aren't identical because they're sampled in distinct factory
        # calls, but the difference must be tiny.
        diff = abs(evt.monotonic_timestamp - evt.monotonic_ns / 1_000_000_000)
        assert diff < 0.01, f"monotonic fields disagree by {diff:.6f}s"
    finally:
        reset_runtime_clock()


def test_event_timestamps_are_non_decreasing_within_a_clock() -> None:
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    try:
        events = [TaskCreatedEvent(task_id=f"t{i}") for i in range(500)]
    finally:
        reset_runtime_clock()
    monotonic_ns = [e.monotonic_ns for e in events]
    assert all(b >= a for a, b in itertools.pairwise(monotonic_ns))


def test_event_serialization_round_trip_preserves_monotonic_ns() -> None:
    evt = TaskCreatedEvent(task_id="t1")
    rebuilt = from_dict(to_dict(evt))
    assert isinstance(rebuilt, TaskCreatedEvent)
    assert rebuilt.monotonic_ns == evt.monotonic_ns
    assert rebuilt.monotonic_timestamp == evt.monotonic_timestamp
    assert rebuilt.timestamp == evt.timestamp
    assert rebuilt.runtime_id == evt.runtime_id


# ── WebSocketBridge sequence delegation ──────────────────────────────────


@pytest_asyncio.fixture
async def wired() -> AsyncIterator[tuple[EventBus, WebSocketBridge, RuntimeClock]]:
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    bus = EventBus()
    await bus.start()
    manager = ConnectionManager()
    metrics_state = MetricsState()
    bridge = WebSocketBridge(bus, manager, metrics_state, clock=clock)
    await bridge.start()
    try:
        yield bus, bridge, clock
    finally:
        await bridge.stop()
        await bus.stop()
        reset_runtime_clock()


async def test_bridge_sequence_delegates_to_clock(wired) -> None:
    bus, bridge, clock = wired
    assert bridge.clock is clock
    assert bridge.current_sequence == 0

    # Publishing one event must allocate exactly one sequence number from the clock.
    bus.publish(TaskCreatedEvent(task_id="x"))
    await bus.join()
    await asyncio.sleep(0.01)

    assert bridge.current_sequence == 1
    assert clock.current_sequence == 1


async def test_bridge_sequence_is_strictly_monotonic_under_load(wired) -> None:
    bus, bridge, clock = wired

    for i in range(50):
        bus.publish(TaskCreatedEvent(task_id=f"t{i}"))
    await bus.join()
    # Bridge has now forwarded 50 events — each took one clock sequence.
    assert clock.current_sequence == 50
    assert bridge.current_sequence == 50


# ── Snapshot frame embeds clock state ────────────────────────────────────


def test_capture_snapshot_embeds_clock_payload() -> None:
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    try:
        bus = EventBus()
        manager = ConnectionManager()
        metrics_state = MetricsState()
        registry = TaskRegistry()
        bridge = WebSocketBridge(bus, manager, metrics_state, clock=clock)
        envelope = bridge.capture_snapshot(registry)
    finally:
        reset_runtime_clock()

    assert isinstance(envelope, Envelope)
    assert envelope.type == "runtime_snapshot"
    clock_payload = envelope.payload["clock"]
    assert clock_payload is not None
    assert clock_payload["runtime_id"] == str(clock.runtime_id)
    assert clock_payload["current_sequence"] == 0
    assert clock_payload["uptime_ns"] >= 0


def test_runtime_snapshot_helper_round_trips_clock_field() -> None:
    payload = {"runtime_id": "abc", "uptime_seconds": 1.5}
    envelope = runtime_snapshot(last_sequence=42, tasks=[], clock=payload)
    rebuilt = json.loads(envelope.model_dump_json())
    assert rebuilt["payload"]["clock"] == payload


# ── Envelope timestamp uses the runtime clock ────────────────────────────


def test_envelope_timestamp_uses_runtime_clock_now() -> None:
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    try:
        before = clock.now()
        envelope = Envelope(type="heartbeat")
        after = clock.now()
    finally:
        reset_runtime_clock()
    assert before <= envelope.timestamp <= after


# ── Cross-cutting: clock identity propagates everywhere ──────────────────


def test_clock_runtime_id_is_carried_through_event_and_snapshot() -> None:
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    try:
        evt = TaskCreatedEvent(task_id="t1")
        assert evt.runtime_id == clock.runtime_id

        bus = EventBus()
        manager = ConnectionManager()
        metrics_state = MetricsState()
        registry = TaskRegistry()
        bridge = WebSocketBridge(bus, manager, metrics_state, clock=clock)
        envelope = bridge.capture_snapshot(registry)
    finally:
        reset_runtime_clock()

    assert envelope.payload["clock"]["runtime_id"] == str(clock.runtime_id)


# ── default clock identity matches what events see ───────────────────────


def test_get_runtime_clock_returns_default_used_by_events() -> None:
    reset_runtime_clock()
    try:
        clock = get_runtime_clock()
        evt = TaskCreatedEvent(task_id="t1")
        assert evt.runtime_id == clock.runtime_id
    finally:
        reset_runtime_clock()
