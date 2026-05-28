"""Registry behaviour: classification, weakref pruning, id stability."""

from __future__ import annotations

import asyncio
import gc

import pytest

from asyncviz.instrumentation.queue import QueueRegistry, classify_queue


def test_classify_distinguishes_stdlib_leaves() -> None:
    assert classify_queue(asyncio.Queue()) == "Queue"
    assert classify_queue(asyncio.LifoQueue()) == "LifoQueue"
    assert classify_queue(asyncio.PriorityQueue()) == "PriorityQueue"


def test_classify_marks_user_subclasses() -> None:
    class MyQ(asyncio.Queue):
        pass

    assert classify_queue(MyQ()) == "subclass"


def test_classify_returns_unknown_for_non_queue() -> None:
    assert classify_queue(object()) == "unknown"


def test_register_is_idempotent() -> None:
    r = QueueRegistry()
    q = asyncio.Queue()
    a = r.register(q, creator_task_id=None)
    b = r.register(q, creator_task_id=None)
    assert a.queue_id == b.queue_id
    assert len(r) == 1


def test_register_returns_kind_and_maxsize() -> None:
    r = QueueRegistry()
    q = asyncio.Queue(maxsize=11)
    identity = r.register(q, creator_task_id="t-7", name="orders")
    assert identity.queue_kind == "Queue"
    assert identity.maxsize == 11
    assert identity.creator_task_id == "t-7"
    assert identity.name == "orders"


def test_weakref_finalizer_prunes_dropped_queue() -> None:
    r = QueueRegistry()
    q = asyncio.Queue()
    identity = r.register(q, creator_task_id=None)
    assert len(r) == 1
    qid = identity.queue_id
    del q
    gc.collect()
    assert len(r) == 0
    assert r.finalized_count == 1
    assert r.get_by_id(qid) is None


def test_get_returns_none_for_unknown_object() -> None:
    r = QueueRegistry()
    assert r.get(asyncio.Queue()) is None


def test_get_by_id_round_trips() -> None:
    r = QueueRegistry()
    q = asyncio.Queue()
    identity = r.register(q, creator_task_id=None)
    assert r.get_by_id(identity.queue_id) is identity


def test_reset_clears_counter() -> None:
    r = QueueRegistry()
    q1, q2 = asyncio.Queue(), asyncio.Queue()
    r.register(q1, creator_task_id=None)
    r.register(q2, creator_task_id=None)
    assert len(r) == 2
    r.reset()
    assert len(r) == 0
    q3 = asyncio.Queue()
    fresh = r.register(q3, creator_task_id=None)
    assert fresh.queue_id == "q-1"


@pytest.mark.parametrize("kind_cls", [asyncio.LifoQueue, asyncio.PriorityQueue])
def test_register_records_subclass_kinds(
    kind_cls: type[asyncio.Queue],
) -> None:
    r = QueueRegistry()
    q = kind_cls()
    identity = r.register(q, creator_task_id=None)
    assert identity.queue_kind == kind_cls.__name__
