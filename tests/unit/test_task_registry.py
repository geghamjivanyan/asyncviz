from __future__ import annotations

import threading
import uuid

import pytest

from asyncviz.runtime.events.models.enums import TaskState
from asyncviz.runtime.tasks import (
    DuplicateTaskError,
    InvalidParentReferenceError,
    InvalidStateTransitionError,
    RuntimeTask,
    TaskMetadata,
    TaskRegistry,
    TaskSnapshot,
    UnknownTaskError,
    can_transition,
    is_terminal,
)

# ── state semantics ─────────────────────────────────────────────────────────


def test_terminal_states_have_no_outgoing_transitions() -> None:
    for state in (TaskState.COMPLETED, TaskState.CANCELLED, TaskState.FAILED):
        assert is_terminal(state)
        for target in TaskState:
            assert not can_transition(state, target)


def test_created_can_transition_to_any_active_or_terminal() -> None:
    for target in (
        TaskState.RUNNING,
        TaskState.WAITING,
        TaskState.COMPLETED,
        TaskState.CANCELLED,
        TaskState.FAILED,
    ):
        assert can_transition(TaskState.CREATED, target)


def test_running_to_running_is_not_allowed() -> None:
    assert not can_transition(TaskState.RUNNING, TaskState.RUNNING)


# ── registration ────────────────────────────────────────────────────────────


def test_register_minimal() -> None:
    registry = TaskRegistry()
    task = registry.register("t1")
    assert isinstance(task, RuntimeTask)
    assert task.task_id == "t1"
    assert task.state == TaskState.CREATED
    assert task.created_at == task.updated_at
    assert "t1" in registry
    assert registry.get("t1") is task


def test_register_with_metadata() -> None:
    rid = uuid.uuid4()
    registry = TaskRegistry()
    task = registry.register(
        "t1",
        metadata=TaskMetadata(
            coroutine_name="worker",
            task_name="t1-name",
            asyncio_task_id=12345,
            runtime_id=rid,
            tags={"env": "test"},
            extra={"trace_id": "abc"},
        ),
    )
    assert task.coroutine_name == "worker"
    assert task.task_name == "t1-name"
    assert task.asyncio_task_id == 12345
    assert task.runtime_id == rid
    assert task.tags == {"env": "test"}
    assert task.metadata == {"trace_id": "abc"}
    assert registry.get_by_asyncio_id(12345) is task


def test_duplicate_register_raises() -> None:
    registry = TaskRegistry()
    registry.register("t1")
    with pytest.raises(DuplicateTaskError):
        registry.register("t1")


def test_register_with_unknown_parent_raises() -> None:
    registry = TaskRegistry()
    with pytest.raises(InvalidParentReferenceError):
        registry.register("t1", metadata=TaskMetadata(parent_task_id="ghost"))


def test_register_with_known_parent_links_children() -> None:
    registry = TaskRegistry()
    registry.register("parent")
    registry.register("c1", metadata=TaskMetadata(parent_task_id="parent"))
    registry.register("c2", metadata=TaskMetadata(parent_task_id="parent"))

    children = sorted(t.task_id for t in registry.children_of("parent"))
    assert children == ["c1", "c2"]


# ── transitions ─────────────────────────────────────────────────────────────


def test_state_transitions_update_indexes() -> None:
    registry = TaskRegistry()
    registry.register("t1")
    assert {t.task_id for t in registry.list(state=TaskState.CREATED)} == {"t1"}

    registry.update_state("t1", TaskState.RUNNING)
    assert {t.task_id for t in registry.list(state=TaskState.CREATED)} == set()
    assert {t.task_id for t in registry.list(state=TaskState.RUNNING)} == {"t1"}

    registry.update_state("t1", TaskState.COMPLETED, duration_seconds=0.5)
    task = registry.get("t1")
    assert task is not None
    assert task.state == TaskState.COMPLETED
    assert task.duration_seconds == 0.5
    assert task.completed_at is not None


def test_invalid_state_transition_raises() -> None:
    registry = TaskRegistry()
    registry.register("t1")
    registry.update_state("t1", TaskState.COMPLETED)
    with pytest.raises(InvalidStateTransitionError):
        registry.update_state("t1", TaskState.RUNNING)


