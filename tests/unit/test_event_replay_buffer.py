from __future__ import annotations

import json

import pytest

from asyncviz.runtime.clock import RuntimeClock, reset_runtime_clock, set_default_runtime_clock
from asyncviz.runtime.events.models import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
)
from asyncviz.runtime.replay import (
    CheckpointStore,
    EventReplayBuffer,
    FrameRetention,
    ReplayBatchModel,
    ReplayCheckpoint,
    ReplayFrame,
    ReplaySnapshot,
    frame_from_event,
)
from asyncviz.runtime.state import RuntimeStateStore
from asyncviz.runtime.tasks import TaskRegistry


@pytest.fixture(autouse=True)
def _fresh_clock():
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    yield clock
    reset_runtime_clock()


@pytest.fixture
def buffer(_fresh_clock: RuntimeClock) -> EventReplayBuffer:
    return EventReplayBuffer(clock=_fresh_clock, capacity=10)


# ── ReplayFrame / frame_from_event ────────────────────────────────────────


def test_frame_from_event_captures_task_metadata() -> None:
    event = TaskCreatedEvent(task_id="t1", task_name="root", coroutine_name="my_coro")
    frame = frame_from_event(event, sequence=42)
    assert frame.sequence == 42
    assert frame.event_type == "asyncio.task.created"
    assert frame.task_id == "t1"
    assert frame.payload["task_id"] == "t1"
    assert frame.payload["task_name"] == "root"


def test_frame_as_dict_is_json_safe() -> None:
    frame = frame_from_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    payload = frame.as_dict()
    json.dumps(payload)  # no exception
    assert payload["sequence"] == 1


# ── FrameRetention ───────────────────────────────────────────────────────


def test_retention_appends_in_sequence_order() -> None:
    retention = FrameRetention(capacity=5)
    for i in range(5):
        retention.append(_frame_at(sequence=i + 1))
    assert [f.sequence for f in retention.snapshot()] == [1, 2, 3, 4, 5]
    assert retention.oldest_sequence() == 1
    assert retention.newest_sequence() == 5


def test_retention_evicts_oldest_when_full() -> None:
    retention = FrameRetention(capacity=3)
    for i in range(6):
        evicted = retention.append(_frame_at(sequence=i + 1))
        if i < 3:
            assert evicted is None
        else:
            assert evicted is not None
            assert evicted.sequence == i - 2
    snap = retention.snapshot()
    assert [f.sequence for f in snap] == [4, 5, 6]
    assert retention.oldest_evicted_sequence == 3


def test_retention_get_by_sequence_is_o1() -> None:
    retention = FrameRetention(capacity=10)
    for i in range(5):
        retention.append(_frame_at(sequence=i + 1))
    frame = retention.get(3)
    assert frame is not None and frame.sequence == 3
    assert retention.get(999) is None


def test_retention_since_returns_gap() -> None:
    retention = FrameRetention(capacity=10)
    for i in range(1, 11):
        retention.append(_frame_at(sequence=i))
    frames = retention.since(5)
    assert [f.sequence for f in frames] == [6, 7, 8, 9, 10]


def test_retention_range_is_inclusive() -> None:
    retention = FrameRetention(capacity=10)
    for i in range(1, 11):
        retention.append(_frame_at(sequence=i))
    frames = retention.range(3, 7)
    assert [f.sequence for f in frames] == [3, 4, 5, 6, 7]


def test_retention_covers_handles_edges() -> None:
    retention = FrameRetention(capacity=5)
    assert retention.covers(0)  # always
    for i in range(1, 6):
        retention.append(_frame_at(sequence=i))
    assert retention.covers(1)
    assert retention.covers(5)
    assert not retention.covers(99)


# ── CheckpointStore ──────────────────────────────────────────────────────


def test_checkpoint_store_adds_and_returns_latest() -> None:
    store = CheckpointStore(capacity=3)
    for i in range(3):
        store.add(_checkpoint_at(sequence=i + 1))
    latest = store.latest()
    assert latest is not None and latest.sequence == 3


def test_checkpoint_store_evicts_oldest() -> None:
    store = CheckpointStore(capacity=2)
    for i in range(4):
        store.add(_checkpoint_at(sequence=i + 1))
    snap = store.snapshot()
    assert [c.sequence for c in snap] == [3, 4]


def test_checkpoint_store_find_for_replay_picks_largest_lte() -> None:
    store = CheckpointStore(capacity=5)
    for seq in (1, 10, 25, 50):
        store.add(_checkpoint_at(sequence=seq))
    # Asking "what's the freshest checkpoint with sequence <= 30?" → 25.
    cp = store.find_for_replay(since_sequence=30)
    assert cp is not None and cp.sequence == 25
    # Below the oldest → None.
    assert store.find_for_replay(since_sequence=0) is None


# ── EventReplayBuffer ────────────────────────────────────────────────────


def test_buffer_append_event_records_frame(buffer: EventReplayBuffer) -> None:
    event = TaskCreatedEvent(task_id="t1")
    frame = buffer.append_event(event, sequence=1)
    assert frame.sequence == 1
    assert buffer.last_sequence == 1
    assert len(buffer) == 1
    assert buffer.get_frame(1) is not None


