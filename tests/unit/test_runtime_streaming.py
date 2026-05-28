from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app
from asyncviz.dashboard.websocket.manager import ConnectionManager
from asyncviz.dashboard.websocket.protocol import Envelope
from asyncviz.dashboard.websocket.streaming import (
    BatchingPolicy,
    RuntimeStreamingEngine,
    StreamingMetrics,
    metrics_delta_payload,
    warning_delta_payload,
)
from asyncviz.runtime.clock import (
    RuntimeClock,
    reset_runtime_clock,
    set_default_runtime_clock,
)
from asyncviz.runtime.events.models import (
    TaskCreatedEvent,
)
from asyncviz.runtime.events.models.enums import TaskState, WarningSeverity
from asyncviz.runtime.metrics import (
    MetricsDelta,
    RuntimeMetricsAggregator,
)
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.runtime.timeline import (
    TimelineDeltaKind,
    TimelineSegmentEngine,
)
from asyncviz.runtime.warnings import (
    RuntimeWarningManager,
    WarningChange,
    WarningDelta,
)
from asyncviz.runtime.warnings.lifecycle import WarningLifecycle


@pytest.fixture(autouse=True)
def _fresh_clock():
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    yield clock
    reset_runtime_clock()


# ── StreamingMetrics primitives ───────────────────────────────────────────


def test_streaming_metrics_counts_per_stream() -> None:
    metrics = StreamingMetrics()
    metrics.record_metrics_delta()
    metrics.record_metrics_delta()
    metrics.record_warning_delta()
    metrics.record_timeline_delta(n=3)
    metrics.record_runtime_delta()
    metrics.record_protocol_error()
    metrics.record_subscription_dispatch()
    metrics.record_subscription_dispatch(failed=True)
    metrics.record_broadcast_failure()
    snap = metrics.snapshot()
    assert snap.metrics_deltas_sent == 2
    assert snap.warning_deltas_sent == 1
    assert snap.timeline_deltas_sent == 3
    assert snap.runtime_deltas_sent == 1
    assert snap.protocol_errors_sent == 1
    assert snap.subscription_dispatches == 2
    assert snap.subscription_failures == 1
    assert snap.broadcast_failures == 1


def test_streaming_metrics_reset_clears_every_counter() -> None:
    metrics = StreamingMetrics()
    metrics.record_metrics_delta()
    metrics.record_broadcast_failure()
    metrics.reset()
    snap = metrics.snapshot()
    assert snap.metrics_deltas_sent == 0
    assert snap.broadcast_failures == 0


def test_batching_policy_default_is_disabled() -> None:
    policy = BatchingPolicy()
    assert policy.enabled is False
    enabled = BatchingPolicy(flush_interval_ns=1_000_000, max_batch_size=8)
    assert enabled.enabled is True


# ── Envelope payload builders ─────────────────────────────────────────────


def test_metrics_delta_payload_carries_changes_and_sequence(_fresh_clock: RuntimeClock) -> None:
    created = TaskCreatedEvent(task_id="t1", coroutine_name="alpha")
    delta = MetricsDelta(
        event=created,
        sequence=42,
        last_sequence=42,
        changes={"created": 1, "active": 1},
        duration_added_seconds=None,
        coroutine_name="alpha",
        terminal_state=None,
    )
    payload = metrics_delta_payload(delta)
    assert payload["sequence"] == 42
    assert payload["last_sequence"] == 42
    assert payload["coroutine_name"] == "alpha"
    assert payload["changes"]["created"] == 1
    assert payload["terminal_state"] is None
    # JSON-serializable
    json.dumps(payload)


def test_warning_delta_payload_round_trips(_fresh_clock: RuntimeClock) -> None:
    lifecycle = WarningLifecycle(
        warning_id="w-1",
        warning_key="key-1",
        warning_type="stuck_task",
        severity=WarningSeverity.WARNING,
        detector="stuck_task_detector",
        message="task t1 stuck",
        created_sequence=10,
        created_monotonic_ns=1000,
        created_at_wall=1.0,
        last_observed_sequence=10,
        last_observed_monotonic_ns=1000,
        last_observed_wall=1.0,
        related_task_ids=["t1"],
    )
    delta = WarningDelta(
        warning=lifecycle,
        change=WarningChange.ACTIVATED,
        sequence=10,
        last_sequence=10,
    )
    payload = warning_delta_payload(delta)
    assert payload["change"] == "activated"
    assert payload["sequence"] == 10
    assert payload["warning"]["warning_id"] == "w-1"
    assert payload["warning"]["severity"] == "warning"
    json.dumps(payload)


# ── Engine wiring + lifecycle ─────────────────────────────────────────────


