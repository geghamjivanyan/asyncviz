from __future__ import annotations

import itertools
import json

import pytest

from asyncviz.runtime.clock import RuntimeClock, reset_runtime_clock, set_default_runtime_clock
from asyncviz.runtime.events.models import (
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskResumedEvent,
    TaskStartedEvent,
    TaskWaitingEvent,
)
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state import RuntimeStateStore
from asyncviz.runtime.state.reducers import TransitionRecord
from asyncviz.runtime.tasks import TaskRegistry
from asyncviz.runtime.timeline import (
    LifecycleSpan,
    SegmentIntent,
    TimelineSegment,
    TimelineSegmentEngine,
    TimelineSnapshot,
    intent_for,
    project_coroutine_tracks,
    project_per_task_tracks,
    project_root_tracks,
    replay_history,
    replay_state_store,
)


@pytest.fixture(autouse=True)
def _fresh_clock():
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    yield clock
    reset_runtime_clock()


@pytest.fixture
def engine(_fresh_clock: RuntimeClock) -> TimelineSegmentEngine:
    return TimelineSegmentEngine(clock=_fresh_clock)


# ── Intent classification ────────────────────────────────────────────────


def test_intent_for_created_is_create() -> None:
    assert intent_for(TaskState.CREATED) is SegmentIntent.CREATE


def test_intent_for_running_opens_run_segment() -> None:
    assert intent_for(TaskState.RUNNING) is SegmentIntent.OPEN_RUN


def test_intent_for_waiting_opens_wait_segment() -> None:
    assert intent_for(TaskState.WAITING) is SegmentIntent.OPEN_WAIT


def test_intent_for_terminal_states_close_and_finalize() -> None:
    assert intent_for(TaskState.COMPLETED) is SegmentIntent.CLOSE_AND_FINALIZE
    assert intent_for(TaskState.CANCELLED) is SegmentIntent.CLOSE_AND_FINALIZE
    assert intent_for(TaskState.FAILED) is SegmentIntent.CLOSE_AND_FINALIZE


# ── Single-task lifecycle ─────────────────────────────────────────────────


def _apply(
    engine: TimelineSegmentEngine,
    task_id: str,
    target: TaskState,
    *,
    sequence: int,
    monotonic_ns: int,
    wall_seconds: float = 0.0,
    **kw,
):
    return engine.apply_transition(
        task_id=task_id,
        target=target,
        sequence=sequence,
        monotonic_ns=monotonic_ns,
        wall_seconds=wall_seconds,
        **kw,
    )


def test_created_then_running_opens_run_segment(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=100)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=200)
    state = engine.state_of("t1")
    assert state is not None
    assert state.open_segment is not None
    assert state.open_segment.segment_type == "run"
    assert state.open_segment.monotonic_start_ns == 200


def test_running_then_waiting_closes_run_opens_wait(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=100)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=200)
    _apply(engine, "t1", TaskState.WAITING, sequence=3, monotonic_ns=350)
    segments = engine.segments_for("t1")
    assert len(segments) == 1
    assert segments[0].segment_type == "run"
    assert segments[0].monotonic_start_ns == 200
    assert segments[0].monotonic_end_ns == 350
    assert segments[0].duration_ns == 150
    state = engine.state_of("t1")
    assert state is not None and state.open_segment is not None
    assert state.open_segment.segment_type == "wait"


def test_waiting_then_running_decomposes_wait_segment(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=100)
    _apply(engine, "t1", TaskState.WAITING, sequence=3, monotonic_ns=200)
    _apply(engine, "t1", TaskState.RUNNING, sequence=4, monotonic_ns=350)
    segments = engine.segments_for("t1")
    assert [s.segment_type for s in segments] == ["run", "wait"]
    assert segments[1].duration_ns == 150


def test_completed_finalizes_open_segment(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=100)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=200)
    result = _apply(engine, "t1", TaskState.COMPLETED, sequence=3, monotonic_ns=500)
    assert result.applied
    assert result.finalized_task
    state = engine.state_of("t1")
    assert state is not None
    assert state.terminal_state == "completed"
    assert state.terminated_at_monotonic_ns == 500
    assert state.open_segment is None
    segments = engine.segments_for("t1")
    assert len(segments) == 1
    assert segments[0].segment_type == "run"
    assert segments[0].monotonic_end_ns == 500


