from __future__ import annotations

import pytest

from asyncviz.cli.browser.browser_backpressure import (
    BrowserBackpressureGuard,
)


def test_acquire_succeeds_under_cap() -> None:
    guard = BrowserBackpressureGuard(max_concurrent=2)
    assert guard.acquire()
    assert guard.acquire()
    assert guard.in_flight == 2
    assert guard.peak == 2


def test_acquire_blocks_over_cap() -> None:
    guard = BrowserBackpressureGuard(max_concurrent=1)
    assert guard.acquire()
    assert not guard.acquire()
    assert guard.denied == 1


def test_release_frees_slot() -> None:
    guard = BrowserBackpressureGuard(max_concurrent=1)
    guard.acquire()
    guard.release()
    assert guard.in_flight == 0
    assert guard.acquire()


def test_release_idempotent_below_zero() -> None:
    guard = BrowserBackpressureGuard(max_concurrent=1)
    # Release without acquire should not throw.
    guard.release()
    guard.release()
    assert guard.in_flight == 0


def test_invalid_capacity_rejected() -> None:
    with pytest.raises(ValueError):
        BrowserBackpressureGuard(max_concurrent=0)


def test_peak_tracks_high_water_mark() -> None:
    guard = BrowserBackpressureGuard(max_concurrent=3)
    guard.acquire()
    guard.acquire()
    guard.release()
    guard.acquire()
    assert guard.peak == 2