def test_buffer_evicts_oldest_when_full(buffer: EventReplayBuffer) -> None:
    for i in range(12):  # capacity is 10
        buffer.append_event(TaskCreatedEvent(task_id=f"t{i}"), sequence=i + 1)
    assert len(buffer) == 10
    assert buffer.oldest_retained_sequence() == 3
    assert buffer.newest_retained_sequence() == 12


def test_buffer_replay_since_hit(buffer: EventReplayBuffer) -> None:
    for i in range(1, 6):
        buffer.append_event(TaskCreatedEvent(task_id=f"t{i}"), sequence=i)
    batch = buffer.replay_since(2)
    assert batch.window.hit is True
    assert [f.sequence for f in batch.window.frames] == [3, 4, 5]
    assert batch.checkpoint is None


def test_buffer_replay_since_miss_when_window_rolled() -> None:
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    buffer = EventReplayBuffer(clock=clock, capacity=3)
    for i in range(1, 11):
        buffer.append_event(TaskCreatedEvent(task_id=f"t{i}"), sequence=i)
    # Retention holds 8, 9, 10; asking for since=2 is a miss.
    batch = buffer.replay_since(2)
    assert batch.window.hit is False
    assert batch.window.frames == []
    assert batch.window.oldest_available_sequence == 8


def test_buffer_replay_range_inclusive(buffer: EventReplayBuffer) -> None:
    for i in range(1, 11):
        buffer.append_event(TaskCreatedEvent(task_id=f"t{i}"), sequence=i)
    batch = buffer.replay_range(3, 7)
    assert batch.window.hit is True
    assert [f.sequence for f in batch.window.frames] == [3, 4, 5, 6, 7]


def test_buffer_replay_since_zero_returns_full_retention(buffer: EventReplayBuffer) -> None:
    for i in range(1, 4):
        buffer.append_event(TaskCreatedEvent(task_id=f"t{i}"), sequence=i)
    batch = buffer.replay_since(0)
    assert batch.window.hit is True
    assert len(batch.window.frames) == 3


def test_buffer_replay_metrics_reflect_hits_and_misses() -> None:
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    buffer = EventReplayBuffer(clock=clock, capacity=3)
    for i in range(1, 11):
        buffer.append_event(TaskCreatedEvent(task_id=f"t{i}"), sequence=i)
    buffer.replay_since(0)  # hit
    buffer.replay_since(2)  # miss (rolled past)
    snap = buffer.snapshot()
    assert snap.self_metrics.replay_hits == 1
    assert snap.self_metrics.replay_misses == 1


# ── Checkpoints via buffer.create_checkpoint ─────────────────────────────


def test_buffer_create_checkpoint_pins_sequence(_fresh_clock: RuntimeClock) -> None:
    store = RuntimeStateStore(TaskRegistry())
    buffer = EventReplayBuffer(clock=_fresh_clock)
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    buffer.append_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    checkpoint = buffer.create_checkpoint(state_store=store)
    assert checkpoint.sequence == 1
    assert checkpoint.state is not None
    assert checkpoint.state["last_sequence"] == 1


def test_buffer_replay_since_returns_checkpoint_when_requested(
    _fresh_clock: RuntimeClock,
) -> None:
    store = RuntimeStateStore(TaskRegistry())
    buffer = EventReplayBuffer(clock=_fresh_clock)
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    buffer.append_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    buffer.create_checkpoint(state_store=store)
    store.apply(TaskCreatedEvent(task_id="t2"), sequence=2)
    buffer.append_event(TaskCreatedEvent(task_id="t2"), sequence=2)

    batch = buffer.replay_since(2, with_checkpoint=True)
    # Window covers nothing after sequence=2; checkpoint at sequence=1
    # is the fast-forward point.
    assert batch.checkpoint is not None
    assert batch.checkpoint.sequence == 1


# ── State-store binding ──────────────────────────────────────────────────


def test_buffer_bind_records_state_changes(_fresh_clock: RuntimeClock) -> None:
    store = RuntimeStateStore(TaskRegistry())
    buffer = EventReplayBuffer(clock=_fresh_clock)
    buffer.bind(store)
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.1), sequence=2)
    assert buffer.last_sequence == 2
    assert len(buffer) == 2


def test_buffer_skips_unsequenced_state_changes(_fresh_clock: RuntimeClock) -> None:
    store = RuntimeStateStore(TaskRegistry())
    buffer = EventReplayBuffer(clock=_fresh_clock)
    buffer.bind(store)
    # No sequence given → buffer should skip the event.
    store.apply(TaskCreatedEvent(task_id="t1"))
    assert len(buffer) == 0


# ── Reconstruction ───────────────────────────────────────────────────────