def test_cancelled_after_waiting_closes_wait_segment(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=100)
    _apply(engine, "t1", TaskState.WAITING, sequence=3, monotonic_ns=200)
    _apply(engine, "t1", TaskState.CANCELLED, sequence=4, monotonic_ns=400)
    segments = engine.segments_for("t1")
    assert [s.segment_type for s in segments] == ["run", "wait"]
    assert segments[1].duration_ns == 200


# ── Reconciliation / invalid transitions ──────────────────────────────────


def test_double_create_is_rejected(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=100)
    result = _apply(engine, "t1", TaskState.CREATED, sequence=2, monotonic_ns=200)
    assert not result.applied
    assert result.invalid


def test_running_without_created_is_rejected(engine: TimelineSegmentEngine) -> None:
    result = _apply(engine, "t1", TaskState.RUNNING, sequence=1, monotonic_ns=100)
    assert not result.applied
    assert result.invalid


def test_terminal_lock_rejects_subsequent_transitions(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=100)
    _apply(engine, "t1", TaskState.COMPLETED, sequence=3, monotonic_ns=200)
    rejected = _apply(engine, "t1", TaskState.WAITING, sequence=4, monotonic_ns=300)
    assert not rejected.applied
    assert rejected.invalid
    second_terminal = _apply(engine, "t1", TaskState.CANCELLED, sequence=5, monotonic_ns=400)
    assert not second_terminal.applied


def test_duration_is_never_negative_under_monotonic_anomaly(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=500)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=600)
    # End ns is BEFORE start ns — pathological clock anomaly.
    _apply(engine, "t1", TaskState.COMPLETED, sequence=3, monotonic_ns=50)
    segments = engine.segments_for("t1")
    assert segments[0].duration_ns == 0


# ── Metrics ───────────────────────────────────────────────────────────────


def test_metrics_reflect_segmentation(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=100)
    _apply(engine, "t1", TaskState.WAITING, sequence=3, monotonic_ns=200)
    _apply(engine, "t1", TaskState.RUNNING, sequence=4, monotonic_ns=300)
    _apply(engine, "t1", TaskState.COMPLETED, sequence=5, monotonic_ns=400)
    metrics = engine.metrics_snapshot()
    assert metrics.transitions_applied == 5
    assert metrics.segments_opened == 3  # run, wait, run
    assert metrics.segments_closed == 3  # each open closed eventually
    assert metrics.active_segments == 0  # task is finalized
    assert metrics.finalized_spans == 1
    assert metrics.segments_by_type.get("run") == 2
    assert metrics.segments_by_type.get("wait") == 1


def test_active_segments_gauge_decrements_on_close(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=100)
    assert engine.metrics_snapshot().active_segments == 1
    _apply(engine, "t1", TaskState.COMPLETED, sequence=3, monotonic_ns=200)
    assert engine.metrics_snapshot().active_segments == 0


# ── Snapshot ──────────────────────────────────────────────────────────────


def test_snapshot_round_trips_through_pydantic(engine: TimelineSegmentEngine) -> None:
    _apply(
        engine,
        "t1",
        TaskState.CREATED,
        sequence=1,
        monotonic_ns=0,
        coroutine_name="alpha",
        task_name="root",
    )
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=100)
    _apply(engine, "t1", TaskState.COMPLETED, sequence=3, monotonic_ns=200)
    snap = engine.snapshot()
    assert isinstance(snap, TimelineSnapshot)
    raw = snap.model_dump_json()
    rebuilt = TimelineSnapshot.model_validate(json.loads(raw))
    assert rebuilt.last_sequence == 3
    assert "t1" in rebuilt.spans_by_task
    span = rebuilt.spans_by_task["t1"]
    assert span.terminal_state == "completed"
    assert span.run_duration_ns == 100
    assert span.segment_count == 1


def test_snapshot_includes_active_segments(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=100)
    snap = engine.snapshot()
    assert len(snap.active_segments) == 1
    assert snap.active_segments[0].segment_type == "run"


