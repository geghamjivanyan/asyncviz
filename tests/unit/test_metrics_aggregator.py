from __future__ import annotations

import json
import threading

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
from asyncviz.runtime.metrics import (
    ApproxHistogram,
    CounterSet,
    DurationAggregator,
    MetricsDelta,
    MetricsIntent,
    RateMeter,
    RuntimeMetricsAggregateSnapshot,
    RuntimeMetricsAggregator,
    aggregate_coroutine_groups,
    aggregate_lineage,
    longest_running_tasks,
    normalize,
)
from asyncviz.runtime.state import RuntimeStateStore
from asyncviz.runtime.tasks import TaskMetadata, TaskRegistry


@pytest.fixture(autouse=True)
def _fresh_clock():
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    yield clock
    reset_runtime_clock()


@pytest.fixture
def aggregator(_fresh_clock: RuntimeClock) -> RuntimeMetricsAggregator:
    return RuntimeMetricsAggregator(TaskRegistry(), clock=_fresh_clock)


# ── CounterSet ────────────────────────────────────────────────────────────


def test_counter_inc_and_total() -> None:
    cs = CounterSet()
    cs.inc("a")
    cs.inc("a", delta=4)
    cs.inc("b")
    assert cs.get("a") == 5
    assert cs.get("b") == 1
    assert cs.total() == 6


def test_counter_reset_clears() -> None:
    cs = CounterSet()
    cs.inc("a")
    cs.reset()
    assert cs.snapshot() == {}


# ── ApproxHistogram ───────────────────────────────────────────────────────


def test_histogram_zero_count_returns_zeroed_snapshot() -> None:
    h = ApproxHistogram()
    snap = h.snapshot()
    assert snap.count == 0
    assert snap.mean == 0.0


def test_histogram_basic_percentiles() -> None:
    h = ApproxHistogram(capacity=2048, seed=42)
    for v in range(1, 101):  # uniform 1..100
        h.observe(float(v))
    snap = h.snapshot()
    assert snap.count == 100
    assert snap.min_value == 1.0
    assert snap.max_value == 100.0
    # Approximation tolerance is wide because percentile is interpolated
    # over the reservoir. With capacity > count, reservoir == samples.
    assert 45 <= snap.p50 <= 55
    assert 90 <= snap.p95 <= 100
    assert 95 <= snap.p99 <= 100


def test_histogram_reservoir_caps_at_capacity() -> None:
    h = ApproxHistogram(capacity=100, seed=0)
    for v in range(1000):
        h.observe(float(v))
    snap = h.snapshot()
    assert snap.count == 1000
    assert snap.samples == 100  # capped


def test_histogram_rejects_negative_values() -> None:
    h = ApproxHistogram()
    h.observe(-1.0)
    assert h.count == 0


# ── RateMeter ─────────────────────────────────────────────────────────────


def test_rate_meter_records_observations() -> None:
    m = RateMeter(window_seconds=10)
    for sec in range(5):
        m.observe(monotonic_seconds=float(sec))
    snap = m.snapshot(monotonic_seconds=4.0)
    assert snap.total_observations == 5
    assert snap.window_seconds == 10
    # 5 events over 10 seconds = 0.5/s
    assert snap.rate_per_second == pytest.approx(0.5)


def test_rate_meter_decays_when_idle() -> None:
    m = RateMeter(window_seconds=5)
    m.observe(monotonic_seconds=0.0, count=10)
    snap_now = m.snapshot(monotonic_seconds=0.0)
    assert snap_now.rate_per_second == pytest.approx(2.0)
    # 10 seconds later, all buckets are out of the window.
    snap_later = m.snapshot(monotonic_seconds=20.0)
    assert snap_later.rate_per_second == 0.0


# ── DurationAggregator ────────────────────────────────────────────────────


def test_duration_aggregator_running_stats() -> None:
    d = DurationAggregator(capacity=128, seed=7)
    for s in (0.1, 0.2, 0.3, 0.4, 0.5):
        d.observe(s)
    snap = d.snapshot()
    assert snap.count == 5
    assert snap.total_seconds == pytest.approx(1.5)
    assert snap.min_seconds == pytest.approx(0.1)
    assert snap.max_seconds == pytest.approx(0.5)
    assert snap.mean_seconds == pytest.approx(0.3)


