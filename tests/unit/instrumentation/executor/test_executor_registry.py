"""Registry behaviour: classification, weakref pruning, lookups."""

from __future__ import annotations

import concurrent.futures
import gc

from asyncviz.instrumentation.executor import (
    ExecutorRegistry,
    WorkItemRegistry,
    classify_executor,
    read_callable_name,
    read_max_workers,
    read_thread_name_prefix,
)


def test_classify_thread_pool_executor() -> None:
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        assert classify_executor(pool) == "Thread"
    finally:
        pool.shutdown(wait=True)


def test_classify_process_pool_executor() -> None:
    pool = concurrent.futures.ProcessPoolExecutor(max_workers=1)
    try:
        assert classify_executor(pool) == "Process"
    finally:
        pool.shutdown(wait=True)


def test_classify_default_short_circuit() -> None:
    assert classify_executor(None, is_default=True) == "default"


def test_classify_unknown_for_non_executor() -> None:
    assert classify_executor(object()) == "unknown"


def test_read_max_workers() -> None:
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    try:
        assert read_max_workers(pool) == 4
    finally:
        pool.shutdown(wait=True)


def test_read_thread_name_prefix() -> None:
    pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="hello",
    )
    try:
        assert read_thread_name_prefix(pool) == "hello"
    finally:
        pool.shutdown(wait=True)


def test_read_callable_name_qualname() -> None:
    def named() -> None:
        pass

    assert read_callable_name(named) == "test_read_callable_name_qualname.<locals>.named"


def test_read_callable_name_lambda() -> None:
    # lambdas keep ``__name__ = "<lambda>"`` which is still usable.
    assert read_callable_name(lambda: None) is not None


def test_register_is_idempotent() -> None:
    r = ExecutorRegistry()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        a = r.register(pool, is_default=False, creator_task_id=None)
        b = r.register(pool, is_default=False, creator_task_id=None)
        assert a.executor_id == b.executor_id
        assert len(r) == 1
    finally:
        pool.shutdown(wait=True)


def test_register_records_kind_and_max_workers() -> None:
    r = ExecutorRegistry()
    pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=3, thread_name_prefix="p",
    )
    try:
        identity = r.register(pool, is_default=False, creator_task_id="t-1")
        assert identity.executor_kind == "Thread"
        assert identity.max_workers == 3
        assert identity.thread_name_prefix == "p"
        assert identity.creator_task_id == "t-1"
    finally:
        pool.shutdown(wait=True)


def test_weakref_finalizer_prunes_dropped_executor() -> None:
    r = ExecutorRegistry()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    identity = r.register(pool, is_default=False, creator_task_id=None)
    assert len(r) == 1
    eid = identity.executor_id
    pool.shutdown(wait=True)
    del pool
    gc.collect()
    assert len(r) == 0
    assert r.finalized_count == 1
    assert r.get_by_id(eid) is None


def test_reset_clears_counter() -> None:
    r = ExecutorRegistry()
    a, b = (
        concurrent.futures.ThreadPoolExecutor(max_workers=1),
        concurrent.futures.ThreadPoolExecutor(max_workers=1),
    )
    try:
        r.register(a, is_default=False, creator_task_id=None)
        r.register(b, is_default=False, creator_task_id=None)
        assert len(r) == 2
        r.reset()
        assert len(r) == 0
        c = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            fresh = r.register(c, is_default=False, creator_task_id=None)
            assert fresh.executor_id == "e-1"
        finally:
            c.shutdown(wait=True)
    finally:
        a.shutdown(wait=True)
        b.shutdown(wait=True)


# ── work item registry ──────────────────────────────────────────────────


def test_work_item_register_allocates_monotonic_ids() -> None:
    r = WorkItemRegistry()
    a = r.register(executor_id="e-1", submitting_task_id=None, callable_name="f")
    b = r.register(executor_id="e-1", submitting_task_id=None, callable_name="g")
    assert a.work_item_id == "w-1"
    assert b.work_item_id == "w-2"


def test_work_item_marks_lifecycle() -> None:
    r = WorkItemRegistry()
    identity = r.register(
        executor_id="e-1", submitting_task_id="t-1", callable_name="f",
    )
    r.mark_started(
        identity.work_item_id, worker_thread_name="t", started_at_ns=100,
    )
    state = r.state(identity.work_item_id)
    assert state is not None
    assert state.started is True
    assert state.worker_thread_name == "t"
    r.mark_completed(identity.work_item_id, finished_at_ns=200)
    state = r.state(identity.work_item_id)
    assert state is not None
    assert state.completed is True
    assert state.finished_at_ns == 200


def test_work_item_forget_removes_entry() -> None:
    r = WorkItemRegistry()
    identity = r.register(
        executor_id="e-1", submitting_task_id=None, callable_name=None,
    )
    r.forget(identity.work_item_id)
    assert len(r) == 0
    assert r.finalized_count == 1
