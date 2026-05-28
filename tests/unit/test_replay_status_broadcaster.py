"""Tests for the replay-status broadcaster.

The broadcaster turns engine snapshots into ``replay_status`` envelopes
and broadcasts them through the dashboard's :class:`ConnectionManager`.
These tests pin three contracts:

* The payload shape the frontend bridge consumes is stable.
* :meth:`start` emits synchronously so the SPA hydrates before the
  first ``runtime_event`` lands.
* Dedup suppresses redundant emissions but lets state transitions
  through.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from asyncviz.dashboard.replay.replay_status_broadcaster import (
    ReplayRecordingMetadata,
    ReplayStatusBroadcaster,
)
from asyncviz.dashboard.websocket.protocol import Envelope


@dataclass
class _FakeSnapshot:
    state: Any
    speed: float = 1.0
    last_sequence: int = 0
    last_monotonic_ns: int = 0
    frames_dispatched: int = 0
    queue_depth: int = 0
    paused: bool = False
    error_detail: str = ""


class _FakeState:
    """Minimal stand-in for :class:`PlaybackState` — the broadcaster
    only reads ``.value``."""

    def __init__(self, name: str) -> None:
        self.value = name


class _FakeEngine:
    """Engine stand-in — provides a controllable :meth:`snapshot`."""

    def __init__(self) -> None:
        self.snapshot_value = _FakeSnapshot(state=_FakeState("idle"))

    def snapshot(self) -> _FakeSnapshot:
        return self.snapshot_value


class _CapturingManager:
    """Collects every broadcasted envelope for assertion."""

    def __init__(self) -> None:
        self.envelopes: list[Envelope] = []

    async def broadcast(self, envelope: Envelope) -> int:
        self.envelopes.append(envelope)
        return 1


def _make_metadata() -> ReplayRecordingMetadata:
    return ReplayRecordingMetadata(
        bundle_id="bundle-xyz",
        runtime_id="rt-1",
        event_count=42,
        chunk_count=3,
        snapshot_count=1,
        last_sequence=100,
        finalized=True,
        source_label="/tmp/test.avz",
    )


@pytest.mark.asyncio
async def test_broadcaster_emits_initial_envelope_on_start() -> None:
    """The first ``replay_status`` must land DURING ``start()`` so
    the frontend's bridge has the session window populated before
    any runtime_event arrives."""
    engine = _FakeEngine()
    manager = _CapturingManager()
    broadcaster = ReplayStatusBroadcaster(
        engine=engine,
        metadata=_make_metadata(),
        manager=manager,  # type: ignore[arg-type]
        dashboard_loop=asyncio.get_running_loop(),
        interval_seconds=0.05,
    )
    await broadcaster.start()
    # ``start()`` returned — the initial envelope must already be on the wire.
    assert len(manager.envelopes) == 1
    await broadcaster.stop()


@pytest.mark.asyncio
async def test_initial_payload_carries_recording_metadata_and_window() -> None:
    engine = _FakeEngine()
    manager = _CapturingManager()
    metadata = _make_metadata()
    broadcaster = ReplayStatusBroadcaster(
        engine=engine,
        metadata=metadata,
        manager=manager,  # type: ignore[arg-type]
        dashboard_loop=asyncio.get_running_loop(),
        interval_seconds=10.0,  # No cadence noise — only the initial emission.
    )
    await broadcaster.start()
    await broadcaster.stop()

    initial = manager.envelopes[0]
    assert initial.type == "replay_status"
    assert initial.payload["recording"]["bundle_id"] == "bundle-xyz"
    assert initial.payload["recording"]["runtime_id"] == "rt-1"
    assert initial.payload["recording"]["event_count"] == 42
    # Window's ``max_sequence`` is the bundle's terminal sequence —
    # this is the key field the SPA reads to decide "loaded" vs
    # "no recording loaded".
    assert initial.payload["window"]["max_sequence"] == 100
    assert initial.payload["window"]["min_sequence"] == 1
    # Playback state mirrors the engine snapshot.
    assert initial.payload["playback"]["state"] == "idle"
    assert initial.payload["playback"]["speed"] == 1.0


@pytest.mark.asyncio
async def test_broadcaster_deduplicates_identical_snapshots() -> None:
    """The cadence loop fires every ``interval_seconds`` regardless of
    whether the engine state moved. Identical payloads must NOT be
    re-broadcast — the SPA's bridge already has them."""
    engine = _FakeEngine()
    manager = _CapturingManager()
    broadcaster = ReplayStatusBroadcaster(
        engine=engine,
        metadata=_make_metadata(),
        manager=manager,  # type: ignore[arg-type]
        dashboard_loop=asyncio.get_running_loop(),
        interval_seconds=0.05,
    )
    await broadcaster.start()
    # Let several cadence ticks fire without changing the engine.
    await asyncio.sleep(0.25)
    await broadcaster.stop()
    # Initial + (possibly) final. The cadence ticks in between MUST
    # be deduplicated.
    types = [e.type for e in manager.envelopes]
    assert all(t == "replay_status" for t in types)
    assert len(manager.envelopes) <= 2


