"""Event + frame compaction tests."""

from __future__ import annotations

from asyncviz.replay.format import make_runtime_event_frame
from asyncviz.runtime.events.models import TaskCreatedEvent
from asyncviz.runtime.memory import (
    EventMemoryOptimizer,
    categorize_event_type,
    compact_event,
    compact_frame,
    get_global_interner,
)


def test_categorize_event_type_for_known_prefixes() -> None:
    assert categorize_event_type("asyncio.task.created") == "task"
    assert categorize_event_type("asyncio.queue.put") == "queue"
    assert categorize_event_type("asyncio.semaphore.acquired") == "semaphore"
    assert categorize_event_type("asyncio.gather.completed") == "gather"
    assert categorize_event_type("asyncio.executor.work.started") == "executor"
    assert categorize_event_type("runtime.started") == "runtime"
    assert categorize_event_type("runtime.metric") == "metric"
    assert categorize_event_type("runtime.warning") == "warning"
    assert categorize_event_type("something.else") == "other"


def test_compact_event_intern_consistency() -> None:
    interner = get_global_interner()
    ev1 = TaskCreatedEvent(task_id="a", task_name="x")
    ev2 = TaskCreatedEvent(task_id="b", task_name="y")
    c1 = compact_event(ev1, interner=interner)
    c2 = compact_event(ev2, interner=interner)
    # Same event_type → interned to same instance.
    assert c1.event_type is c2.event_type
    assert c1.category == "task"


def test_compact_event_interns_payload_keys(optimizer: EventMemoryOptimizer) -> None:
    ev1 = TaskCreatedEvent(task_id="t-1", task_name="a")
    ev2 = TaskCreatedEvent(task_id="t-2", task_name="b")
    c1 = optimizer.compact_event(ev1)
    c2 = optimizer.compact_event(ev2)
    # Both payloads share the same interned keys.
    common_keys = set(c1.payload.keys()) & set(c2.payload.keys())
    assert common_keys  # baseline: payloads should share at least one key
    for key in common_keys:
        # Look up the key in both dicts — assert they're the same string.
        k1 = next(k for k in c1.payload if k == key)
        k2 = next(k for k in c2.payload if k == key)
        assert k1 is k2


def test_compact_event_strips_envelope_fields(
    optimizer: EventMemoryOptimizer,
) -> None:
    ev = TaskCreatedEvent(task_id="t-1", task_name="hello")
    compact = optimizer.compact_event(ev)
    # event_type lives on the envelope, not in the payload.
    assert "event_type" not in compact.payload
    assert "event_id" not in compact.payload
    assert "monotonic_ns" not in compact.payload


def test_compact_replay_frame_interns_types(optimizer: EventMemoryOptimizer) -> None:
    ev = TaskCreatedEvent(task_id="t-1", task_name="hello")
    f1 = make_runtime_event_frame(sequence=1, monotonic_ns=10, event=ev)
    f2 = make_runtime_event_frame(sequence=2, monotonic_ns=20, event=ev)
    c1 = optimizer.compact_replay_frame(f1)
    c2 = optimizer.compact_replay_frame(f2)
    assert c1.payload_type is c2.payload_type
    assert c1.frame_type is c2.frame_type


def test_compact_dict_event_handles_raw_dict(
    optimizer: EventMemoryOptimizer,
) -> None:
    data = {
        "event_type": "asyncio.task.created",
        "event_id": "id-1",
        "monotonic_ns": 1234,
        "task_id": "t-1",
        "task_name": "x",
    }
    compact = optimizer.compact_dict_event(data)
    assert compact.event_type == "asyncio.task.created"
    assert compact.payload["task_id"] == "t-1"


def test_compact_replay_frame_cache_round_trip(
    optimizer: EventMemoryOptimizer,
) -> None:
    ev = TaskCreatedEvent(task_id="t-1", task_name="hello")
    frame = make_runtime_event_frame(sequence=5, monotonic_ns=50, event=ev)
    optimizer.compact_replay_frame(frame, cache=True)
    cached = optimizer.replay_cache.get(5)
    assert cached is not None
    assert cached.sequence == 5


def test_compact_frame_module_function_increments_metrics(
    optimizer: EventMemoryOptimizer,
) -> None:
    ev = TaskCreatedEvent(task_id="t-1", task_name="hello")
    frame = make_runtime_event_frame(sequence=1, monotonic_ns=1, event=ev)
    compact_frame(frame, interner=optimizer.interner)
    from asyncviz.runtime.memory import get_memory_metrics_snapshot

    assert get_memory_metrics_snapshot().compact_frames_built >= 1
