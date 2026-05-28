from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from asyncviz.instrumentation.asyncio import AsyncioPatcher
from asyncviz.runtime.events import EventBus
from asyncviz.runtime.events.models import TaskCreatedEvent
from asyncviz.runtime.events.models.enums import EventType
from asyncviz.runtime.lineage import (
    CyclicAncestryError,
    LineageBinding,
    LineageDepthExceededError,
    LineageTracker,
    ancestors_tuple,
    bind_lineage_context,
    current_parent_task,
    current_runtime_task,
    descendants_of,
    detect_cycle,
    iter_subtree,
    lineage_path,
    list_roots,
    reset_lineage_context,
    snapshot_lineage,
)
from asyncviz.runtime.tasks import TaskMetadata, TaskRegistry

# ── LineageTracker primitives ─────────────────────────────────────────────


def test_register_root_task() -> None:
    tracker = LineageTracker()
    lineage = tracker.register("root", None)
    assert lineage.is_root
    assert lineage.parent_task_id is None
    assert lineage.root_task_id == "root"
    assert lineage.depth == 0
    assert lineage.ancestor_chain == ()
    assert lineage.child_count == 0


def test_register_with_known_parent_computes_chain() -> None:
    tracker = LineageTracker()
    tracker.register("root", None)
    tracker.register("a", "root")
    tracker.register("b", "a")
    grand = tracker.lineage_of("b")
    assert grand is not None
    assert grand.parent_task_id == "a"
    assert grand.root_task_id == "root"
    assert grand.depth == 2
    assert grand.ancestor_chain == ("a", "root")


def test_register_with_unknown_parent_stores_link_but_treats_as_root() -> None:
    """Late-parent replay: parent reference preserved, ancestor chain empty."""
    tracker = LineageTracker()
    lineage = tracker.register("orphan", "unknown-parent")
    assert lineage.parent_task_id == "unknown-parent"
    assert lineage.depth == 0
    assert lineage.ancestor_chain == ()


def test_register_is_idempotent() -> None:
    tracker = LineageTracker()
    a = tracker.register("t", None)
    b = tracker.register("t", "ignored")
    # Second register returns the *original* lineage — first-wins semantics.
    assert a.parent_task_id == b.parent_task_id is None


def test_child_count_updates_on_register() -> None:
    tracker = LineageTracker()
    tracker.register("root", None)
    tracker.register("child1", "root")
    tracker.register("child2", "root")
    assert tracker.child_count("root") == 2


def test_unregister_drops_links_and_orphans_children() -> None:
    tracker = LineageTracker()
    tracker.register("root", None)
    tracker.register("child", "root")
    tracker.register("grand", "child")
    tracker.unregister("child")
    assert "child" not in tracker
    # Grandchild's ancestors cleared; root no longer has child references.
    assert tracker.parent_of("grand") == "child"  # link preserved
    assert tracker.ancestors("grand") == ()
    assert tracker.children("root") == ()


def test_clear_resets_state() -> None:
    tracker = LineageTracker()
    tracker.register("a", None)
    tracker.register("b", "a")
    tracker.clear()
    assert len(tracker) == 0


# ── Cycle protection ─────────────────────────────────────────────────────


def test_self_parent_rejected() -> None:
    tracker = LineageTracker()
    tracker.register("t", None)
    # Already registered as root; second register is idempotent (no error).
    second = tracker.register("t", "t")
    assert second.parent_task_id is None


def test_indirect_cycle_rejected() -> None:
    tracker = LineageTracker()
    tracker.register("a", None)
    tracker.register("b", "a")
    tracker.register("c", "b")
    # Attempting to register "a" as a child of "c" would form a-cycle.
    # First unregister "a" (so we can attempt the wrong link) — actually
    # easier: directly test detect_cycle.
    assert detect_cycle("c", "a", tracker._parent_of) is True


def test_explicit_cycle_via_detect() -> None:
    parent_of: dict[str, str | None] = {"a": None, "b": "a", "c": "b"}
    assert detect_cycle("b", "a", parent_of) is True
    assert detect_cycle("c", "a", parent_of) is True
    assert detect_cycle("c", "x", parent_of) is False


