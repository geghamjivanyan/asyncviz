"""Registry behaviour: ids, progress tracking, weakref pruning, lookups."""

from __future__ import annotations

import asyncio
import gc

import pytest

from asyncviz.instrumentation.gather import GatherRegistry


def test_register_allocates_monotonic_ids() -> None:
    r = GatherRegistry()
    a = r.register(parent_task_id="t-1", child_task_ids=["c1"], return_exceptions=False)
    b = r.register(parent_task_id="t-1", child_task_ids=["c2"], return_exceptions=False)
    assert a.gather_id == "g-1"
    assert b.gather_id == "g-2"


def test_register_records_metadata() -> None:
    r = GatherRegistry()
    identity = r.register(
        parent_task_id="t-7",
        child_task_ids=["c1", "c2", "c3"],
        return_exceptions=True,
    )
    assert identity.parent_task_id == "t-7"
    assert identity.child_count == 3
    assert identity.child_task_ids == ("c1", "c2", "c3")
    assert identity.return_exceptions is True


@pytest.mark.asyncio
async def test_weakref_finalizer_prunes_after_anchor_gc() -> None:
    r = GatherRegistry()
    loop = asyncio.get_running_loop()
    anchor = loop.create_future()
    identity = r.register(
        parent_task_id=None,
        child_task_ids=["c1"],
        return_exceptions=False,
        anchor=anchor,
    )
    assert len(r) == 1
    del anchor
    gc.collect()
    assert len(r) == 0
    assert r.finalized_count == 1
    assert r.get(identity.gather_id) is None


def test_record_child_completed_tracks_progress() -> None:
    r = GatherRegistry()
    identity = r.register(
        parent_task_id=None,
        child_task_ids=["c1", "c2", "c3"],
        return_exceptions=False,
    )
    assert r.record_child_completed(identity.gather_id) == (1, 3)
    assert r.record_child_completed(identity.gather_id) == (2, 3)
    assert r.record_child_completed(identity.gather_id) == (3, 3)


def test_record_child_completed_returns_none_for_unknown() -> None:
    r = GatherRegistry()
    assert r.record_child_completed("ghost") is None


def test_mark_terminal_sets_flags() -> None:
    r = GatherRegistry()
    identity = r.register(
        parent_task_id=None,
        child_task_ids=["c"],
        return_exceptions=False,
    )
    r.mark_terminal(identity.gather_id, cancelled=True)
    progress = r.progress(identity.gather_id)
    assert progress is not None
    _completed, _total, cancelled, failed = progress
    assert cancelled is True
    assert failed is False


def test_forget_removes_entry() -> None:
    r = GatherRegistry()
    identity = r.register(
        parent_task_id=None,
        child_task_ids=["c"],
        return_exceptions=False,
    )
    r.forget(identity.gather_id)
    assert len(r) == 0
    assert r.finalized_count == 1


def test_reset_clears_counter() -> None:
    r = GatherRegistry()
    r.register(parent_task_id=None, child_task_ids=["c"], return_exceptions=False)
    r.register(parent_task_id=None, child_task_ids=["c"], return_exceptions=False)
    assert len(r) == 2
    r.reset()
    assert len(r) == 0
    fresh = r.register(
        parent_task_id=None,
        child_task_ids=["c"],
        return_exceptions=False,
    )
    assert fresh.gather_id == "g-1"


def test_iter_identities_returns_all_active() -> None:
    r = GatherRegistry()
    r.register(parent_task_id=None, child_task_ids=["c1"], return_exceptions=False)
    r.register(parent_task_id=None, child_task_ids=["c2"], return_exceptions=False)
    ids = sorted(identity.gather_id for identity in r.iter_identities())
    assert ids == ["g-1", "g-2"]