def test_update_unknown_task_raises() -> None:
    registry = TaskRegistry()
    with pytest.raises(UnknownTaskError):
        registry.update_state("ghost", TaskState.RUNNING)


def test_failed_transition_captures_exception_details() -> None:
    registry = TaskRegistry()
    registry.register("t1")
    registry.update_state("t1", TaskState.RUNNING)
    registry.update_state(
        "t1",
        TaskState.FAILED,
        exception_type="RuntimeError",
        exception_message="boom",
        duration_seconds=0.25,
    )
    task = registry.get("t1")
    assert task is not None
    assert task.exception_type == "RuntimeError"
    assert task.exception_message == "boom"
    assert task.duration_seconds == 0.25


# ── lookup / indexing ───────────────────────────────────────────────────────


def test_list_filters_by_state_and_parent() -> None:
    registry = TaskRegistry()
    registry.register("parent")
    registry.register("c1", metadata=TaskMetadata(parent_task_id="parent"))
    registry.register("c2", metadata=TaskMetadata(parent_task_id="parent"))
    registry.update_state("c1", TaskState.RUNNING)

    only_running = registry.list(state=TaskState.RUNNING)
    assert [t.task_id for t in only_running] == ["c1"]

    parent_children = registry.list(parent_task_id="parent")
    assert {t.task_id for t in parent_children} == {"c1", "c2"}

    parentless = registry.list(parent_task_id=None)
    assert {t.task_id for t in parentless} == {"parent"}


def test_remove_deletes_from_all_indexes() -> None:
    registry = TaskRegistry()
    registry.register("t1", metadata=TaskMetadata(asyncio_task_id=42, parent_task_id=None))
    assert registry.remove("t1") is True
    assert registry.get("t1") is None
    assert registry.get_by_asyncio_id(42) is None
    assert registry.list() == []
    assert registry.remove("t1") is False


def test_clear_resets_metrics_and_index() -> None:
    registry = TaskRegistry()
    registry.register("t1")
    registry.register("t2")
    registry.clear()
    assert len(registry) == 0
    snap = registry.metrics_snapshot()
    assert snap.total_tasks == 0
    assert snap.active_tasks == 0


# ── snapshots ───────────────────────────────────────────────────────────────


def test_snapshot_active_excludes_terminal_states() -> None:
    registry = TaskRegistry()
    registry.register("active1")
    registry.register("active2")
    registry.register("done")
    registry.update_state("done", TaskState.COMPLETED)

    active = registry.snapshot_active_tasks()
    assert {s.task_id for s in active} == {"active1", "active2"}
    assert all(isinstance(s, TaskSnapshot) for s in active)


def test_snapshot_all_returns_deterministic_order() -> None:
    registry = TaskRegistry()
    for tid in ("c", "a", "b"):
        registry.register(tid)

    snap = registry.snapshot_all_tasks()
    # Sort key is (created_at, task_id). Unique created_at per call means the
    # order matches registration order — a stable, replay-friendly contract.
    assert [s.task_id for s in snap] == ["c", "a", "b"]


def test_snapshot_ordering_breaks_ties_by_task_id() -> None:
    registry = TaskRegistry()
    registry.register("c")
    registry.register("a")
    registry.register("b")
    # Force identical created_at to exercise the task_id tiebreaker.
    for task_id in ("a", "b", "c"):
        registry.get(task_id).created_at = 100.0  # type: ignore[union-attr]

    snap = registry.snapshot_all_tasks()
    assert [s.task_id for s in snap] == ["a", "b", "c"]


def test_snapshot_task_returns_immutable_view() -> None:
    registry = TaskRegistry()
    registry.register("t1")
    snap = registry.snapshot_task("t1")
    assert snap is not None
    assert isinstance(snap, TaskSnapshot)
    with pytest.raises(Exception):  # noqa: B017 — pydantic ValidationError
        snap.task_id = "tampered"  # type: ignore[misc]


