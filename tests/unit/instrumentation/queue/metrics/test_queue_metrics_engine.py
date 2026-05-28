"""End-to-end behaviour tests for :class:`QueueMetricsEngine`.

Exercises the engine directly via ``apply_event`` so the assertions are
deterministic and don't depend on the asyncio.Queue patcher running.
The integration with the patched queues is covered separately in the
test below that round-trips through the event bus.
"""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.instrumentation.queue.metrics import (
    QueueMetricsConfig,
    QueueMetricsEngine,
    rebuild_metrics_from_events,
)
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.event import RuntimeEvent
from asyncviz.runtime.events.models.queue import (
    QueueCancelledEvent,
    QueueCreatedEvent,
    QueueEmptyWaitEvent,
    QueueFullWaitEvent,
    QueueGetEvent,
    QueuePutEvent,
    QueueTaskDoneEvent,
)
from asyncviz.runtime.events.models.queue_metrics import (
    QueueContentionDetectedEvent,
    QueueMetricsUpdatedEvent,
)

# ── helpers ─────────────────────────────────────────────────────────────


def _snapshot(*, size: int, maxsize: int, blocked_putters: int = 0, blocked_getters: int = 0):
    return {
        "size": size,
        "maxsize": maxsize,
        "blocked_putters": blocked_putters,
        "blocked_getters": blocked_getters,
        "unfinished_tasks": 0,
    }


def _created(qid: str = "q-1", *, maxsize: int = 4) -> QueueCreatedEvent:
    return QueueCreatedEvent(
        queue_id=qid,
        queue_kind="Queue",
        maxsize=maxsize,
        snapshot=_snapshot(size=0, maxsize=maxsize),
    )


def _put(
    qid: str = "q-1",
    *,
    size_after: int,
    maxsize: int = 4,
    blocked: bool = False,
    wait_seconds: float | None = None,
    blocked_putters: int = 0,
) -> QueuePutEvent:
    return QueuePutEvent(
        queue_id=qid,
        queue_kind="Queue",
        maxsize=maxsize,
        snapshot=_snapshot(
            size=size_after, maxsize=maxsize, blocked_putters=blocked_putters,
        ),
        nowait=False,
        blocked=blocked,
        wait_seconds=wait_seconds,
    )


def _get(
    qid: str = "q-1",
    *,
    size_after: int,
    maxsize: int = 4,
    blocked: bool = False,
    wait_seconds: float | None = None,
    blocked_getters: int = 0,
) -> QueueGetEvent:
    return QueueGetEvent(
        queue_id=qid,
        queue_kind="Queue",
        maxsize=maxsize,
        snapshot=_snapshot(
            size=size_after, maxsize=maxsize, blocked_getters=blocked_getters,
        ),
        nowait=False,
        blocked=blocked,
        wait_seconds=wait_seconds,
    )


# ── basic ingest ────────────────────────────────────────────────────────


def test_apply_event_ignores_non_queue_events(
    engine_unbound: QueueMetricsEngine,
) -> None:
    event = RuntimeEvent.of("asyncio.task.created", task_id="t-1")
    assert engine_unbound.apply_event(event) is False
    snap = engine_unbound.snapshot()
    assert snap.self_metrics.events_ignored == 1
    assert snap.self_metrics.events_observed == 0


def test_first_event_registers_a_queue(
    engine_unbound: QueueMetricsEngine,
) -> None:
    engine_unbound.apply_event(_created("q-1"))
    snap = engine_unbound.snapshot()
    assert len(snap.queues) == 1
    record = snap.queues[0]
    assert record.queue_id == "q-1"
    assert record.queue_kind == "Queue"
    assert record.maxsize == 4


def test_throughput_counters_track_puts_and_gets(
    engine_unbound: QueueMetricsEngine,
) -> None:
    engine_unbound.apply_event(_created())
    for i in range(1, 5):
        engine_unbound.apply_event(_put(size_after=i))
    for i in range(3, -1, -1):
        engine_unbound.apply_event(_get(size_after=i))
    record = engine_unbound.snapshot_queue("q-1")
    assert record is not None
    assert record.throughput.put_count == 4
    assert record.throughput.get_count == 4
    assert record.throughput.producer_consumer_delta == 0
    assert record.occupancy.peak_size == 4
    assert record.occupancy.current_size == 0


def test_blocked_put_event_records_wait(
    engine_unbound: QueueMetricsEngine,
) -> None:
    engine_unbound.apply_event(_created(maxsize=1))
    engine_unbound.apply_event(_put(size_after=1, maxsize=1))
    engine_unbound.apply_event(
        _put(size_after=1, maxsize=1, blocked=True, wait_seconds=0.5),
    )
    record = engine_unbound.snapshot_queue("q-1")
    assert record is not None
    assert record.contention.blocked_put_count == 1
    assert record.put_wait.count == 1
    assert record.put_wait.mean_seconds == pytest.approx(0.5)


