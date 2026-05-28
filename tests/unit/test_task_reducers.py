from __future__ import annotations

import pytest

from asyncviz.runtime.clock import RuntimeClock, reset_runtime_clock, set_default_runtime_clock
from asyncviz.runtime.events.models import (
    TaskCancelledEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskFailedEvent,
    TaskResumedEvent,
    TaskStartedEvent,
    TaskWaitingEvent,
)
from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.state import (
    ProjectionName,
    ReducerContext,
    ReducerRegistry,
    RuntimeStateStore,
    TransitionHistory,
    TransitionRecord,
    UnknownReducerError,
    build_default_registry,
    evaluate_transition,
)
from asyncviz.runtime.state.reducers import (
    InvalidTransitionError,
    ProjectionInvalidationBus,
    ReducerMetrics,
    ReducerRegistrationError,
    TaskCancelledReducer,
    TaskCompletedReducer,
    TaskCreatedReducer,
    TaskFailedReducer,
    TaskStartedReducer,
    TaskWaitingReducer,
    TerminalStateLockedError,
    assert_transition,
)
from asyncviz.runtime.tasks import TaskRegistry


@pytest.fixture(autouse=True)
def _fresh_clock():
    reset_runtime_clock()
    clock = RuntimeClock()
    set_default_runtime_clock(clock)
    yield clock
    reset_runtime_clock()


@pytest.fixture
def ctx() -> ReducerContext:
    return ReducerContext(
        registry=TaskRegistry(),
        history=TransitionHistory(),
        projections=ProjectionInvalidationBus(),
        metrics=ReducerMetrics(),
        sequence=1,
    )


# ── Validation ────────────────────────────────────────────────────────────


def test_evaluate_transition_first_event_must_be_created() -> None:
    plan = evaluate_transition(current=None, target=TaskState.CREATED)
    assert plan.allowed
    plan2 = evaluate_transition(current=None, target=TaskState.RUNNING)
    assert not plan2.allowed
    assert "first event" in (plan2.reason or "")


def test_evaluate_transition_terminal_is_locked() -> None:
    plan = evaluate_transition(current=TaskState.COMPLETED, target=TaskState.RUNNING)
    assert not plan.allowed
    assert plan.terminal_blocked
    assert "terminal" in (plan.reason or "")


def test_evaluate_transition_legal_transitions() -> None:
    cases = [
        (TaskState.CREATED, TaskState.RUNNING),
        (TaskState.RUNNING, TaskState.WAITING),
        (TaskState.WAITING, TaskState.RUNNING),
        (TaskState.RUNNING, TaskState.COMPLETED),
        (TaskState.RUNNING, TaskState.FAILED),
        (TaskState.RUNNING, TaskState.CANCELLED),
    ]
    for current, target in cases:
        plan = evaluate_transition(current, target)
        assert plan.allowed, f"{current.value} → {target.value} should be allowed"


def test_assert_transition_raises_invalid() -> None:
    with pytest.raises(InvalidTransitionError):
        assert_transition(current=None, target=TaskState.RUNNING)


def test_assert_transition_raises_terminal() -> None:
    with pytest.raises(TerminalStateLockedError):
        assert_transition(current=TaskState.COMPLETED, target=TaskState.RUNNING)


# ── TransitionHistory ─────────────────────────────────────────────────────


def test_transition_history_appends_and_caps() -> None:
    history = TransitionHistory(per_task_limit=3)
    states = [
        TaskState.CREATED,
        TaskState.RUNNING,
        TaskState.WAITING,
        TaskState.RUNNING,
    ]
    for i, state in enumerate(states, start=1):
        history.append(
            "t1",
            TransitionRecord(
                sequence=i,
                state=state,
                monotonic_ns=i * 100,
                wall_seconds=float(i),
                event_id=f"e{i}",
                event_type=f"e{i}",
            ),
        )
    records = history.get("t1")
    assert len(records) == 3
    # Oldest was evicted.
    assert records[0].sequence == 2
    assert history.total_evicted == 1


def test_transition_history_export_is_json_safe() -> None:
    history = TransitionHistory()
    history.append(
        "t1",
        TransitionRecord(
            sequence=1,
            state=TaskState.CREATED,
            monotonic_ns=100,
            wall_seconds=1.0,
            event_id="e",
            event_type="t",
        ),
    )
    export = history.export()
    assert "t1" in export
    assert export["t1"][0]["state"] == "created"


# ── Per-reducer behavior ──────────────────────────────────────────────────


def test_task_created_reducer_registers_and_records(ctx: ReducerContext) -> None:
    reducer = TaskCreatedReducer()
    event = TaskCreatedEvent(task_id="t1", task_name="root")
    result = reducer.apply(ctx, event)
    assert result.applied is True
    assert result.target_state is TaskState.CREATED
    snap = ctx.registry.snapshot_task("t1")
    assert snap is not None and snap.state.value == "created"
    history = ctx.history.get("t1")
    assert len(history) == 1
    assert history[0].state is TaskState.CREATED