def test_snapshot_task_is_json_safe() -> None:
    import json

    registry = TaskRegistry()
    registry.register(
        "t1",
        metadata=TaskMetadata(
            runtime_id=uuid.uuid4(),
            tags={"env": "dev"},
            extra={"trace": "x"},
        ),
    )
    snap = registry.snapshot_task("t1")
    assert snap is not None
    payload = snap.model_dump(mode="json")
    json.dumps(payload)  # should not raise


# ── metrics ─────────────────────────────────────────────────────────────────


def test_metrics_count_lifecycle() -> None:
    registry = TaskRegistry()
    registry.register("t1")
    registry.register("t2")
    registry.register("t3")
    registry.update_state("t2", TaskState.RUNNING)
    registry.update_state("t2", TaskState.COMPLETED)
    registry.update_state("t3", TaskState.RUNNING)
    registry.update_state("t3", TaskState.FAILED)

    snap = registry.metrics_snapshot()
    assert snap.total_tasks == 3
    assert snap.completed_tasks == 1
    assert snap.failed_tasks == 1
    assert snap.cancelled_tasks == 0
    assert snap.active_tasks == 1  # only "t1" still in CREATED


def test_remove_updates_metrics() -> None:
    registry = TaskRegistry()
    registry.register("t1")
    registry.update_state("t1", TaskState.RUNNING)
    registry.update_state("t1", TaskState.COMPLETED)
    registry.remove("t1")
    snap = registry.metrics_snapshot()
    assert snap.total_tasks == 0
    assert snap.completed_tasks == 0


# ── event bus extension point ───────────────────────────────────────────────


def test_handle_event_drives_lifecycle() -> None:
    from asyncviz.runtime.events.models import (
        TaskCompletedEvent,
        TaskCreatedEvent,
        TaskFailedEvent,
        TaskStartedEvent,
    )

    registry = TaskRegistry()
    registry.handle_event(TaskCreatedEvent(task_id="t1", coroutine_name="worker"))
    registry.handle_event(TaskStartedEvent(task_id="t1"))
    registry.handle_event(TaskCompletedEvent(task_id="t1", duration_seconds=0.5))

    task = registry.get("t1")
    assert task is not None
    assert task.state == TaskState.COMPLETED
    assert task.coroutine_name == "worker"
    assert task.duration_seconds == 0.5

    # Unknown task and bad transitions are tolerated (logged at debug).
    registry.handle_event(TaskStartedEvent(task_id="ghost"))
    registry.handle_event(TaskFailedEvent(task_id="t1"))  # already terminal


def test_handle_event_is_idempotent_for_created() -> None:
    from asyncviz.runtime.events.models import TaskCreatedEvent

    registry = TaskRegistry()
    registry.handle_event(TaskCreatedEvent(task_id="t1"))
    registry.handle_event(TaskCreatedEvent(task_id="t1"))
    assert len(registry) == 1


def test_handle_event_drops_unresolved_parent() -> None:
    from asyncviz.runtime.events.models import TaskCreatedEvent

    registry = TaskRegistry()
    registry.handle_event(TaskCreatedEvent(task_id="t1", parent_task_id="ghost"))
    task = registry.get("t1")
    assert task is not None
    assert task.parent_task_id is None


# ── concurrency ─────────────────────────────────────────────────────────────


def test_concurrent_registration_is_safe() -> None:
    registry = TaskRegistry()
    errors: list[Exception] = []

    def worker(start: int) -> None:
        try:
            for i in range(start, start + 50):
                registry.register(f"t{i}")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i * 50,), daemon=True) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    snap = registry.metrics_snapshot()
    assert snap.total_tasks == 200
    assert snap.active_tasks == 200  # all still CREATED


def test_concurrent_transitions_are_safe() -> None:
    registry = TaskRegistry()
    for i in range(200):
        registry.register(f"t{i}")

    def runner(start: int) -> None:
        for i in range(start, start + 50):
            registry.update_state(f"t{i}", TaskState.RUNNING)
            registry.update_state(f"t{i}", TaskState.COMPLETED)

    threads = [threading.Thread(target=runner, args=(i * 50,), daemon=True) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    snap = registry.metrics_snapshot()
    assert snap.completed_tasks == 200
    assert snap.active_tasks == 0