def test_full_wait_and_empty_wait_counters(
    engine_unbound: QueueMetricsEngine,
) -> None:
    engine_unbound.apply_event(_created(maxsize=2))
    engine_unbound.apply_event(
        QueueFullWaitEvent(
            queue_id="q-1", queue_kind="Queue", maxsize=2,
            snapshot=_snapshot(size=2, maxsize=2),
        ),
    )
    engine_unbound.apply_event(
        QueueEmptyWaitEvent(
            queue_id="q-1", queue_kind="Queue", maxsize=2,
            snapshot=_snapshot(size=0, maxsize=2),
        ),
    )
    record = engine_unbound.snapshot_queue("q-1")
    assert record is not None
    assert record.contention.full_wait_count == 1
    assert record.contention.empty_wait_count == 1


def test_task_done_and_cancellation_counters(
    engine_unbound: QueueMetricsEngine,
) -> None:
    engine_unbound.apply_event(_created())
    engine_unbound.apply_event(
        QueueTaskDoneEvent(
            queue_id="q-1", queue_kind="Queue", maxsize=4,
            snapshot=_snapshot(size=0, maxsize=4),
        ),
    )
    engine_unbound.apply_event(
        QueueCancelledEvent(
            queue_id="q-1", queue_kind="Queue", maxsize=4,
            snapshot=_snapshot(size=0, maxsize=4),
            operation="put", wait_seconds=0.2,
        ),
    )
    record = engine_unbound.snapshot_queue("q-1")
    assert record is not None
    assert record.throughput.task_done_count == 1
    assert record.contention.cancelled_count == 1
    assert record.put_wait.count == 1  # cancelled put attributed to put_wait


# ── pressure / contention / saturation transitions ──────────────────────


def test_contention_edge_triggers_event(engine_unbound: QueueMetricsEngine) -> None:
    seen: list[QueueContentionDetectedEvent] = []
    engine_unbound.subscribe(
        lambda delta: seen.append(delta) if delta.kind == "contention-detected" else None,
    )
    engine_unbound.apply_event(_created(maxsize=2))
    # 0 → 1 blocked producer fires the leading-edge event.
    engine_unbound.apply_event(
        _put(size_after=2, maxsize=2, blocked_putters=1),
    )
    assert len(seen) == 1
    # Going to 2 blocked producers does NOT re-fire the edge (already above).
    engine_unbound.apply_event(
        _put(size_after=2, maxsize=2, blocked_putters=2),
    )
    assert len(seen) == 1


def test_saturation_event_fires_once_per_crossing(
    engine_unbound: QueueMetricsEngine,
) -> None:
    seen: list = []
    engine_unbound.subscribe(
        lambda delta: seen.append(delta) if delta.kind == "saturation-detected" else None,
    )
    engine_unbound.apply_event(_created(maxsize=10))
    # 9/10 = 0.9, saturation_threshold default = 0.9
    engine_unbound.apply_event(_put(size_after=9, maxsize=10))
    assert len(seen) == 1
    # Stay saturated — no re-fire.
    engine_unbound.apply_event(_put(size_after=10, maxsize=10))
    assert len(seen) == 1
    # Drain below recovery threshold (0.75) so the sticky bit clears.
    engine_unbound.apply_event(_get(size_after=4, maxsize=10))
    # Saturate again — fires once more.
    engine_unbound.apply_event(_put(size_after=9, maxsize=10))
    assert len(seen) == 2


def test_pressure_change_event_fires_on_level_transition(
    engine_unbound: QueueMetricsEngine,
) -> None:
    seen: list = []
    engine_unbound.subscribe(
        lambda delta: seen.append(delta) if delta.kind == "pressure-changed" else None,
    )
    engine_unbound.apply_event(_created(maxsize=10))
    # Empty queue — calm. The first emission won't fire a pressure-change
    # because the engine's tracked "last emitted level" defaults to calm
    # and the snapshot is also calm.
    engine_unbound.apply_event(_put(size_after=1, maxsize=10))
    assert seen == []
    # Drive to high pressure — many blocked producers + near-full.
    engine_unbound.apply_event(
        _put(size_after=10, maxsize=10, blocked_putters=10),
    )
    assert len(seen) >= 1
    assert seen[-1].new_level in {"warning", "critical"}


# ── debounce ────────────────────────────────────────────────────────────