def _build_engine(loop: asyncio.AbstractEventLoop, _fresh_clock: RuntimeClock):
    manager = ConnectionManager()
    aggregator = RuntimeMetricsAggregator(TaskRegistry(), clock=_fresh_clock)
    warning_manager = RuntimeWarningManager(
        TaskRegistry(),
        aggregator=aggregator,
        clock=_fresh_clock,
    )
    timeline = TimelineSegmentEngine(clock=_fresh_clock)
    engine = RuntimeStreamingEngine(
        manager=manager,
        clock=_fresh_clock,
        metrics_aggregator=aggregator,
        warning_manager=warning_manager,
        timeline_engine=timeline,
        loop=loop,
    )
    return engine, manager, aggregator, warning_manager, timeline


def test_engine_start_is_idempotent(_fresh_clock: RuntimeClock) -> None:
    loop = asyncio.new_event_loop()
    try:
        engine, *_ = _build_engine(loop, _fresh_clock)
        assert engine.is_running is False
        engine.start(loop=loop)
        assert engine.is_running is True
        engine.start(loop=loop)  # idempotent
        assert engine.is_running is True
        engine.stop()
        assert engine.is_running is False
        engine.stop()  # idempotent
    finally:
        loop.close()


def test_engine_forwards_metrics_delta_to_broadcast(_fresh_clock: RuntimeClock) -> None:
    """Trigger an aggregator delta and assert the engine broadcasts a typed envelope."""

    async def scenario() -> list[Envelope]:
        loop = asyncio.get_running_loop()
        engine, manager, aggregator, *_ = _build_engine(loop, _fresh_clock)

        captured: list[Envelope] = []

        async def fake_broadcast(env: Envelope) -> int:
            captured.append(env)
            return 1

        manager.broadcast = fake_broadcast  # type: ignore[assignment]
        engine.start(loop=loop)
        try:
            aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
            # Drain the loop so the scheduled broadcast task runs.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        finally:
            engine.stop()
        return captured

    captured = asyncio.run(scenario())
    assert captured, "expected at least one metrics_delta envelope to be broadcast"
    types = {env.type for env in captured}
    assert "metrics_delta" in types