# ── Normalization ─────────────────────────────────────────────────────────


def test_normalize_task_events_carry_intent() -> None:
    cases = [
        (TaskCreatedEvent(task_id="t"), MetricsIntent.CREATE),
        (TaskStartedEvent(task_id="t"), MetricsIntent.START),
        (TaskWaitingEvent(task_id="t"), MetricsIntent.WAIT),
        (TaskCompletedEvent(task_id="t", duration_seconds=0.1), MetricsIntent.COMPLETE),
        (TaskCancelledEvent(task_id="t", duration_seconds=0.1), MetricsIntent.CANCEL),
        (TaskFailedEvent(task_id="t", duration_seconds=0.1), MetricsIntent.FAIL),
    ]
    for event, expected in cases:
        norm = normalize(event, sequence=None)
        assert norm.intent is expected, (event, expected)


def test_normalize_non_task_events_have_ignore_intent() -> None:
    norm = normalize(create_runtime_metric(name="x", value=1.0), sequence=None)
    assert norm.intent is MetricsIntent.IGNORE


# ── Aggregator core ───────────────────────────────────────────────────────


def test_aggregator_lifecycle_counts(aggregator: RuntimeMetricsAggregator) -> None:
    aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    aggregator.apply_event(TaskCreatedEvent(task_id="t2"), sequence=2)
    aggregator.apply_event(TaskCompletedEvent(task_id="t1", duration_seconds=0.1), sequence=3)
    counts = aggregator.counts_snapshot()
    assert counts["total"] == 2
    assert counts["active"] == 1
    assert counts["completed"] == 1
    assert counts["terminal"] == 1


def test_aggregator_records_duration_into_completed_bucket(
    aggregator: RuntimeMetricsAggregator,
) -> None:
    aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    aggregator.apply_event(TaskCompletedEvent(task_id="t1", duration_seconds=0.5), sequence=2)
    aggregator.apply_event(TaskCreatedEvent(task_id="t2"), sequence=3)
    aggregator.apply_event(TaskCompletedEvent(task_id="t2", duration_seconds=1.5), sequence=4)
    completed = aggregator.completed_durations.snapshot()
    assert completed.count == 2
    assert completed.total_seconds == pytest.approx(2.0)
    overall = aggregator.overall_durations.snapshot()
    assert overall.count == 2


def test_aggregator_records_cancellation_origins(aggregator: RuntimeMetricsAggregator) -> None:
    aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    aggregator.apply_event(
        TaskCancelledEvent(task_id="t1", duration_seconds=0.1, cancellation_origin="shutdown"),
        sequence=2,
    )
    aggregator.apply_event(TaskCreatedEvent(task_id="t2"), sequence=3)
    aggregator.apply_event(
        TaskCancelledEvent(task_id="t2", duration_seconds=0.1, cancellation_origin="explicit"),
        sequence=4,
    )
    assert aggregator.cancellations_by_origin.snapshot() == {"shutdown": 1, "explicit": 1}


def test_aggregator_rejects_duplicate_events(aggregator: RuntimeMetricsAggregator) -> None:
    evt = TaskCreatedEvent(task_id="t1")
    aggregator.apply_event(evt, sequence=1)
    accepted = aggregator.apply_event(evt, sequence=2)  # same event_id
    assert accepted is False
    self_metrics = aggregator.self_metrics_snapshot()
    assert self_metrics.events_duplicate == 1


def test_aggregator_rejects_stale_sequence(aggregator: RuntimeMetricsAggregator) -> None:
    aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=10)
    accepted = aggregator.apply_event(TaskCreatedEvent(task_id="t2"), sequence=5)
    assert accepted is False
    self_metrics = aggregator.self_metrics_snapshot()
    assert self_metrics.events_stale == 1


def test_aggregator_ignores_non_task_events(aggregator: RuntimeMetricsAggregator) -> None:
    accepted = aggregator.apply_event(create_runtime_metric(name="x", value=1.0), sequence=1)
    assert accepted is False
    counts = aggregator.counts_snapshot()
    assert counts == {} or counts.get("total", 0) == 0


# ── Throughput rates ──────────────────────────────────────────────────────


