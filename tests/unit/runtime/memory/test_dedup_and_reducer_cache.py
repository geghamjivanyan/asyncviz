"""Deduplicator + reducer-cache tests."""

from __future__ import annotations

from asyncviz.runtime.memory import (
    BoundedReducerCache,
    EventDeduplicator,
    EventMemoryOptimizer,
    ProjectionReusePool,
    get_or_compute,
)
from asyncviz.runtime.memory.models.compact_event import CompactEvent


def _event(sequence: int, payload: dict | None = None) -> CompactEvent:
    return CompactEvent(
        event_type="asyncio.task.created",
        event_id=f"id-{sequence}",
        monotonic_ns=sequence * 10,
        category="task",
        payload=payload or {"task_id": f"t-{sequence}"},
    )


def test_deduplicator_detects_repeats() -> None:
    dedup = EventDeduplicator(window_size=8)
    e = _event(1)
    d1 = dedup.observe(e)
    d2 = dedup.observe(e)
    assert not d1.duplicate
    assert d2.duplicate


def test_deduplicator_window_eviction() -> None:
    dedup = EventDeduplicator(window_size=2)
    dedup.observe(_event(1))
    dedup.observe(_event(2))
    dedup.observe(_event(3))
    # Window evicted seq=1's digest.
    assert not dedup.observe(_event(1)).duplicate


def test_optimizer_observe_event_returns_dedup_decision(
    optimizer: EventMemoryOptimizer,
) -> None:
    e = _event(1)
    d1 = optimizer.observe_event(e)
    d2 = optimizer.observe_event(e)
    assert not d1.duplicate
    assert d2.duplicate


def test_bounded_reducer_cache_lru_eviction() -> None:
    cache: BoundedReducerCache[str, int] = BoundedReducerCache("test", capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.get("a") is None  # evicted
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_get_or_compute_caches() -> None:
    cache: BoundedReducerCache[str, int] = BoundedReducerCache("test", capacity=4)
    calls = [0]

    def factory() -> int:
        calls[0] += 1
        return 42

    v1 = get_or_compute(cache, "k", factory)
    v2 = get_or_compute(cache, "k", factory)
    assert v1 == 42 and v2 == 42
    assert calls[0] == 1


def test_projection_reuse_returns_same_instance_for_equal_payloads() -> None:
    pool: ProjectionReusePool[str] = ProjectionReusePool()
    a = pool.reuse_or_store("k", {"x": 1, "y": 2})
    b = pool.reuse_or_store("k", {"x": 1, "y": 2})
    assert a is b


def test_projection_reuse_replaces_on_change() -> None:
    pool: ProjectionReusePool[str] = ProjectionReusePool()
    pool.reuse_or_store("k", {"x": 1})
    second = pool.reuse_or_store("k", {"x": 2})
    third = pool.reuse_or_store("k", {"x": 2})
    assert second is third