def test_snapshot_is_deterministic_repeated_calls(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t2", TaskState.CREATED, sequence=2, monotonic_ns=10)
    _apply(engine, "t1", TaskState.RUNNING, sequence=3, monotonic_ns=20)
    _apply(engine, "t2", TaskState.RUNNING, sequence=4, monotonic_ns=30)
    snap1 = engine.snapshot()
    snap2 = engine.snapshot()
    # Track ordering is stable even though wall_now / monotonic_now advance.
    assert [t.track_id for t in snap1.tracks] == [t.track_id for t in snap2.tracks]


# ── Replay reconstruction ────────────────────────────────────────────────


def _record(sequence: int, state: TaskState, ns: int, wall: float = 0.0) -> TransitionRecord:
    return TransitionRecord(
        sequence=sequence,
        state=state,
        monotonic_ns=ns,
        wall_seconds=wall,
        event_id=f"e{sequence}",
        event_type=f"asyncio.task.{state.value}",
    )


def test_replay_history_reconstructs_segments(engine: TimelineSegmentEngine) -> None:
    history = {
        "t1": [
            _record(1, TaskState.CREATED, 0),
            _record(2, TaskState.RUNNING, 100),
            _record(3, TaskState.WAITING, 200),
            _record(4, TaskState.RUNNING, 300),
            _record(5, TaskState.COMPLETED, 400),
        ]
    }
    applied = replay_history(engine, history)
    assert applied == 5
    segments = engine.segments_for("t1")
    assert [s.segment_type for s in segments] == ["run", "wait", "run"]
    assert [s.duration_ns for s in segments] == [100, 100, 100]


def test_replay_history_orders_cross_task_by_sequence(engine: TimelineSegmentEngine) -> None:
    history = {
        "t1": [
            _record(1, TaskState.CREATED, 0),
            _record(3, TaskState.RUNNING, 100),
        ],
        "t2": [
            _record(2, TaskState.CREATED, 50),
            _record(4, TaskState.RUNNING, 150),
        ],
    }
    replay_history(engine, history)
    # Both tasks have one open run segment after replay.
    assert engine.state_of("t1").open_segment is not None  # type: ignore[union-attr]
    assert engine.state_of("t2").open_segment is not None  # type: ignore[union-attr]


def test_engine_rebuild_resets_and_replays(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=100)
    assert engine.metrics_snapshot().segments_opened == 1
    history = {
        "t2": [
            _record(1, TaskState.CREATED, 0),
            _record(2, TaskState.RUNNING, 100),
            _record(3, TaskState.COMPLETED, 200),
        ]
    }
    engine.rebuild(history)
    assert engine.state_of("t1") is None  # cleared
    span = engine.queries.get_span("t2")
    assert span is not None
    assert span.terminal_state == "completed"
    assert engine.metrics_snapshot().rebuilds_completed == 1


def test_replay_state_store_uses_real_transitions(_fresh_clock: RuntimeClock) -> None:
    store = RuntimeStateStore(TaskRegistry())
    store.apply(TaskCreatedEvent(task_id="t1", coroutine_name="alpha"), sequence=1)
    store.apply(TaskStartedEvent(task_id="t1"), sequence=2)
    store.apply(TaskWaitingEvent(task_id="t1"), sequence=3)
    store.apply(TaskResumedEvent(task_id="t1"), sequence=4)
    store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.1), sequence=5)

    engine = TimelineSegmentEngine(clock=_fresh_clock)
    applied = replay_state_store(engine, store)
    assert applied == 5
    span = engine.queries.get_span("t1")
    assert span is not None
    assert span.terminal_state == "completed"
    assert [s.segment_type for s in span.segments] == ["run", "wait", "run"]
    assert span.coroutine_name == "alpha"


# ── State-store integration ──────────────────────────────────────────────


def test_engine_bound_to_state_store_observes_transitions(_fresh_clock: RuntimeClock) -> None:
    store = RuntimeStateStore(TaskRegistry())
    engine = TimelineSegmentEngine(clock=_fresh_clock)
    engine.bind(store)
    store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
    store.apply(TaskStartedEvent(task_id="t1"), sequence=2)
    store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.1), sequence=3)
    span = engine.queries.get_span("t1")
    assert span is not None
    assert span.terminal_state == "completed"


def test_engine_ignores_non_task_events_via_bind(_fresh_clock: RuntimeClock) -> None:
    from asyncviz.runtime.events.models import create_runtime_metric

    store = RuntimeStateStore(TaskRegistry())
    engine = TimelineSegmentEngine(clock=_fresh_clock)
    engine.bind(store)
    store.apply(create_runtime_metric(name="x", value=1.0), sequence=1)
    assert engine.metrics_snapshot().transitions_applied == 0