def test_task_created_reducer_rejects_duplicate(ctx: ReducerContext) -> None:
    reducer = TaskCreatedReducer()
    event = TaskCreatedEvent(task_id="t1")
    reducer.apply(ctx, event)
    second = reducer.apply(ctx, event)
    assert not second.applied
    assert second.invalid_transition


def test_task_started_reducer_requires_creation(ctx: ReducerContext) -> None:
    reducer = TaskStartedReducer()
    result = reducer.apply(ctx, TaskStartedEvent(task_id="unknown"))
    assert not result.applied
    assert result.invalid_transition


def test_task_started_then_waiting_then_resumed_sequence(ctx: ReducerContext) -> None:
    TaskCreatedReducer().apply(ctx, TaskCreatedEvent(task_id="t1"))
    started = TaskStartedReducer().apply(ctx, TaskStartedEvent(task_id="t1"))
    # RUNNING → RUNNING is not a legal transition; second TaskStartedEvent rejects.
    started_again = TaskStartedReducer().apply(ctx, TaskStartedEvent(task_id="t1"))
    waiting = TaskWaitingReducer().apply(ctx, TaskWaitingEvent(task_id="t1"))
    # WAITING → RUNNING is legal; resume returns to RUNNING.
    resumed = TaskStartedReducer().apply(ctx, TaskStartedEvent(task_id="t1"))
    assert started.applied
    assert not started_again.applied
    assert started_again.invalid_transition
    assert waiting.applied
    assert resumed.applied
    states = [r.state for r in ctx.history.get("t1")]
    assert states == [
        TaskState.CREATED,
        TaskState.RUNNING,
        TaskState.WAITING,
        TaskState.RUNNING,
    ]


def test_task_completed_after_running_is_legal(ctx: ReducerContext) -> None:
    TaskCreatedReducer().apply(ctx, TaskCreatedEvent(task_id="t1"))
    TaskStartedReducer().apply(ctx, TaskStartedEvent(task_id="t1"))
    result = TaskCompletedReducer().apply(
        ctx, TaskCompletedEvent(task_id="t1", duration_seconds=0.1)
    )
    assert result.applied
    snap = ctx.registry.snapshot_task("t1")
    assert snap is not None and snap.state.value == "completed"


def test_task_event_after_terminal_is_terminal_blocked(ctx: ReducerContext) -> None:
    TaskCreatedReducer().apply(ctx, TaskCreatedEvent(task_id="t1"))
    TaskCompletedReducer().apply(ctx, TaskCompletedEvent(task_id="t1", duration_seconds=0.1))
    result = TaskWaitingReducer().apply(ctx, TaskWaitingEvent(task_id="t1"))
    assert not result.applied
    assert result.terminal_blocked


def test_task_cancelled_marks_cancellations_projection(ctx: ReducerContext) -> None:
    TaskCreatedReducer().apply(ctx, TaskCreatedEvent(task_id="t1"))
    TaskCancelledReducer().apply(
        ctx,
        TaskCancelledEvent(task_id="t1", duration_seconds=0.1, cancellation_origin="explicit"),
    )
    counts = ctx.projections.metrics().counts
    assert counts.get(ProjectionName.CANCELLATIONS_BY_ORIGIN.value, 0) >= 1


def test_task_failed_records_exception(ctx: ReducerContext) -> None:
    TaskCreatedReducer().apply(ctx, TaskCreatedEvent(task_id="t1"))
    result = TaskFailedReducer().apply(
        ctx,
        TaskFailedEvent(
            task_id="t1",
            duration_seconds=0.1,
            exception_type="ValueError",
            exception_message="boom",
        ),
    )
    assert result.applied
    snap = ctx.registry.snapshot_task("t1")
    assert snap is not None and snap.exception_type == "ValueError"


# ── ReducerRegistry ───────────────────────────────────────────────────────


def test_registry_dispatch_returns_matching_reducer() -> None:
    registry = build_default_registry()
    event = TaskCompletedEvent(task_id="t1")
    reducer = registry.get_strict(event)
    assert isinstance(reducer, TaskCompletedReducer)


def test_registry_rejects_duplicate_registration() -> None:
    registry = ReducerRegistry()
    registry.register(TaskCreatedReducer())

    class AltCreatedReducer:
        event_type = TaskCreatedEvent
        name = "alt"

        def apply(self, ctx, event):
            raise NotImplementedError

    with pytest.raises(ReducerRegistrationError):
        registry.register(AltCreatedReducer())


def test_registry_replace_overwrites() -> None:
    registry = build_default_registry()
    original = registry.get(TaskCompletedEvent(task_id="t"))
    assert original is not None

    class NewCompleted(TaskCompletedReducer):
        pass

    replaced = registry.replace(NewCompleted())
    assert replaced is original
    new_reducer = registry.get(TaskCompletedEvent(task_id="t"))
    assert isinstance(new_reducer, NewCompleted)


