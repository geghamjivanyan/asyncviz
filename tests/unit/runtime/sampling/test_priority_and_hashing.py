"""Priority classification + deterministic bucket tests."""

from __future__ import annotations

from asyncviz.runtime.sampling import (
    BUCKET_COUNT,
    SamplingPriority,
    classify_event_priority,
    deterministic_bucket,
    is_structural_event,
)


def test_classify_critical_events() -> None:
    assert classify_event_priority("runtime.warning") == SamplingPriority.CRITICAL
    assert classify_event_priority("runtime.started") == SamplingPriority.CRITICAL
    assert (
        classify_event_priority("asyncio.loop.blocked") == SamplingPriority.CRITICAL
    )


def test_classify_structural_events() -> None:
    assert (
        classify_event_priority("asyncio.task.created") == SamplingPriority.STRUCTURAL
    )
    assert (
        classify_event_priority("asyncio.queue.created") == SamplingPriority.STRUCTURAL
    )
    assert (
        classify_event_priority("asyncio.gather.completed")
        == SamplingPriority.STRUCTURAL
    )


def test_classify_delta_events() -> None:
    assert (
        classify_event_priority("asyncio.queue.metrics.updated")
        == SamplingPriority.DELTA
    )
    assert classify_event_priority("runtime.metric") == SamplingPriority.DELTA


def test_classify_falls_back_to_state() -> None:
    assert (
        classify_event_priority("asyncio.task.waiting") == SamplingPriority.STATE
    )
    assert classify_event_priority("totally.unknown") == SamplingPriority.STATE


def test_priority_ordering() -> None:
    assert SamplingPriority.CRITICAL > SamplingPriority.STRUCTURAL
    assert SamplingPriority.STRUCTURAL > SamplingPriority.STATE
    assert SamplingPriority.STATE > SamplingPriority.DELTA


def test_is_structural_event_for_lifecycle() -> None:
    assert is_structural_event("asyncio.task.created")
    assert is_structural_event("asyncio.queue.created")
    assert is_structural_event("runtime.warning")  # critical also returns True
    assert not is_structural_event("asyncio.queue.metrics.updated")


def test_deterministic_bucket_is_stable() -> None:
    b1 = deterministic_bucket("asyncio.task.created", 42)
    b2 = deterministic_bucket("asyncio.task.created", 42)
    assert b1 == b2
    assert 0 <= b1 < BUCKET_COUNT


def test_deterministic_bucket_changes_with_sequence() -> None:
    # Over a window of sequences we expect bucket diversity (not
    # all the same), even if any *specific* adjacent pair could
    # theoretically collide.
    buckets = {
        deterministic_bucket("asyncio.task.created", i) for i in range(16)
    }
    assert len(buckets) > 1


def test_deterministic_bucket_changes_with_seed() -> None:
    a = deterministic_bucket("asyncio.task.created", 1, seed=1)
    b = deterministic_bucket("asyncio.task.created", 1, seed=2)
    assert a != b
