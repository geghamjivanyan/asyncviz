"""Replay + websocket bridge tests."""

from __future__ import annotations

import asyncio

from asyncviz.runtime.compat import (
    ReplayLoopBridge,
    WebsocketLoopBridge,
    asyncio_baseline_capabilities,
    default_config,
)

# ── replay bridge ────────────────────────────────────────────────


async def test_replay_bridge_starts_session() -> None:
    bridge = ReplayLoopBridge(default_config())
    bridge.attach(asyncio_baseline_capabilities())
    bridge.start_session(baseline_sequence=0)
    assert bridge.replay_safe()


async def test_replay_bridge_observes_frames_without_drift() -> None:
    bridge = ReplayLoopBridge(default_config())
    bridge.attach(asyncio_baseline_capabilities())
    bridge.start_session(baseline_sequence=0)
    await asyncio.sleep(0.01)
    offset = bridge.observe_frame(sequence=1, expected_offset_ns=10_000_000)
    assert offset > 0
    report = bridge.report()
    assert report.frames_observed == 1
    # The default 50ms tolerance gives slow CI plenty of room.
    assert report.frames_drifted == 0


async def test_replay_bridge_detects_drift_with_tight_tolerance() -> None:
    from asyncviz.runtime.compat import LoopCompatConfig

    bridge = ReplayLoopBridge(LoopCompatConfig(clock_drift_tolerance_ns=1))
    bridge.attach(asyncio_baseline_capabilities())
    bridge.start_session(baseline_sequence=0)
    await asyncio.sleep(0.005)
    bridge.observe_frame(sequence=1, expected_offset_ns=0)
    assert bridge.report().frames_drifted >= 1


async def test_replay_bridge_reset() -> None:
    bridge = ReplayLoopBridge(default_config())
    bridge.attach(asyncio_baseline_capabilities())
    bridge.start_session(baseline_sequence=0)
    bridge.observe_frame(sequence=1, expected_offset_ns=0)
    bridge.reset()
    assert bridge.report().frames_observed == 0


# ── websocket bridge ─────────────────────────────────────────────


def test_websocket_bridge_disabled_when_configured() -> None:
    from asyncviz.runtime.compat import LoopCompatConfig

    bridge = WebsocketLoopBridge(LoopCompatConfig(record_websocket_anomalies=False))
    bridge.record_flush()
    assert bridge.report().flushes_observed == 0


def test_websocket_bridge_records_flushes() -> None:
    bridge = WebsocketLoopBridge(default_config())
    bridge.record_flush()
    bridge.record_flush()
    bridge.record_flush()
    report = bridge.report()
    assert report.flushes_observed == 3


def test_websocket_bridge_detects_cadence_deviation() -> None:
    import time

    bridge = WebsocketLoopBridge(default_config(), target_interval_ns=1_000)
    bridge.record_flush()
    time.sleep(0.005)
    bridge.record_flush()
    report = bridge.report()
    assert report.deviations_recorded >= 1


def test_websocket_bridge_reset() -> None:
    bridge = WebsocketLoopBridge(default_config())
    bridge.record_flush()
    bridge.reset()
    assert bridge.report().flushes_observed == 0
