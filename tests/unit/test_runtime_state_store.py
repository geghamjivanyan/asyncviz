from __future__ import annotations

import json
import threading
import uuid

import pytest

from asyncviz.runtime.clock import RuntimeClock, reset_runtime_clock, set_default_runtime_clock
from asyncviz.runtime.events.models import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
    TaskWaitingEvent,
    create_runtime_metric,
)
from asyncviz.runtime.queue import QueuedEvent
from asyncviz.runtime.state import (
    ReconciliationDecision,
    ReconciliationPolicy,
    RuntimeStateSnapshot,
    RuntimeStateStore,
    StateChange,
    bind_store_to_event_bus,
    build_index_view,
    cancellations_by_origin_projection,
    coroutine_groups_projection,
    default_projections,
    lineage_tree_projection,
    normalize_event,
)
from asyncviz.runtime.tasks import TaskRegistry


@pytest.fixture(autouse=True)
def _fresh_clock():
    """Each test gets its own RuntimeClock so sequences don't bleed across cases."""
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    yield clock
    reset_runtime_clock()


@pytest.fixture
def store(_fresh_clock: RuntimeClock) -> RuntimeStateStore:
    return RuntimeStateStore(TaskRegistry(), clock=_fresh_clock)


# ── ReconciliationPolicy ──────────────────────────────────────────────────


def test_policy_evaluates_fresh_event_as_apply() -> None:
    policy = ReconciliationPolicy()
    assert policy.evaluate(sequence=1, event_id="a") is ReconciliationDecision.APPLY


def test_policy_stale_after_record() -> None:
    policy = ReconciliationPolicy()
    policy.record_applied(sequence=5, event_id="a")
    assert policy.evaluate(sequence=3, event_id="b") is ReconciliationDecision.STALE
    assert policy.evaluate(sequence=6, event_id="c") is ReconciliationDecision.APPLY


def test_policy_detects_duplicate_event_id() -> None:
    policy = ReconciliationPolicy()
    policy.record_applied(sequence=1, event_id="a")
    assert policy.evaluate(sequence=2, event_id="a") is ReconciliationDecision.DUPLICATE


def test_policy_event_id_window_evicts_oldest() -> None:
    policy = ReconciliationPolicy(event_id_window=3)
    for i, sid in enumerate(["a", "b", "c", "d"], start=1):
        policy.record_applied(sequence=i, event_id=sid)
    # 'a' should have been evicted; re-seeing it is APPLY (and stale by seq).
    assert policy.evaluate(sequence=10, event_id="a") is ReconciliationDecision.APPLY


def test_policy_reset_for_rebuild_clears_state() -> None:
    policy = ReconciliationPolicy()
    policy.record_applied(sequence=42, event_id="a")
    policy.reset_for_rebuild()
    assert policy.last_sequence == 0
    assert policy.evaluate(sequence=1, event_id="a") is ReconciliationDecision.APPLY


# ── Normalization ────────────────────────────────────────────────────────


def test_normalize_task_event_is_task_event() -> None:
    evt = TaskCreatedEvent(task_id="t1")
    norm = normalize_event(evt, sequence=7)
    assert norm.is_task_event is True
    assert norm.sequence == 7
    assert norm.event_type == "asyncio.task.created"


def test_normalize_non_task_event_is_not_task_event() -> None:
    evt = create_runtime_metric(name="x", value=1.0)
    norm = normalize_event(evt, sequence=1)
    assert norm.is_task_event is False


# ── Reducer dispatch ─────────────────────────────────────────────────────


def test_apply_task_created_registers_in_registry(store: RuntimeStateStore) -> None:
    evt = TaskCreatedEvent(task_id="t1", task_name="root", coroutine_name="my_coro")
    decision = store.apply(evt, sequence=1)
    assert decision is ReconciliationDecision.APPLY
    snap = store.registry.snapshot_task("t1")
    assert snap is not None
    assert snap.task_name == "root"


