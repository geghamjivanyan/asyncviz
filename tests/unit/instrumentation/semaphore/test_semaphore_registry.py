"""Registry behaviour: classification, weakref pruning, id stability."""

from __future__ import annotations

import asyncio
import gc

import pytest

from asyncviz.instrumentation.semaphore import (
    SemaphoreRegistry,
    classify_semaphore,
    read_bound_value,
    read_initial_value,
)


def test_classify_distinguishes_stdlib_leaves() -> None:
    assert classify_semaphore(asyncio.Semaphore()) == "Semaphore"
    assert classify_semaphore(asyncio.BoundedSemaphore()) == "BoundedSemaphore"


def test_classify_marks_user_subclasses() -> None:
    class MyS(asyncio.Semaphore):
        pass

    assert classify_semaphore(MyS()) == "subclass"


def test_classify_returns_unknown_for_non_semaphore() -> None:
    assert classify_semaphore(object()) == "unknown"


def test_register_is_idempotent() -> None:
    r = SemaphoreRegistry()
    s = asyncio.Semaphore(2)
    a = r.register(s, initial_value=2, creator_task_id=None)
    b = r.register(s, initial_value=2, creator_task_id=None)
    assert a.semaphore_id == b.semaphore_id
    assert len(r) == 1


def test_register_records_kind_and_initial_value() -> None:
    r = SemaphoreRegistry()
    s = asyncio.Semaphore(7)
    identity = r.register(s, initial_value=7, creator_task_id="t-3")
    assert identity.semaphore_kind == "Semaphore"
    assert identity.initial_value == 7
    assert identity.bound_value is None
    assert identity.creator_task_id == "t-3"


def test_register_records_bounded_value() -> None:
    r = SemaphoreRegistry()
    s = asyncio.BoundedSemaphore(4)
    identity = r.register(s, initial_value=4, creator_task_id=None)
    assert identity.semaphore_kind == "BoundedSemaphore"
    assert identity.bound_value == 4


def test_weakref_finalizer_prunes_dropped_semaphore() -> None:
    r = SemaphoreRegistry()
    s = asyncio.Semaphore(1)
    identity = r.register(s, initial_value=1, creator_task_id=None)
    assert len(r) == 1
    sid = identity.semaphore_id
    del s
    gc.collect()
    assert len(r) == 0
    assert r.finalized_count == 1
    assert r.get_by_id(sid) is None


def test_get_returns_none_for_unknown_object() -> None:
    r = SemaphoreRegistry()
    assert r.get(asyncio.Semaphore()) is None


def test_get_by_id_round_trips() -> None:
    r = SemaphoreRegistry()
    s = asyncio.Semaphore(1)
    identity = r.register(s, initial_value=1, creator_task_id=None)
    assert r.get_by_id(identity.semaphore_id) is identity


def test_reset_clears_counter() -> None:
    r = SemaphoreRegistry()
    a, b = asyncio.Semaphore(1), asyncio.Semaphore(1)
    r.register(a, initial_value=1, creator_task_id=None)
    r.register(b, initial_value=1, creator_task_id=None)
    assert len(r) == 2
    r.reset()
    assert len(r) == 0
    c = asyncio.Semaphore(1)
    fresh = r.register(c, initial_value=1, creator_task_id=None)
    assert fresh.semaphore_id == "s-1"


def test_read_initial_value_from_args_and_kwargs() -> None:
    class _Stub:
        _value = 99

    assert read_initial_value(_Stub(), 4) == 4
    assert read_initial_value(_Stub(), value=12) == 12
    # Falls back to ``_value`` when no explicit argument supplied.
    assert read_initial_value(_Stub()) == 99


def test_read_bound_value_returns_none_for_plain_semaphore() -> None:
    assert read_bound_value(asyncio.Semaphore(2), 2) is None


def test_read_bound_value_returns_bound_for_bounded_semaphore() -> None:
    assert read_bound_value(asyncio.BoundedSemaphore(8), 8) == 8


@pytest.mark.parametrize("kind_cls", [asyncio.Semaphore, asyncio.BoundedSemaphore])
def test_register_records_subclass_kinds(
    kind_cls: type[asyncio.Semaphore],
) -> None:
    r = SemaphoreRegistry()
    s = kind_cls(1)
    identity = r.register(s, initial_value=1, creator_task_id=None)
    assert identity.semaphore_kind == kind_cls.__name__