def test_aggregator_throughput_tracks_creates() -> None:
    reset_runtime_clock()
    set_default_runtime_clock(RuntimeClock())
    aggregator = RuntimeMetricsAggregator(TaskRegistry(), rate_window_seconds=5)
    # Each TaskCreatedEvent stamps its own monotonic_ns from the clock;
    # they'll all land in the same second bucket, producing 4/window_seconds rate.
    for i in range(4):
        aggregator.apply_event(TaskCreatedEvent(task_id=f"t{i}"), sequence=i + 1)
    rate = aggregator.rate_meter("tasks").snapshot(
        monotonic_seconds=aggregator.clock.runtime_uptime()
    )
    assert rate.total_observations == 4
    # Spread over the window — rate is total / window_seconds.
    assert rate.rate_per_second > 0.0


# ── Subscription / streaming ──────────────────────────────────────────────


def test_aggregator_notifies_subscribers(aggregator: RuntimeMetricsAggregator) -> None:
    deltas: list[MetricsDelta] = []
    aggregator.subscribe(deltas.append)
    aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    aggregator.apply_event(TaskCompletedEvent(task_id="t1", duration_seconds=0.1), sequence=2)
    assert len(deltas) == 2
    assert deltas[0].changes == {"total": 1, "active": 1}
    assert deltas[1].terminal_state == "completed"
    assert deltas[1].duration_added_seconds == pytest.approx(0.1)


def test_aggregator_isolates_subscriber_failures(
    aggregator: RuntimeMetricsAggregator,
) -> None:
    good: list[MetricsDelta] = []

    def bad(_d: MetricsDelta) -> None:
        raise RuntimeError("boom")

    aggregator.subscribe(bad)
    aggregator.subscribe(good.append)
    aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    assert len(good) == 1
    assert aggregator.self_metrics_snapshot().subscription_failures == 1


def test_aggregator_unsubscribe_stops_notifications(
    aggregator: RuntimeMetricsAggregator,
) -> None:
    received: list[MetricsDelta] = []
    sub = aggregator.subscribe(received.append)
    aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    assert aggregator.unsubscribe(sub) is True
    aggregator.apply_event(TaskCreatedEvent(task_id="t2"), sequence=2)
    assert len(received) == 1


# ── Snapshot ──────────────────────────────────────────────────────────────


def test_snapshot_round_trips_through_pydantic(aggregator: RuntimeMetricsAggregator) -> None:
    # Seed the registry so coroutine + lineage projections have data.
    aggregator.registry.register("t1", metadata=TaskMetadata(coroutine_name="alpha"))
    aggregator.apply_event(TaskCreatedEvent(task_id="t1", coroutine_name="alpha"), sequence=1)
    aggregator.apply_event(TaskCompletedEvent(task_id="t1", duration_seconds=0.05), sequence=2)
    snap = aggregator.snapshot()
    assert isinstance(snap, RuntimeMetricsAggregateSnapshot)
    raw = snap.model_dump_json()
    rebuilt = RuntimeMetricsAggregateSnapshot.model_validate(json.loads(raw))
    assert rebuilt.counts.total == 1
    assert rebuilt.counts.completed == 1
    assert rebuilt.last_sequence == 2
    assert rebuilt.runtime_id == str(aggregator.clock.runtime_id)


def test_snapshot_includes_self_metrics(aggregator: RuntimeMetricsAggregator) -> None:
    aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    snap = aggregator.snapshot()
    assert snap.self_metrics.events_observed == 1
    assert snap.self_metrics.snapshots_emitted >= 1


def test_snapshot_coroutine_rows_sorted_by_count() -> None:
    reset_runtime_clock()
    set_default_runtime_clock(RuntimeClock())
    registry = TaskRegistry()
    registry.register("t1", metadata=TaskMetadata(coroutine_name="alpha"))
    registry.register("t2", metadata=TaskMetadata(coroutine_name="alpha"))
    registry.register("t3", metadata=TaskMetadata(coroutine_name="beta"))
    aggregator = RuntimeMetricsAggregator(registry)
    snap = aggregator.snapshot()
    names = [r.coroutine_name for r in snap.coroutines]
    assert names[0] == "alpha"  # higher task_count first


