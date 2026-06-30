"""Topology, replay-cache, websocket-buffer tests."""

from __future__ import annotations

from asyncviz.runtime.memory import (
    CompactTopology,
    EventMemoryOptimizer,
    MemoryOptimizerConfig,
    ReplayFrameCache,
    StringInterner,
    WebsocketBufferPool,
)
from asyncviz.runtime.memory.models.compact_frame import CompactReplayFrame


def test_topology_add_and_query() -> None:
    interner = StringInterner(capacity=16)
    topo = CompactTopology(capacity=8, interner=interner)
    topo.add_edge("a", "b")
    topo.add_edge("a", "c")
    assert topo.neighbors("a") == frozenset({"b", "c"})
    assert "a" in topo


def test_topology_eviction_when_full() -> None:
    interner = StringInterner(capacity=64)
    topo = CompactTopology(capacity=2, interner=interner)
    topo.add_edge("a", "b")
    topo.add_edge("c", "d")
    stats = topo.stats()
    assert stats.evictions >= 1
    assert stats.node_count == 2


def test_topology_interns_node_ids() -> None:
    interner = StringInterner(capacity=16)
    topo = CompactTopology(capacity=16, interner=interner)
    topo.add_edge("source", "target")
    topo.add_edge("source", "another")
    # After two adds, source appears once in the dict.
    assert "source" in topo
    # The interner should hold the canonical instances.
    assert interner.stats().size >= 2


def test_replay_frame_cache_lru() -> None:
    cache = ReplayFrameCache(capacity=2)
    f1 = CompactReplayFrame(
        schema_version=1,
        frame_type="runtime_event",
        sequence=1,
        monotonic_ns=1,
        payload_type="x",
        payload={},
    )
    f2 = CompactReplayFrame(
        schema_version=1,
        frame_type="runtime_event",
        sequence=2,
        monotonic_ns=2,
        payload_type="x",
        payload={},
    )
    f3 = CompactReplayFrame(
        schema_version=1,
        frame_type="runtime_event",
        sequence=3,
        monotonic_ns=3,
        payload_type="x",
        payload={},
    )
    cache.put(f1)
    cache.put(f2)
    cache.put(f3)
    assert cache.get(1) is None  # evicted
    assert cache.get(2) is not None
    assert cache.get(3) is not None


def test_replay_frame_cache_hit_metric() -> None:
    from asyncviz.runtime.memory import get_memory_metrics_snapshot

    cache = ReplayFrameCache(capacity=2)
    cache.put(
        CompactReplayFrame(
            schema_version=1,
            frame_type="runtime_event",
            sequence=1,
            monotonic_ns=1,
            payload_type="x",
            payload={},
        ),
    )
    before = get_memory_metrics_snapshot()
    cache.get(1)
    cache.get(99)
    after = get_memory_metrics_snapshot()
    assert after.replay_cache_hits - before.replay_cache_hits == 1
    assert after.replay_cache_misses - before.replay_cache_misses == 1


def test_websocket_buffer_pool_reuses() -> None:
    pool = WebsocketBufferPool(capacity_buffers=2, default_bytes=1024)
    b1 = pool.acquire()
    b1.extend(b"hello")
    pool.release(b1)
    b2 = pool.acquire()
    # Released buffer reused; contents cleared.
    assert len(b2) == 0


def test_websocket_buffer_pool_grows_when_needed() -> None:
    pool = WebsocketBufferPool(capacity_buffers=1, default_bytes=512)
    b1 = pool.acquire()
    pool.release(b1)
    # Request a larger buffer — pool should grow the reused bytearray.
    pool.acquire(min_bytes=2048)
    assert pool.stats().grow_events >= 1


def test_optimizer_websocket_buffer_context_manager() -> None:
    opt = EventMemoryOptimizer(config=MemoryOptimizerConfig())
    with opt.websocket_buffer() as buf:
        buf.extend(b"hi")
    # After release, the buffer should be back in the pool.
    stats = opt.websocket_buffers.stats()
    assert stats.in_pool >= 1
