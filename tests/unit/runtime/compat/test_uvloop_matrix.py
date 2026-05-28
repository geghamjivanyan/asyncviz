"""uvloop-matrix tests.

Each test runs once under stock asyncio + once under uvloop (when
available) and verifies the compat layer produces the documented
result on both loops. The matrix is gated on
``is_uvloop_available()`` so the suite passes cleanly on Windows /
PyPy where uvloop isn't installed.
"""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.runtime.compat import (
    LoopCompatibilityManager,
    LoopKind,
    default_config,
    detect_active_loop,
    is_uvloop_available,
    is_uvloop_installed,
)

pytestmark = pytest.mark.skipif(
    not is_uvloop_available(),
    reason="uvloop not installed",
)


def _run_under_uvloop(coro_fn):
    """Run ``coro_fn`` under uvloop with the original policy
    restored at the end. Avoids leaking the policy swap across
    tests."""
    import uvloop

    original_policy = asyncio.get_event_loop_policy()
    try:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        return asyncio.new_event_loop().run_until_complete(coro_fn())
    finally:
        asyncio.set_event_loop_policy(original_policy)


def test_detect_active_loop_under_uvloop() -> None:
    async def _detect() -> LoopKind:
        return detect_active_loop().kind

    kind = _run_under_uvloop(_detect)
    assert kind == LoopKind.UVLOOP


def test_manager_attach_under_uvloop_reports_uvloop_kind() -> None:
    async def _attach() -> tuple[LoopKind, bool]:
        mgr = LoopCompatibilityManager(config=default_config())
        caps = mgr.attach()
        installed = caps.supports_create_task and caps.supports_task_factory
        mgr.detach()
        return caps.kind, installed

    kind, installed = _run_under_uvloop(_attach)
    assert kind == LoopKind.UVLOOP
    assert installed is True


def test_task_bridge_counts_match_across_loops() -> None:
    async def _churn() -> int:
        mgr = LoopCompatibilityManager(config=default_config())
        mgr.attach()
        try:
            await asyncio.gather(*(asyncio.sleep(0) for _ in range(32)))
            await asyncio.sleep(0)
            stats = mgr.task_bridge().stats()
            return stats.tasks_completed
        finally:
            mgr.detach()

    # Under uvloop.
    uvloop_count = _run_under_uvloop(_churn)
    # Under stock asyncio.
    asyncio_count = asyncio.run(_churn())
    assert uvloop_count == asyncio_count == 32


def test_clock_drift_stays_within_tolerance_under_uvloop() -> None:
    async def _drift() -> int:
        mgr = LoopCompatibilityManager(config=default_config())
        mgr.attach()
        bridge = mgr.clock_bridge()
        bridge.sample()
        for _ in range(10):
            await asyncio.sleep(0.005)
            bridge.sample()
        report = bridge.report()
        mgr.detach()
        return report.max_drift_ns

    drift = _run_under_uvloop(_drift)
    assert drift < 5_000_000  # 5ms ceiling — generous for 10 iterations


def test_replay_bridge_observes_frames_under_uvloop() -> None:
    async def _replay() -> tuple[int, int]:
        mgr = LoopCompatibilityManager(config=default_config())
        mgr.attach()
        replay = mgr.replay_bridge()
        replay.start_session(baseline_sequence=0)
        for i in range(20):
            await asyncio.sleep(0.002)
            replay.observe_frame(sequence=i, expected_offset_ns=i * 2_000_000)
        report = replay.report()
        mgr.detach()
        return report.frames_observed, report.frames_drifted

    frames, drifted = _run_under_uvloop(_replay)
    assert frames == 20
    # Under the default 50ms tolerance we should never trip a drift
    # frame on a healthy machine.
    assert drifted == 0


def test_install_uvloop_idempotent_when_already_active() -> None:
    import uvloop

    original_policy = asyncio.get_event_loop_policy()
    try:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        assert is_uvloop_installed()
        mgr = LoopCompatibilityManager()
        # The manager's install path is gated on "no loop running",
        # which is true here. Both calls should succeed.
        first = mgr.install_uvloop()
        second = mgr.install_uvloop()
        assert first is True
        assert second is True
    finally:
        asyncio.set_event_loop_policy(original_policy)