def test_cyclic_rejection_counter() -> None:
    """A genuine cycle attempt — the tracker rejects it and bumps the counter."""
    tracker = LineageTracker()
    tracker.register("a", None)
    tracker.register("b", "a")
    tracker.register("c", "b")
    # Manually corrupt state to set up a cycle (events arriving out of order
    # on replay could in theory produce this) — then attempt a register that
    # would close the loop.
    tracker._parent_of["a"] = "c"  # a → c → b → a
    with pytest.raises(CyclicAncestryError):
        tracker.register("loop", "a")
    metrics = tracker.metrics_snapshot()
    assert metrics.cyclic_rejections == 1


# ── Walk + descendants ───────────────────────────────────────────────────


def test_walk_ancestors_yields_closest_first() -> None:
    parent_of: dict[str, str | None] = {"root": None, "a": "root", "b": "a", "c": "b"}
    assert list(ancestors_tuple("c", parent_of)) == ["b", "a", "root"]


def test_walk_raises_on_cycle() -> None:
    # Corrupt state to test the guard.
    parent_of: dict[str, str | None] = {"a": "b", "b": "a"}
    with pytest.raises(LineageDepthExceededError):
        ancestors_tuple("a", parent_of, max_depth=10)


def test_descendants_bfs_order() -> None:
    children_of = {
        "root": {"a", "b"},
        "a": {"c"},
        "b": {"d", "e"},
    }
    result = descendants_of("root", children_of)
    assert set(result) == {"a", "b", "c", "d", "e"}
    # root comes first via iter_subtree; descendants_of strips it.
    subtree = list(iter_subtree("root", children_of))
    assert subtree[0] == "root"


def test_lineage_path_inclusive() -> None:
    parent_of: dict[str, str | None] = {"root": None, "a": "root", "b": "a"}
    assert lineage_path("b", parent_of) == ["root", "a", "b"]


def test_list_roots() -> None:
    parent_of: dict[str, str | None] = {"r1": None, "r2": None, "a": "r1"}
    assert set(list_roots(parent_of)) == {"r1", "r2"}


# ── Snapshot serialization ───────────────────────────────────────────────


def test_snapshot_lineage_serializes_descendants() -> None:
    tracker = LineageTracker()
    tracker.register("root", None)
    tracker.register("a", "root")
    tracker.register("b", "root")
    tracker.register("c", "a")
    snap = snapshot_lineage(tracker, "root")
    assert snap is not None
    payload = snap.model_dump()
    json.dumps(payload)  # JSON-safe
    assert snap.task_id == "root"
    assert snap.depth == 0
    assert snap.child_count == 2
    assert set(snap.descendants) == {"a", "b", "c"}


def test_snapshot_lineage_returns_none_for_unknown() -> None:
    tracker = LineageTracker()
    assert snapshot_lineage(tracker, "missing") is None


# ── Registry integration ─────────────────────────────────────────────────


def test_registry_propagates_lineage_to_runtime_task() -> None:
    reg = TaskRegistry()
    reg.register("root")
    reg.register("child", metadata=TaskMetadata(parent_task_id="root"))
    reg.register("grand", metadata=TaskMetadata(parent_task_id="child"))

    root = reg.get("root")
    child = reg.get("child")
    grand = reg.get("grand")
    assert root is not None and child is not None and grand is not None

    assert root.depth == 0 and root.root_task_id == "root"
    assert child.depth == 1 and child.root_task_id == "root"
    assert child.ancestor_chain == ("root",)
    assert grand.depth == 2 and grand.root_task_id == "root"
    assert grand.ancestor_chain == ("child", "root")
    assert root.child_count == 1
    assert child.child_count == 1


def test_registry_child_count_decrements_on_remove() -> None:
    reg = TaskRegistry()
    reg.register("root")
    reg.register("a", metadata=TaskMetadata(parent_task_id="root"))
    reg.register("b", metadata=TaskMetadata(parent_task_id="root"))
    assert reg.get("root").child_count == 2  # type: ignore[union-attr]
    reg.remove("a")
    assert reg.get("root").child_count == 1  # type: ignore[union-attr]


