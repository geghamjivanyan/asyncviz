from __future__ import annotations

import threading

from asyncviz.runtime.monitoring.blocking.stack_capture import (
    ReentryGuard,
    TaskMetadataResolver,
)


def test_reentry_guard_allows_first_acquire() -> None:
    g = ReentryGuard()
    with g.acquire() as allowed:
        assert allowed is True


def test_reentry_guard_blocks_nested_acquire_on_same_thread() -> None:
    g = ReentryGuard()
    with g.acquire() as outer_ok:
        assert outer_ok is True
        with g.acquire() as inner_ok:
            assert inner_ok is False


def test_reentry_guard_independent_per_thread() -> None:
    g = ReentryGuard()
    other_allowed = []

    def other():
        with g.acquire() as allowed:
            other_allowed.append(allowed)

    with g.acquire() as outer_ok:
        assert outer_ok is True
        t = threading.Thread(target=other)
        t.start()
        t.join()
    assert other_allowed == [True]


def test_reentry_guard_releases_on_exception() -> None:
    g = ReentryGuard()
    try:
        with g.acquire():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    # Should be able to re-enter after the exception.
    with g.acquire() as allowed:
        assert allowed is True


def test_task_resolver_returns_empty_outside_loop() -> None:
    r = TaskMetadataResolver()
    meta = r.resolve()
    assert meta.task_id is None
    assert meta.task_name is None


def test_task_resolver_handles_no_registry() -> None:
    """The resolver returns sane defaults even with no registry attached."""
    r = TaskMetadataResolver(registry=None)
    meta = r.resolve()
    # Outside an event loop both task and registry are None — no crash.
    assert meta.task_id is None