def test_apply_state_transitions_in_order(store: RuntimeStateStore) -> None:
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    store.apply(TaskStartedEvent(task_id="t1"), sequence=2)
    store.apply(TaskWaitingEvent(task_id="t1"), sequence=3)
    store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.1), sequence=4)
    snap = store.registry.snapshot_task("t1")
    assert snap is not None
    assert snap.state.value == "completed"


def test_apply_terminal_then_resumed_does_not_regress(store: RuntimeStateStore) -> None:
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.5), sequence=2)
    # Late "waiting" event for the same task → registry rejects the transition,
    # store counts rejected internally via registry metrics; nothing crashes.
    store.apply(TaskWaitingEvent(task_id="t1"), sequence=3)
    snap = store.registry.snapshot_task("t1")
    assert snap is not None
    assert snap.state.value == "completed"


# ── Reconciliation behavior ──────────────────────────────────────────────


def test_stale_sequence_is_suppressed(store: RuntimeStateStore) -> None:
    evt1 = TaskCreatedEvent(task_id="t1")
    evt2 = TaskCreatedEvent(task_id="t2")
    store.apply(evt1, sequence=10)
    decision = store.apply(evt2, sequence=5)
    assert decision is ReconciliationDecision.STALE
    metrics = store.metrics_snapshot()
    assert metrics.events_stale == 1
    assert metrics.events_applied == 1


def test_duplicate_event_id_is_suppressed(store: RuntimeStateStore) -> None:
    evt = TaskCreatedEvent(task_id="t1")
    first = store.apply(evt, sequence=1)
    second = store.apply(evt, sequence=2)
    assert first is ReconciliationDecision.APPLY
    assert second is ReconciliationDecision.DUPLICATE
    metrics = store.metrics_snapshot()
    assert metrics.events_duplicate == 1


def test_non_task_event_counts_as_unknown_type(store: RuntimeStateStore) -> None:
    evt = create_runtime_metric(name="x", value=1.0)
    decision = store.apply(evt, sequence=1)
    # Decision is APPLY (it advances last_sequence) but it doesn't mutate state.
    assert decision is ReconciliationDecision.APPLY
    metrics = store.metrics_snapshot()
    assert metrics.events_unknown_type == 1
    assert metrics.events_applied == 0


# ── Snapshot determinism ─────────────────────────────────────────────────


def test_snapshot_is_pydantic_round_trip_safe(store: RuntimeStateStore) -> None:
    store.apply(TaskCreatedEvent(task_id="t1", task_name="root"), sequence=1)
    store.apply(
        TaskCreatedEvent(task_id="t2", task_name="child", parent_task_id="t1"),
        sequence=2,
    )
    store.apply(TaskCompletedEvent(task_id="t2", duration_seconds=0.05), sequence=3)

    snap = store.snapshot()
    assert isinstance(snap, RuntimeStateSnapshot)
    payload = snap.model_dump(mode="json")
    raw = json.dumps(payload)
    rebuilt = RuntimeStateSnapshot.model_validate(json.loads(raw))
    assert rebuilt.last_sequence == 3
    assert rebuilt.metrics.total_tasks == 2
    assert rebuilt.metrics.terminal_tasks == 1


def test_snapshot_includes_projections_by_default(store: RuntimeStateStore) -> None:
    store.apply(TaskCreatedEvent(task_id="t1", coroutine_name="alpha"), sequence=1)
    store.apply(TaskCreatedEvent(task_id="t2", coroutine_name="beta"), sequence=2)
    snap = store.snapshot()
    assert "lineage_tree" in snap.projections
    assert "coroutine_groups" in snap.projections
    assert set(default_projections().keys()) <= set(snap.projections.keys())


def test_snapshot_can_omit_projections(store: RuntimeStateStore) -> None:
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    snap = store.snapshot(include_projections=False)
    assert snap.projections == {}