def test_registry_unknown_event_class_is_strict_error() -> None:
    registry = ReducerRegistry()
    with pytest.raises(UnknownReducerError):
        registry.get_strict(TaskCreatedEvent(task_id="t"))


def test_registry_describe_lists_event_to_reducer_mapping() -> None:
    registry = build_default_registry()
    described = registry.describe()
    assert described["TaskCreatedEvent"] == "asyncio.task.created"
    assert described["TaskFailedEvent"] == "asyncio.task.failed"


# ── Reducer metrics ───────────────────────────────────────────────────────


def test_reducer_metrics_split_applied_vs_rejected(ctx: ReducerContext) -> None:
    TaskCreatedReducer().apply(ctx, TaskCreatedEvent(task_id="t1"))
    # Duplicate creation → rejected.
    TaskCreatedReducer().apply(ctx, TaskCreatedEvent(task_id="t1"))
    snap = ctx.metrics.snapshot()
    counters = snap.by_reducer["asyncio.task.created"]
    assert counters.applied == 1
    assert counters.rejected == 1
    assert counters.invalid_transitions == 1


def test_reducer_metrics_break_out_terminal_blocked(ctx: ReducerContext) -> None:
    TaskCreatedReducer().apply(ctx, TaskCreatedEvent(task_id="t1"))
    TaskCompletedReducer().apply(ctx, TaskCompletedEvent(task_id="t1", duration_seconds=0.1))
    TaskWaitingReducer().apply(ctx, TaskWaitingEvent(task_id="t1"))
    snap = ctx.metrics.snapshot()
    waiting = snap.by_reducer["asyncio.task.waiting"]
    assert waiting.rejected == 1
    assert waiting.terminal_blocked == 1


# ── Store integration ─────────────────────────────────────────────────────


def test_store_apply_populates_transition_history() -> None:
    reset_runtime_clock()
    set_default_runtime_clock(RuntimeClock())
    try:
        store = RuntimeStateStore(TaskRegistry())
        store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
        store.apply(TaskStartedEvent(task_id="t1"), sequence=2)
        store.apply(TaskWaitingEvent(task_id="t1"), sequence=3)
        store.apply(TaskResumedEvent(task_id="t1"), sequence=4)
        store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.1), sequence=5)
        history = store.history.get("t1")
        assert [r.state.value for r in history] == [
            "created",
            "running",
            "waiting",
            "running",
            "completed",
        ]
        assert [r.sequence for r in history] == [1, 2, 3, 4, 5]
    finally:
        reset_runtime_clock()


def test_store_snapshot_carries_transitions_by_default() -> None:
    reset_runtime_clock()
    set_default_runtime_clock(RuntimeClock())
    try:
        store = RuntimeStateStore(TaskRegistry())
        store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
        store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.05), sequence=2)
        snap = store.snapshot()
        assert "t1" in snap.transitions
        states = [r["state"] for r in snap.transitions["t1"]]
        assert states == ["created", "completed"]
    finally:
        reset_runtime_clock()


def test_store_snapshot_can_omit_transitions() -> None:
    reset_runtime_clock()
    set_default_runtime_clock(RuntimeClock())
    try:
        store = RuntimeStateStore(TaskRegistry())
        store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
        snap = store.snapshot(include_transitions=False)
        assert snap.transitions == {}
    finally:
        reset_runtime_clock()


def test_store_rebuild_resets_transitions_and_metrics() -> None:
    reset_runtime_clock()
    set_default_runtime_clock(RuntimeClock())
    try:
        store = RuntimeStateStore(TaskRegistry())
        store.apply(TaskCreatedEvent(task_id="t1"), sequence=1)
        store.apply(TaskCompletedEvent(task_id="t1", duration_seconds=0.1), sequence=2)
        assert len(store.history.get("t1")) == 2
        assert store.reducer_metrics_snapshot().total_applied == 2

        store.rebuild([])
        assert store.history.get("t1") == ()
        assert store.reducer_metrics_snapshot().total_applied == 0
    finally:
        reset_runtime_clock()


# ── Legacy compatibility ──────────────────────────────────────────────────


def test_legacy_find_reducer_still_works() -> None:
    from asyncviz.runtime.state.reducers import find_reducer

    registry = TaskRegistry()
    reducer = find_reducer(TaskCreatedEvent(task_id="t"))
    assert reducer is not None
    # Old callable shape: (registry, event) -> None
    reducer(registry, TaskCreatedEvent(task_id="t"))
    assert registry.snapshot_task("t") is not None


def test_legacy_reduce_function_compatibility() -> None:
    from asyncviz.runtime.state.reducers import reduce_task_created

    registry = TaskRegistry()
    reduce_task_created(registry, TaskCreatedEvent(task_id="t"))
    assert registry.snapshot_task("t") is not None