# ── Rebuild ───────────────────────────────────────────────────────────────


def test_rebuild_resets_and_replays(aggregator: RuntimeMetricsAggregator) -> None:
    aggregator.apply_event(TaskCreatedEvent(task_id="t1"), sequence=1)
    aggregator.apply_event(TaskCompletedEvent(task_id="t1", duration_seconds=0.1), sequence=2)
    assert aggregator.counts_snapshot()["completed"] == 1

    events = [
        (TaskCreatedEvent(task_id="r1"), 1),
        (TaskCreatedEvent(task_id="r2"), 2),
        (TaskCancelledEvent(task_id="r1", duration_seconds=0.05), 3),
    ]
    applied = aggregator.rebuild(events)
    assert applied == 3
    counts = aggregator.counts_snapshot()
    assert counts["total"] == 2
    assert counts["cancelled"] == 1
    assert counts.get("completed", 0) == 0
    assert aggregator.self_metrics_snapshot().rebuilds_completed == 1


# ── State-store integration ───────────────────────────────────────────────


def test_aggregator_bound_to_state_store(_fresh_clock: RuntimeClock) -> None:
    store = RuntimeStateStore(TaskRegistry())
    aggregator = RuntimeMetricsAggregator(store.registry, clock=_fresh_clock)
    aggregator.bind(store)
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.05), sequence=2)
    counts = aggregator.counts_snapshot()
    assert counts["total"] == 1
    assert counts["completed"] == 1


# ── Projections ───────────────────────────────────────────────────────────


def test_aggregate_coroutine_groups_orders_by_count() -> None:
    reset_runtime_clock()
    set_default_runtime_clock(RuntimeClock())
    registry = TaskRegistry()
    for tid, name in [
        ("t1", "alpha"),
        ("t2", "alpha"),
        ("t3", "alpha"),
        ("t4", "beta"),
        ("t5", None),
    ]:
        registry.register(tid, metadata=TaskMetadata(coroutine_name=name))
    rows = aggregate_coroutine_groups(registry.snapshot_all_tasks())
    names = [r.coroutine_name for r in rows]
    assert names == ["alpha", "<anonymous>", "beta"]


def test_aggregate_lineage_summary() -> None:
    reset_runtime_clock()
    set_default_runtime_clock(RuntimeClock())
    registry = TaskRegistry()
    registry.register("root")
    registry.register("c1", metadata=TaskMetadata(parent_task_id="root"))
    registry.register("c2", metadata=TaskMetadata(parent_task_id="root"))
    registry.register("gc", metadata=TaskMetadata(parent_task_id="c1"))
    summary = aggregate_lineage(registry.snapshot_all_tasks())
    assert summary.root_count == 1
    assert summary.max_depth == 2
    assert summary.largest_tree_size == 4
    assert summary.largest_tree_root_id == "root"


def test_longest_running_tasks_picks_top_n() -> None:
    reset_runtime_clock()
    set_default_runtime_clock(RuntimeClock())
    registry = TaskRegistry()
    durations = [0.1, 0.5, 0.2, 0.4, 0.3]
    for i, d in enumerate(durations):
        registry.register(f"t{i}")
        registry.handle_event(TaskCompletedEvent(task_id=f"t{i}", duration_seconds=d))
    top = longest_running_tasks(registry.snapshot_all_tasks(), limit=3)
    assert [t.task_id for t in top][:3] == ["t1", "t3", "t4"]


# ── Concurrency ───────────────────────────────────────────────────────────


def test_concurrent_apply_metrics_correct(aggregator: RuntimeMetricsAggregator) -> None:
    EVENTS = 100
    THREADS = 4
    events = [(TaskCreatedEvent(task_id=f"t-{i}"), i + 1) for i in range(EVENTS)]

    def worker(start: int, end: int) -> None:
        for evt, seq in events[start:end]:
            aggregator.apply_event(evt, sequence=seq)

    chunk = EVENTS // THREADS
    threads = [
        threading.Thread(target=worker, args=(i * chunk, (i + 1) * chunk)) for i in range(THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    observed = aggregator.self_metrics_snapshot().events_observed
    stale = aggregator.self_metrics_snapshot().events_stale
    assert observed + stale == EVENTS