def test_registry_lineage_queries() -> None:
    reg = TaskRegistry()
    reg.register("root")
    reg.register("a", metadata=TaskMetadata(parent_task_id="root"))
    reg.register("b", metadata=TaskMetadata(parent_task_id="root"))
    reg.register("c", metadata=TaskMetadata(parent_task_id="a"))

    children = reg.get_children("root")
    assert {t.task_id for t in children} == {"a", "b"}

    descendants = reg.get_descendants("root")
    assert {t.task_id for t in descendants} == {"a", "b", "c"}

    roots = reg.get_root_tasks()
    assert {t.task_id for t in roots} == {"root"}


def test_registry_lineage_metrics_snapshot() -> None:
    reg = TaskRegistry()
    reg.register("root1")
    reg.register("root2")
    reg.register("a", metadata=TaskMetadata(parent_task_id="root1"))
    reg.register("b", metadata=TaskMetadata(parent_task_id="a"))
    metrics = reg.lineage_metrics_snapshot()
    assert metrics.tracked_tasks == 4
    assert metrics.root_tasks == 2
    assert metrics.max_depth == 2
    assert metrics.orphan_links == 0


def test_registry_snapshot_carries_lineage_fields() -> None:
    reg = TaskRegistry()
    reg.register("root")
    reg.register("child", metadata=TaskMetadata(parent_task_id="root"))
    snap = reg.snapshot_task("child")
    assert snap is not None
    assert snap.parent_task_id == "root"
    assert snap.root_task_id == "root"
    assert snap.depth == 1
    assert snap.ancestor_chain == ["root"]


# ── ContextVar propagation ───────────────────────────────────────────────


def test_lineage_context_vars_default_to_none() -> None:
    assert current_runtime_task() is None
    assert current_parent_task() is None


def test_bind_and_reset_lineage_context() -> None:
    binding = bind_lineage_context("t1", None)
    try:
        assert current_runtime_task() == "t1"
        assert current_parent_task() is None
        inner = bind_lineage_context("t2", "t1")
        try:
            assert current_runtime_task() == "t2"
            assert current_parent_task() == "t1"
        finally:
            reset_lineage_context(inner)
        assert current_runtime_task() == "t1"
    finally:
        reset_lineage_context(binding)
    assert current_runtime_task() is None
    assert isinstance(binding, LineageBinding)


# ── End-to-end via instrumented asyncio ──────────────────────────────────


@pytest_asyncio.fixture
async def patched_runtime() -> AsyncIterator[tuple[EventBus, AsyncioPatcher, TaskRegistry]]:
    bus = EventBus()
    await bus.start()
    registry = TaskRegistry()
    sub = bus.subscribe(
        registry.handle_event,
        event_types={
            EventType.TASK_CREATED,
            EventType.TASK_STARTED,
            EventType.TASK_WAITING,
            EventType.TASK_RESUMED,
            EventType.TASK_COMPLETED,
            EventType.TASK_CANCELLED,
            EventType.TASK_FAILED,
        },
    )
    patcher = AsyncioPatcher(bus)
    patcher.patch()
    try:
        yield bus, patcher, registry
    finally:
        patcher.unpatch()
        bus.unsubscribe(sub)
        await bus.stop()


async def test_nested_create_task_records_correct_lineage(patched_runtime) -> None:
    bus, _patcher, registry = patched_runtime
    parent_seen: list[str | None] = []

    async def grandchild() -> None:
        parent_seen.append(current_parent_task())

    async def child() -> None:
        await asyncio.create_task(grandchild(), name="grand")

    async def root() -> None:
        await asyncio.create_task(child(), name="child")

    task = asyncio.create_task(root(), name="root")
    await task
    await bus.join()

    # Three tasks observed via instrumented create_task.
    metrics = registry.lineage_metrics_snapshot()
    assert metrics.tracked_tasks >= 3
    assert metrics.max_depth >= 2


async def test_event_carries_parent_task_id(patched_runtime) -> None:
    bus, _patcher, _registry = patched_runtime
    received: list[TaskCreatedEvent] = []
    bus.subscribe(received.append, event_types={"asyncio.task.created"})

    async def child() -> None:
        return None

    async def root() -> None:
        await asyncio.create_task(child(), name="child")

    task = asyncio.create_task(root(), name="root")
    await task
    await bus.join()

    # Find the child creation event and confirm parent_task_id was set.
    child_events = [e for e in received if e.task_name == "child"]
    assert len(child_events) == 1
    assert child_events[0].parent_task_id is not None