def test_engine_forwards_timeline_delta_to_broadcast(_fresh_clock: RuntimeClock) -> None:
    async def scenario() -> list[Envelope]:
        loop = asyncio.get_running_loop()
        engine, manager, _, _, timeline = _build_engine(loop, _fresh_clock)

        captured: list[Envelope] = []

        async def fake_broadcast(env: Envelope) -> int:
            captured.append(env)
            return 1

        manager.broadcast = fake_broadcast  # type: ignore[assignment]
        engine.start(loop=loop)
        try:
            timeline.apply_transition(
                task_id="t1",
                target=TaskState.CREATED,
                sequence=1,
                monotonic_ns=100,
                wall_seconds=1.0,
            )
            timeline.apply_transition(
                task_id="t1",
                target=TaskState.RUNNING,
                sequence=2,
                monotonic_ns=200,
                wall_seconds=2.0,
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        finally:
            engine.stop()
        return captured

    captured = asyncio.run(scenario())
    types = [env.type for env in captured]
    assert "timeline_delta" in types
    # Per-stream metric should track timeline broadcasts


def test_engine_records_per_stream_counters(_fresh_clock: RuntimeClock) -> None:
    async def scenario():
        loop = asyncio.get_running_loop()
        engine, manager, aggregator, _, timeline = _build_engine(loop, _fresh_clock)

        async def fake_broadcast(env: Envelope) -> int:
            return 1

        manager.broadcast = fake_broadcast  # type: ignore[assignment]
        engine.start(loop=loop)
        try:
            aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
            timeline.apply_transition(
                task_id="t1",
                target=TaskState.CREATED,
                sequence=2,
                monotonic_ns=10,
                wall_seconds=0.01,
            )
            timeline.apply_transition(
                task_id="t1",
                target=TaskState.RUNNING,
                sequence=3,
                monotonic_ns=20,
                wall_seconds=0.02,
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            return engine.metrics_snapshot()
        finally:
            engine.stop()

    snap = asyncio.run(scenario())
    assert snap.metrics_deltas_sent >= 1
    assert snap.timeline_deltas_sent >= 1
    assert snap.subscription_dispatches >= snap.metrics_deltas_sent


def test_engine_records_broadcast_failure_on_manager_exception(
    _fresh_clock: RuntimeClock,
) -> None:
    async def scenario():
        loop = asyncio.get_running_loop()
        engine, manager, aggregator, *_ = _build_engine(loop, _fresh_clock)

        async def broken_broadcast(env: Envelope) -> int:
            raise RuntimeError("broadcast boom")

        manager.broadcast = broken_broadcast  # type: ignore[assignment]
        engine.start(loop=loop)
        try:
            aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            return engine.metrics_snapshot()
        finally:
            engine.stop()

    snap = asyncio.run(scenario())
    assert snap.broadcast_failures >= 1
    assert snap.subscription_failures >= 1


def test_engine_unsubscribes_on_stop(_fresh_clock: RuntimeClock) -> None:
    async def scenario():
        loop = asyncio.get_running_loop()
        engine, manager, aggregator, _, timeline = _build_engine(loop, _fresh_clock)
        captured: list[Envelope] = []

        async def fake_broadcast(env: Envelope) -> int:
            captured.append(env)
            return 1

        manager.broadcast = fake_broadcast  # type: ignore[assignment]
        engine.start(loop=loop)
        engine.stop()  # Tear down before any deltas fire.

        aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
        timeline.apply_transition(
            task_id="t1",
            target=TaskState.CREATED,
            sequence=2,
            monotonic_ns=10,
            wall_seconds=0.01,
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return captured

    captured = asyncio.run(scenario())
    assert captured == [], "no broadcasts should fire after stop()"


# ── Timeline payload shape ────────────────────────────────────────────────


def test_engine_timeline_payload_includes_segment_kind(_fresh_clock: RuntimeClock) -> None:
    async def scenario() -> list[Envelope]:
        loop = asyncio.get_running_loop()
        engine, manager, _, _, timeline = _build_engine(loop, _fresh_clock)
        captured: list[Envelope] = []

        async def fake_broadcast(env: Envelope) -> int:
            captured.append(env)
            return 1

        manager.broadcast = fake_broadcast  # type: ignore[assignment]
        engine.start(loop=loop)
        try:
            timeline.apply_transition(
                task_id="t1",
                target=TaskState.CREATED,
                sequence=1,
                monotonic_ns=100,
                wall_seconds=0.1,
            )
            timeline.apply_transition(
                task_id="t1",
                target=TaskState.RUNNING,
                sequence=2,
                monotonic_ns=200,
                wall_seconds=0.2,
            )
            timeline.apply_transition(
                task_id="t1",
                target=TaskState.COMPLETED,
                sequence=3,
                monotonic_ns=300,
                wall_seconds=0.3,
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        finally:
            engine.stop()
        return captured

    captured = asyncio.run(scenario())
    timeline_envs = [env for env in captured if env.type == "timeline_delta"]
    assert timeline_envs, "expected timeline_delta envelopes"
    kinds = {env.payload["kind"] for env in timeline_envs}
    # Closed (RUNNING → COMPLETED closes the run segment) + opened + finalized.
    assert TimelineDeltaKind.SEGMENT_OPENED.value in kinds
    assert TimelineDeltaKind.SEGMENT_CLOSED.value in kinds
    assert TimelineDeltaKind.SPAN_FINALIZED.value in kinds


# ── Engine.emit (manual broadcast path) ───────────────────────────────────


def test_engine_emit_routes_through_broadcast(_fresh_clock: RuntimeClock) -> None:
    async def scenario():
        loop = asyncio.get_running_loop()
        engine, manager, *_ = _build_engine(loop, _fresh_clock)
        captured: list[Envelope] = []

        async def fake_broadcast(env: Envelope) -> int:
            captured.append(env)
            return 1

        manager.broadcast = fake_broadcast  # type: ignore[assignment]
        env = Envelope(type="protocol_error", payload={"code": "x", "message": "y"})
        await engine.emit(env, kind="runtime")
        return captured, engine.metrics_snapshot()

    captured, snap = asyncio.run(scenario())
    assert len(captured) == 1
    assert captured[0].type == "protocol_error"
    assert snap.runtime_deltas_sent == 1


# ── /api/runtime/streaming endpoint ───────────────────────────────────────


@pytest.fixture
def app():
    return create_app(AsyncVizConfig(frontend_mode="api-only"))


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def test_streaming_endpoint_returns_canonical_shape(client) -> None:
    response = client.get("/api/runtime/streaming")
    assert response.status_code == 200
    data = response.json()
    for key in (
        "running",
        "metrics_deltas_sent",
        "warning_deltas_sent",
        "timeline_deltas_sent",
        "runtime_deltas_sent",
        "protocol_errors_sent",
        "subscription_dispatches",
        "subscription_failures",
        "broadcast_failures",
    ):
        assert key in data
    # Engine must have started during the TestClient context lifespan.
    assert data["running"] is True


def test_streaming_engine_is_running_after_lifespan(client, app) -> None:
    # Engine is started by the dashboard lifespan; ``client`` triggers it.
    assert app.state.streaming_engine.is_running is True


def test_backend_state_exposes_streaming_engine(app) -> None:
    assert app.state.backend.streaming_engine is app.state.streaming_engine