def test_snapshot_tasks_sorted_deterministically(store: RuntimeStateStore) -> None:
    # Apply events out-of-order by created_at via uuid jittering — registry
    # sorts on (created_at, task_id) so snapshot order is stable.
    for tid in ["t-z", "t-a", "t-m"]:
        store.apply(TaskCreatedEvent(task_id=tid), sequence=hash(tid) & 0xFFFFFF)

    snap1 = store.snapshot()
    snap2 = store.snapshot()
    assert [t.task_id for t in snap1.tasks] == [t.task_id for t in snap2.tasks]


# ── Projections ──────────────────────────────────────────────────────────


def test_lineage_tree_projection_groups_by_root(store: RuntimeStateStore) -> None:
    store.apply(TaskCreatedEvent(task_id="root"), sequence=1)
    store.apply(TaskCreatedEvent(task_id="a", parent_task_id="root"), sequence=2)
    store.apply(TaskCreatedEvent(task_id="b", parent_task_id="root"), sequence=3)
    store.apply(TaskCreatedEvent(task_id="c", parent_task_id="a"), sequence=4)
    tasks = list(store.registry.snapshot_all_tasks())
    projection = lineage_tree_projection(tasks, lineage=store.lineage)
    trees = projection["trees"]
    assert "root" in trees
    tree = trees["root"]
    assert tree["size"] == 4
    assert tree["max_depth"] == 2
    assert tree["task_ids"][0] == "root"


def test_coroutine_groups_projection_rolls_up_durations(store: RuntimeStateStore) -> None:
    store.apply(TaskCreatedEvent(task_id="t1", coroutine_name="alpha"), sequence=1)
    store.apply(TaskCreatedEvent(task_id="t2", coroutine_name="alpha"), sequence=2)
    store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.10), sequence=3)
    store.apply(TaskCompletedEvent(task_id="t2", duration_seconds=0.30), sequence=4)
    tasks = list(store.registry.snapshot_all_tasks())
    groups = coroutine_groups_projection(tasks)
    assert groups["alpha"]["count"] == 2
    assert groups["alpha"]["completed"] == 2
    assert groups["alpha"]["average_completed_duration_seconds"] == pytest.approx(0.20)


def test_cancellations_by_origin_projection(store: RuntimeStateStore) -> None:
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    store.apply(TaskCreatedEvent(task_id="t2"), sequence=2)
    store.apply(
        TaskCancelledEvent(task_id="t1", duration_seconds=0.1, cancellation_origin="shutdown"),
        sequence=3,
    )
    store.apply(
        TaskCancelledEvent(task_id="t2", duration_seconds=0.1, cancellation_origin="explicit"),
        sequence=4,
    )
    by_origin = cancellations_by_origin_projection(store.registry)
    assert by_origin["shutdown"] == ["t1"]
    assert by_origin["explicit"] == ["t2"]


# ── Subscriptions ────────────────────────────────────────────────────────


def test_subscription_receives_state_changes(store: RuntimeStateStore) -> None:
    received: list[StateChange] = []
    store.subscribe(received.append)
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.1), sequence=2)
    assert len(received) == 2
    assert received[0].event_type == "asyncio.task.created"
    assert received[0].sequence == 1
    assert received[1].event_type == "asyncio.task.completed"


def test_subscription_failure_isolated(store: RuntimeStateStore) -> None:
    received: list[StateChange] = []

    def bad(_change: StateChange) -> None:
        raise RuntimeError("boom")

    store.subscribe(bad)
    store.subscribe(received.append)
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    assert len(received) == 1
    metrics = store.metrics_snapshot()
    assert metrics.subscription_failures == 1


def test_unsubscribe_stops_notifications(store: RuntimeStateStore) -> None:
    received: list[StateChange] = []
    sub = store.subscribe(received.append)
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    assert store.unsubscribe(sub) is True
    store.apply(TaskCreatedEvent(task_id="t2"), sequence=2)
    assert len(received) == 1


# ── Rebuild from replay ──────────────────────────────────────────────────


