"""Compatibility manager (façade) tests."""

from __future__ import annotations

import asyncio

from asyncviz.runtime.compat import (
    LoopCompatibilityManager,
    LoopKind,
    default_config,
    is_uvloop_available,
    is_uvloop_installed,
    prefer_uvloop_config,
)


def test_manager_default_state() -> None:
    mgr = LoopCompatibilityManager()
    assert mgr.installed_uvloop is False
    assert mgr.capabilities.kind in (LoopKind.ASYNCIO, LoopKind.UVLOOP)


def test_install_uvloop_when_available_then_restore() -> None:
    if not is_uvloop_available():
        return
    mgr = LoopCompatibilityManager(config=prefer_uvloop_config())
    installed = mgr.install_uvloop()
    assert installed is True
    assert is_uvloop_installed()
    mgr.restore_default_policy()
    assert is_uvloop_installed() is False


def test_install_uvloop_falls_back_gracefully() -> None:
    # The manager should never raise when fallback is enabled, even if
    # we try to install while a loop is running (which asyncio
    # explicitly forbids).
    mgr = LoopCompatibilityManager(config=prefer_uvloop_config())

    async def _inside_loop() -> bool:
        # We're already in a running loop, so the policy swap will
        # be rejected.
        return mgr.install_uvloop()

    installed = asyncio.run(_inside_loop())
    # On macOS/Linux the inner call sees uvloop's policy already
    # selected — accept either outcome.
    assert isinstance(installed, bool)


async def test_attach_detects_active_loop() -> None:
    mgr = LoopCompatibilityManager(config=default_config())
    caps = mgr.attach()
    assert caps.kind in (LoopKind.ASYNCIO, LoopKind.UVLOOP)
    mgr.detach()


async def test_attach_records_metrics() -> None:
    mgr = LoopCompatibilityManager(config=default_config())
    mgr.attach()
    snap = mgr.metrics.snapshot()
    assert snap.managers_attached >= 1
    mgr.detach()


async def test_attach_installs_bridges() -> None:
    mgr = LoopCompatibilityManager(config=default_config())
    mgr.attach()
    assert mgr.task_bridge().stats().installed is True
    assert mgr.scheduler_bridge().stats().installed is True
    mgr.detach()
    assert mgr.task_bridge().stats().installed is False
    assert mgr.scheduler_bridge().stats().installed is False


async def test_diagnostics_returns_structured_snapshot() -> None:
    mgr = LoopCompatibilityManager()
    mgr.attach()
    try:
        diag = mgr.diagnostics()
        assert diag.state.active_kind in (LoopKind.ASYNCIO, LoopKind.UVLOOP)
        assert diag.state.capabilities is mgr.capabilities
        assert diag.task.installed is True
    finally:
        mgr.detach()


async def test_manager_state_reflects_loop() -> None:
    mgr = LoopCompatibilityManager()
    mgr.attach()
    try:
        state = mgr.state()
        assert state.detected_at_ns > 0
        assert state.active_kind in (LoopKind.ASYNCIO, LoopKind.UVLOOP)
    finally:
        mgr.detach()


async def test_reset_clears_bridge_state() -> None:
    mgr = LoopCompatibilityManager()
    mgr.attach()
    try:
        mgr.clock_bridge().sample()
        mgr.websocket_bridge().record_flush()
        mgr.reset()
        assert mgr.clock_bridge().report().samples_observed == 0
        assert mgr.websocket_bridge().report().flushes_observed == 0
    finally:
        mgr.detach()


async def test_detach_is_idempotent() -> None:
    mgr = LoopCompatibilityManager()
    mgr.attach()
    mgr.detach()
    mgr.detach()  # should not raise
