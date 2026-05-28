"""Seek-cache LRU tests."""

from __future__ import annotations

from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.seek import SeekCache, SeekCacheEntry


def _entry(seq: int) -> SeekCacheEntry:
    return SeekCacheEntry(
        sequence=seq,
        monotonic_ns=seq * 10,
        state=VirtualRuntimeState(last_sequence=seq, last_monotonic_ns=seq * 10),
    )


def test_cache_put_and_get() -> None:
    cache = SeekCache(capacity=4)
    cache.put(_entry(5))
    out = cache.get(5)
    assert out is not None
    assert out.sequence == 5


def test_cache_miss_returns_none_and_counts() -> None:
    cache = SeekCache(capacity=4)
    assert cache.get(99) is None
    stats = cache.stats()
    assert stats.misses == 1
    assert stats.hits == 0


def test_cache_lru_eviction() -> None:
    cache = SeekCache(capacity=2)
    cache.put(_entry(1))
    cache.put(_entry(2))
    cache.put(_entry(3))
    assert cache.get(1) is None  # evicted
    assert cache.get(2) is not None
    assert cache.get(3) is not None
    stats = cache.stats()
    assert stats.evictions == 1


def test_cache_move_to_end_on_access() -> None:
    cache = SeekCache(capacity=2)
    cache.put(_entry(1))
    cache.put(_entry(2))
    cache.get(1)  # marks 1 as recently used
    cache.put(_entry(3))  # would evict LRU
    assert cache.get(1) is not None  # still here — 2 was evicted instead
    assert cache.get(2) is None


def test_cache_invalidate() -> None:
    cache = SeekCache(capacity=2)
    cache.put(_entry(1))
    cache.invalidate(1)
    assert cache.get(1) is None


def test_cache_with_zero_capacity_is_disabled() -> None:
    cache = SeekCache(capacity=0)
    cache.put(_entry(1))
    assert cache.get(1) is None
    assert cache.size == 0