def test_rebuild_replays_event_stream(store: RuntimeStateStore) -> None:
    # Original timeline.
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    store.apply(TaskCreatedEvent(task_id="t2", parent_task_id="t1"), sequence=2)
    store.apply(TaskCompletedEvent(task_id="t2", duration_seconds=0.1), sequence=3)
    original_snap = store.snapshot(include_projections=False)

    # Capture the event stream as QueuedEvents (events with their sequences).
    events = [
        QueuedEvent(sequence=1, event=TaskCreatedEvent(task_id="t1", event_id=uuid.uuid4())),
        QueuedEvent(
            sequence=2,
            event=TaskCreatedEvent(task_id="t2", parent_task_id="t1", event_id=uuid.uuid4()),
        ),
        QueuedEvent(
            sequence=3,
            event=TaskCompletedEvent(task_id="t2", duration_seconds=0.1, event_id=uuid.uuid4()),
        ),
    ]
    applied = store.rebuild(events)
    assert applied == 3

    rebuilt_snap = store.snapshot(include_projections=False)
    assert rebuilt_snap.metrics.total_tasks == original_snap.metrics.total_tasks
    assert rebuilt_snap.metrics.completed_tasks == original_snap.metrics.completed_tasks
    assert rebuilt_snap.last_sequence == 3


def test_rebuild_resets_metrics_lifetime_counters(store: RuntimeStateStore) -> None:
    evt = TaskCreatedEvent(task_id="t1")  # same event_id used twice
    store.apply(evt, sequence=1)
    store.apply(evt, sequence=2)  # duplicate event_id
    metrics_pre = store.metrics_snapshot()
    assert metrics_pre.events_duplicate == 1

    store.rebuild([])
    metrics_post = store.metrics_snapshot()
    # Per-event counters reset; lifetime rebuild counter advances.
    assert metrics_post.events_duplicate == 0
    assert metrics_post.events_applied == 0
    assert metrics_post.rebuilds_completed == 1


# ── EventBus integration ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bind_store_to_event_bus_routes_publishes() -> None:
    from asyncviz.runtime.events import EventBus

    bus = EventBus()
    await bus.start()
    try:
        registry = TaskRegistry()
        store = RuntimeStateStore(registry)
        sub = bind_store_to_event_bus(store, bus)
        bus.publish(TaskCreatedEvent(task_id="t1"))
        await bus.join()
        assert registry.snapshot_task("t1") is not None
        bus.unsubscribe(sub)
    finally:
        await bus.stop()


# ── Indexes ──────────────────────────────────────────────────────────────


def test_build_index_view_partitions_by_state(store: RuntimeStateStore) -> None:
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    store.apply(TaskCreatedEvent(task_id="t2"), sequence=2)
    store.apply(TaskStartedEvent(task_id="t2"), sequence=3)
    store.apply(TaskCreatedEvent(task_id="t3"), sequence=4)
    store.apply(TaskFailedEvent(task_id="t3", duration_seconds=0.1), sequence=5)
    view = build_index_view(store.registry)
    assert set(view.active).issuperset({"t1", "t2"})
    assert view.failed == ["t3"]


# ── Concurrency ──────────────────────────────────────────────────────────


def test_concurrent_apply_does_not_corrupt_metrics(store: RuntimeStateStore) -> None:
    """Multiple threads applying events keep counters consistent."""
    EVENTS_PER_THREAD = 50
    THREADS = 4

    events: list[tuple[int, TaskCreatedEvent]] = []
    for t in range(THREADS):
        for i in range(EVENTS_PER_THREAD):
            events.append((t * EVENTS_PER_THREAD + i + 1, TaskCreatedEvent(task_id=f"t{t}-{i}")))

    def worker(start: int, end: int) -> None:
        for seq, evt in events[start:end]:
            store.apply(evt, sequence=seq)

    chunk = EVENTS_PER_THREAD
    threads = [
        threading.Thread(target=worker, args=(i * chunk, (i + 1) * chunk)) for i in range(THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    metrics = store.metrics_snapshot()
    # Every event id is unique, so no duplicates. Stale rejections may happen
    # because the workers are racing, but total applies + stale must equal total.
    assert metrics.events_applied + metrics.events_stale == THREADS * EVENTS_PER_THREAD