def test_updated_event_debounce_respects_min_event_delta() -> None:
    engine = QueueMetricsEngine(
        bus=None,
        config=QueueMetricsConfig(
            updated_min_interval_seconds=999.0,  # time-based gate never trips
            updated_min_event_delta=5,
            saturation_threshold=2.0,  # never trip
            contention_blocked_threshold=999,
        ),
    )
    updates: list = []
    engine.subscribe(
        lambda d: updates.append(d) if d.kind == "updated" else None,
    )
    engine.apply_event(_created(maxsize=10))
    # The first event always emits (state.last_emit_monotonic == 0.0).
    assert len(updates) == 1
    # Next 4 events should NOT emit (delta < 5 since last emission).
    for i in range(2, 6):
        engine.apply_event(_put(size_after=i, maxsize=10))
    assert len(updates) == 1
    # 5th event since last emission → fires.
    engine.apply_event(_put(size_after=6, maxsize=10))
    assert len(updates) == 2


# ── rebuild ──────────────────────────────────────────────────────────────


def test_rebuild_is_deterministic() -> None:
    events: list[RuntimeEvent] = [
        _created("q-1", maxsize=4),
        _put("q-1", size_after=1),
        _put("q-1", size_after=2),
        _get("q-1", size_after=1),
        _put("q-1", size_after=2),
    ]
    _eng1, snap1, applied1 = rebuild_metrics_from_events(events)
    _eng2, snap2, applied2 = rebuild_metrics_from_events(events)
    assert applied1 == applied2 == 5
    # Records compare structurally — dataclasses with frozen=True / slots=True
    # produce equal instances when their fields match.
    assert snap1.queues[0].to_dict() == snap2.queues[0].to_dict()


def test_rebuild_silently_does_not_emit() -> None:
    fired: list = []
    eng = QueueMetricsEngine(bus=None, emit_during_apply=False)
    eng.subscribe(lambda d: fired.append(d))
    events = [
        _created("q-1", maxsize=2),
        _put("q-1", size_after=1, maxsize=2),
        _put("q-1", size_after=2, maxsize=2),
    ]
    eng.rebuild_from_events(events)
    assert fired == []
    # State still updated.
    record = eng.snapshot_queue("q-1")
    assert record is not None
    assert record.throughput.put_count == 2


# ── backpressure / safety ────────────────────────────────────────────────


def test_max_tracked_queues_evicts_new_queues() -> None:
    engine = QueueMetricsEngine(bus=None, config=QueueMetricsConfig(max_tracked_queues=2))
    engine.apply_event(_created("q-1"))
    engine.apply_event(_created("q-2"))
    engine.apply_event(_created("q-3"))  # evicted
    snap = engine.snapshot()
    assert {q.queue_id for q in snap.queues} == {"q-1", "q-2"}
    assert snap.self_metrics.queues_evicted == 1


# ── bus integration ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_engine_subscribes_to_bus_queue_events(
    bus: EventBus, fast_emit_config: QueueMetricsConfig,
) -> None:
    engine = QueueMetricsEngine(bus=bus, config=fast_emit_config)
    engine.start()
    try:
        events: list = []
        bus.subscribe(
            lambda e: events.append(e),
            event_types={"asyncio.queue.metrics.updated"},
        )
        bus.publish(_created("q-1", maxsize=4))
        bus.publish(_put("q-1", size_after=1))
        await bus.join()
        # At least one updated event should have made it through the bus.
        assert any(isinstance(e, QueueMetricsUpdatedEvent) for e in events)
    finally:
        engine.stop()


@pytest.mark.asyncio
async def test_engine_stop_unsubscribes(bus: EventBus) -> None:
    engine = QueueMetricsEngine(bus=bus)
    engine.start()
    engine.stop()
    # After stop, raw events should not be observed by the engine.
    bus.publish(_created("q-1"))
    await bus.join()
    snap = engine.snapshot()
    assert snap.self_metrics.events_observed == 0


# ── synthetic producer/consumer workload ─────────────────────────────────


def test_high_throughput_workload_balances() -> None:
    engine = QueueMetricsEngine(bus=None)
    engine.apply_event(_created("q-1", maxsize=100))
    for i in range(1, 51):
        engine.apply_event(_put("q-1", size_after=i, maxsize=100))
    for i in range(49, -1, -1):
        engine.apply_event(_get("q-1", size_after=i, maxsize=100))
    record = engine.snapshot_queue("q-1")
    assert record is not None
    assert record.throughput.put_count == 50
    assert record.throughput.get_count == 50
    assert record.throughput.producer_consumer_delta == 0
    assert record.occupancy.peak_size == 50
    assert record.occupancy.current_size == 0


# ── snapshot round-trip ──────────────────────────────────────────────────


def test_snapshot_is_json_safe(engine_unbound: QueueMetricsEngine) -> None:
    import json

    engine_unbound.apply_event(_created("q-1", maxsize=4))
    engine_unbound.apply_event(_put("q-1", size_after=1))
    body = engine_unbound.snapshot().to_dict()
    payload = json.dumps(body)
    restored = json.loads(payload)
    assert restored["queues"][0]["queue_id"] == "q-1"


# silence linter
del asyncio