@pytest.mark.asyncio
async def test_broadcaster_emits_on_state_transition() -> None:
    """A real state change must produce a new envelope on the next
    cadence tick (not be dedup-suppressed)."""
    engine = _FakeEngine()
    manager = _CapturingManager()
    broadcaster = ReplayStatusBroadcaster(
        engine=engine,
        metadata=_make_metadata(),
        manager=manager,  # type: ignore[arg-type]
        dashboard_loop=asyncio.get_running_loop(),
        interval_seconds=0.03,
    )
    await broadcaster.start()
    # Move the engine forward.
    engine.snapshot_value = _FakeSnapshot(
        state=_FakeState("playing"),
        last_sequence=50,
        frames_dispatched=25,
    )
    # Wait long enough for the cadence task to pick it up.
    await asyncio.sleep(0.12)
    await broadcaster.stop()

    states = [
        (e.payload["playback"]["state"], e.payload["playback"]["last_sequence"])
        for e in manager.envelopes
    ]
    # The initial is ("idle", 0) and at least one update is ("playing", 50).
    assert ("idle", 0) in states
    assert ("playing", 50) in states


@pytest.mark.asyncio
async def test_broadcaster_emits_final_envelope_on_stop() -> None:
    """``stop()`` records a final snapshot so the SPA leaves the
    "stopped" / final state visible after playback completes."""
    engine = _FakeEngine()
    manager = _CapturingManager()
    broadcaster = ReplayStatusBroadcaster(
        engine=engine,
        metadata=_make_metadata(),
        manager=manager,  # type: ignore[arg-type]
        dashboard_loop=asyncio.get_running_loop(),
        interval_seconds=10.0,
    )
    await broadcaster.start()
    # Engine settles into "stopped".
    engine.snapshot_value = _FakeSnapshot(
        state=_FakeState("stopped"),
        last_sequence=100,
        frames_dispatched=100,
    )
    await broadcaster.stop()

    last = manager.envelopes[-1]
    assert last.payload["playback"]["state"] == "stopped"


@pytest.mark.asyncio
async def test_double_start_is_idempotent() -> None:
    engine = _FakeEngine()
    manager = _CapturingManager()
    broadcaster = ReplayStatusBroadcaster(
        engine=engine,
        metadata=_make_metadata(),
        manager=manager,  # type: ignore[arg-type]
        dashboard_loop=asyncio.get_running_loop(),
        interval_seconds=10.0,
    )
    await broadcaster.start()
    await broadcaster.start()  # Should be a no-op.
    await broadcaster.stop()
    # Exactly one initial + at most one final emission.
    assert 1 <= len(manager.envelopes) <= 2