# ── Lineage / projections ────────────────────────────────────────────────


def test_per_task_tracks_one_per_span(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t2", TaskState.CREATED, sequence=2, monotonic_ns=10)
    spans = engine.queries.get_all_spans()
    tracks = project_per_task_tracks(spans)
    assert len(tracks) == 2
    for track in tracks:
        assert len(track.spans) == 1
        assert track.track_type == "task"


def test_root_tracks_group_by_root(engine: TimelineSegmentEngine) -> None:
    _apply(
        engine, "root", TaskState.CREATED, sequence=1, monotonic_ns=0, root_task_id="root", depth=0
    )
    _apply(
        engine,
        "child",
        TaskState.CREATED,
        sequence=2,
        monotonic_ns=10,
        parent_task_id="root",
        root_task_id="root",
        depth=1,
    )
    _apply(
        engine,
        "grand",
        TaskState.CREATED,
        sequence=3,
        monotonic_ns=20,
        parent_task_id="child",
        root_task_id="root",
        depth=2,
    )
    tracks = project_root_tracks(engine.queries.get_all_spans())
    assert len(tracks) == 1
    track = tracks[0]
    assert track.track_id == "root:root"
    assert len(track.spans) == 3
    # DFS order: root, child, grand by depth.
    assert [s.task_id for s in track.spans] == ["root", "child", "grand"]


def test_coroutine_tracks_group_by_name(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0, coroutine_name="alpha")
    _apply(engine, "t2", TaskState.CREATED, sequence=2, monotonic_ns=10, coroutine_name="alpha")
    _apply(engine, "t3", TaskState.CREATED, sequence=3, monotonic_ns=20, coroutine_name="beta")
    tracks = project_coroutine_tracks(engine.queries.get_all_spans())
    assert len(tracks) == 2
    by_label = {t.label: t for t in tracks}
    assert len(by_label["alpha"].spans) == 2
    assert len(by_label["beta"].spans) == 1


# ── Wall-clock total_duration semantics ──────────────────────────────────


def test_active_task_has_growing_total_duration(_fresh_clock: RuntimeClock) -> None:
    engine = TimelineSegmentEngine(clock=_fresh_clock)
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=_fresh_clock.monotonic_ns())
    span1 = engine.queries.get_span("t1")
    assert span1 is not None and span1.terminal_state is None
    # The duration is computed against "now" — strictly non-negative.
    assert span1.total_duration_ns >= 0


def test_terminated_task_has_fixed_total_duration(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=100)
    _apply(engine, "t1", TaskState.COMPLETED, sequence=2, monotonic_ns=400)
    span = engine.queries.get_span("t1")
    assert span is not None
    assert span.total_duration_ns == 300


# ── Sequence monotonicity ────────────────────────────────────────────────


def test_segment_sequences_are_monotonic(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=100)
    _apply(engine, "t1", TaskState.WAITING, sequence=3, monotonic_ns=200)
    _apply(engine, "t1", TaskState.RUNNING, sequence=4, monotonic_ns=300)
    _apply(engine, "t1", TaskState.COMPLETED, sequence=5, monotonic_ns=400)
    segments: tuple[TimelineSegment, ...] = engine.segments_for("t1")
    sequences = [s.sequence_start for s in segments if s.sequence_start is not None]
    assert all(b > a for a, b in itertools.pairwise(sequences))


# ── Queries ──────────────────────────────────────────────────────────────


def test_queries_active_segment(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t1", TaskState.RUNNING, sequence=2, monotonic_ns=100)
    active = engine.queries.get_active_segment("t1")
    assert active is not None
    assert active.segment_type == "run"


def test_queries_get_span_returns_none_for_unknown(engine: TimelineSegmentEngine) -> None:
    assert engine.queries.get_span("unknown") is None


def test_lifecycle_span_to_dict_is_json_safe(engine: TimelineSegmentEngine) -> None:
    _apply(engine, "t1", TaskState.CREATED, sequence=1, monotonic_ns=0)
    _apply(engine, "t1", TaskState.COMPLETED, sequence=2, monotonic_ns=100)
    span = engine.queries.get_span("t1")
    assert isinstance(span, LifecycleSpan)
    json.dumps(span.model_dump(mode="json"))
