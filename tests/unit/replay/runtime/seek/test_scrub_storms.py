"""Rapid-scrub / coalescing tests."""

from __future__ import annotations

from asyncviz.replay.runtime.seek import (
    ReplaySeekCoordinator,
    SeekState,
    get_seek_metrics_snapshot,
)


def test_rapid_scrub_settles_to_last_target(
    coordinator: ReplaySeekCoordinator,
) -> None:
    targets = [5, 8, 3, 12, 7, 18, 4]
    for target in targets:
        coordinator.seek_to_sequence(target)
    assert coordinator.state.state == SeekState.COMPLETED
    # The cursor landed on the *last* target (or later under
    # best_effort).
    assert coordinator.cursor.last_seek_sequence >= 4


def test_repeat_scrubs_warm_the_cache(
    coordinator: ReplaySeekCoordinator,
) -> None:
    before = get_seek_metrics_snapshot()
    # First pass populates the cache.
    for target in (5, 10, 15):
        coordinator.seek_to_sequence(target)
    # Second pass should hit the cache.
    for target in (5, 10, 15):
        coordinator.seek_to_sequence(target)
    after = get_seek_metrics_snapshot()
    assert after.cache_hits - before.cache_hits >= 3


def test_scrubs_count_metric_increments_per_seek(
    coordinator: ReplaySeekCoordinator,
) -> None:
    before = get_seek_metrics_snapshot()
    for target in (5, 10, 15, 20, 5, 10):
        coordinator.seek_to_sequence(target)
    after = get_seek_metrics_snapshot()
    assert after.seeks_requested - before.seeks_requested == 6
    assert after.seeks_completed - before.seeks_completed == 6