def test_replay_into_state_rebuilds_from_buffer(_fresh_clock: RuntimeClock) -> None:
    source_store = RuntimeStateStore(TaskRegistry())
    buffer = EventReplayBuffer(clock=_fresh_clock)
    buffer.bind(source_store)
    source_store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    source_store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.1), sequence=2)

    # Build a fresh target store and replay every retained frame into it.
    target_store = RuntimeStateStore(TaskRegistry())
    applied = buffer.replay_into_state(target_store)
    assert applied == 2
    snap = target_store.snapshot(include_projections=False)
    assert snap.metrics.total_tasks == 1
    assert snap.metrics.completed_tasks == 1


def test_replay_into_metrics_aggregates_from_buffer(_fresh_clock: RuntimeClock) -> None:
    from asyncviz.runtime.metrics import RuntimeMetricsAggregator

    registry = TaskRegistry()
    store = RuntimeStateStore(registry)
    buffer = EventReplayBuffer(clock=_fresh_clock)
    buffer.bind(store)
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.2), sequence=2)

    aggregator = RuntimeMetricsAggregator(TaskRegistry(), clock=_fresh_clock)
    applied = buffer.replay_into_metrics(aggregator)
    assert applied == 2
    counts = aggregator.counts_snapshot()
    assert counts["total"] == 1
    assert counts["completed"] == 1


# ── Snapshot ──────────────────────────────────────────────────────────────


def test_snapshot_round_trips_through_pydantic(buffer: EventReplayBuffer) -> None:
    for i in range(1, 4):
        buffer.append_event(TaskCreatedEvent(task_id=f"t{i}"), sequence=i)
    snap = buffer.snapshot()
    assert isinstance(snap, ReplaySnapshot)
    raw = snap.model_dump_json()
    rebuilt = ReplaySnapshot.model_validate(json.loads(raw))
    assert rebuilt.frame_count == 3
    assert rebuilt.oldest_sequence == 1
    assert rebuilt.newest_sequence == 3


def test_buffer_clear_resets_everything(buffer: EventReplayBuffer) -> None:
    for i in range(1, 6):
        buffer.append_event(TaskCreatedEvent(task_id=f"t{i}"), sequence=i)
    buffer.clear()
    assert len(buffer) == 0
    assert buffer.last_sequence == 0


def test_buffer_rebuild_replays_pairs(buffer: EventReplayBuffer) -> None:
    pairs = [(TaskCreatedEvent(task_id=f"t{i}"), i + 1) for i in range(5)]
    applied = buffer.rebuild(pairs)
    assert applied == 5
    assert len(buffer) == 5


# ── Subscriptions ────────────────────────────────────────────────────────


def test_buffer_notifies_subscribers(buffer: EventReplayBuffer) -> None:
    received: list[ReplayFrame] = []
    buffer.subscribe(received.append)
    buffer.append_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    assert len(received) == 1
    assert received[0].sequence == 1


def test_buffer_subscription_failures_isolated(buffer: EventReplayBuffer) -> None:
    received: list[ReplayFrame] = []

    def bad(_: ReplayFrame) -> None:
        raise RuntimeError("boom")

    buffer.subscribe(bad)
    buffer.subscribe(received.append)
    buffer.append_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    assert len(received) == 1
    snap = buffer.snapshot()
    assert snap.self_metrics.subscription_failures == 1


# ── Replay-batch with checkpoint flow ────────────────────────────────────


def test_replay_since_provides_checkpoint_fallback_on_miss(
    _fresh_clock: RuntimeClock,
) -> None:
    store = RuntimeStateStore(TaskRegistry())
    buffer = EventReplayBuffer(clock=_fresh_clock, capacity=3)
    buffer.bind(store)
    for i in range(1, 11):
        store.apply(TaskCreatedEvent(task_id=f"t{i}"), sequence=i)
    buffer.create_checkpoint(state_store=store, label="end-of-burst")

    # Retention only holds the last 3 (seq 8, 9, 10). Asking since=2 is a miss
    # but the checkpoint (which pins sequence=10) is available as a fast-forward.
    batch = buffer.replay_since(2, with_checkpoint=True)
    assert batch.window.hit is False
    assert batch.checkpoint is not None
    assert batch.checkpoint.sequence == 10
    assert batch.checkpoint.label == "end-of-burst"


# ── helpers ──────────────────────────────────────────────────────────────


def _frame_at(*, sequence: int) -> ReplayFrame:
    return ReplayFrame(
        sequence=sequence,
        event_id=f"e{sequence}",
        event_type="asyncio.task.created",
        monotonic_ns=sequence * 1000,
        wall_seconds=float(sequence),
        runtime_id="runtime",
        task_id=f"t{sequence}",
        parent_task_id=None,
        payload={"event_type": "asyncio.task.created", "task_id": f"t{sequence}"},
    )


def _checkpoint_at(*, sequence: int) -> ReplayCheckpoint:
    return ReplayCheckpoint(
        checkpoint_id=f"cp{sequence}",
        sequence=sequence,
        monotonic_ns=sequence * 1000,
        wall_seconds=float(sequence),
        runtime_id="runtime",
        state=None,
        timeline=None,
        metrics=None,
        warnings=None,
        label=None,
    )


# Provided for tests that intentionally ignore the unused-import detector.
_ = (TaskCancelledEvent, ReplayBatchModel)
