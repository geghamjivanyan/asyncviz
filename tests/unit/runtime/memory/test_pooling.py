"""Object-pool tests."""

from __future__ import annotations

import pytest

from asyncviz.runtime.memory import (
    ObjectPool,
    PoolReleaseError,
)


def _factory() -> bytearray:
    return bytearray()


def test_acquire_returns_fresh_when_empty() -> None:
    pool: ObjectPool[bytearray] = ObjectPool(_factory, capacity=2)
    token = pool.acquire()
    assert isinstance(token.obj, bytearray)
    stats = pool.stats()
    assert stats.acquires == 1
    assert stats.pool_misses == 1


def test_release_returns_object_for_reuse() -> None:
    pool: ObjectPool[bytearray] = ObjectPool(_factory, capacity=2)
    t1 = pool.acquire()
    t1.release()
    t2 = pool.acquire()
    # Same identity after release/acquire round-trip.
    assert id(t2.obj) == id(t1.obj)
    stats = pool.stats()
    assert stats.pool_hits == 1


def test_reset_runs_on_release() -> None:
    cleared: list[bytearray] = []

    def reset(buf: bytearray) -> None:
        cleared.append(buf)

    pool: ObjectPool[bytearray] = ObjectPool(_factory, capacity=2, reset=reset)
    token = pool.acquire()
    token.obj.extend(b"hello")
    token.release()
    assert cleared == [token.obj]


def test_double_release_raises_strict() -> None:
    pool: ObjectPool[bytearray] = ObjectPool(_factory, capacity=2, strict=True)
    token = pool.acquire()
    token.release()
    with pytest.raises(PoolReleaseError):
        token.release()


def test_double_release_lenient_swallows() -> None:
    pool: ObjectPool[bytearray] = ObjectPool(_factory, capacity=2, strict=False)
    token = pool.acquire()
    token.release()
    token.release()  # no raise


def test_context_manager_releases_automatically() -> None:
    pool: ObjectPool[bytearray] = ObjectPool(_factory, capacity=2)
    token = pool.acquire()
    with token as obj:
        obj.extend(b"data")
    # Token released — re-acquiring gives us the same instance.
    t2 = pool.acquire()
    assert t2.obj is token.obj


def test_capacity_drops_overflow() -> None:
    pool: ObjectPool[bytearray] = ObjectPool(_factory, capacity=1)
    t1 = pool.acquire()
    t2 = pool.acquire()
    t1.release()
    t2.release()  # capacity is 1; this object goes to GC, not the pool
    stats = pool.stats()
    assert stats.size == 1  # only one back in pool
