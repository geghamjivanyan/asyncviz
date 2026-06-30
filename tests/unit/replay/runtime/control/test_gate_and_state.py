"""ReplayPlaybackGate + state-holder tests."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.replay.runtime.control import (
    PlaybackPhase,
    PlaybackPhaseSnapshot,
    ReplayPlaybackGate,
    ReplayPlaybackStateHolder,
)


def test_gate_initially_open() -> None:
    gate = ReplayPlaybackGate()
    assert gate.is_open


def test_gate_close_open_cycles() -> None:
    gate = ReplayPlaybackGate()
    gate.close()
    assert not gate.is_open
    gate.open()
    assert gate.is_open


@pytest.mark.asyncio
async def test_gate_wait_releases_when_opened() -> None:
    gate = ReplayPlaybackGate()
    gate.close()

    async def waiter() -> None:
        await asyncio.wait_for(gate.wait_until_open(), timeout=1.0)

    task = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    assert not task.done()
    gate.open()
    await task


def test_state_holder_swaps_atomically_and_notifies() -> None:
    holder = ReplayPlaybackStateHolder()
    received: list[tuple[PlaybackPhase, PlaybackPhase]] = []
    holder.subscribe(lambda prev, nxt: received.append((prev.phase, nxt.phase)))
    holder.transition_to(
        PlaybackPhaseSnapshot(
            phase=PlaybackPhase.PLAYING,
            last_sequence=0,
            last_monotonic_ns=0,
        ),
    )
    holder.transition_to(
        PlaybackPhaseSnapshot(
            phase=PlaybackPhase.PAUSED,
            last_sequence=10,
            last_monotonic_ns=100,
        ),
    )
    assert received == [
        (PlaybackPhase.IDLE, PlaybackPhase.PLAYING),
        (PlaybackPhase.PLAYING, PlaybackPhase.PAUSED),
    ]
    assert holder.phase == PlaybackPhase.PAUSED


def test_state_holder_update_position_does_not_change_phase() -> None:
    holder = ReplayPlaybackStateHolder()
    holder.transition_to(
        PlaybackPhaseSnapshot(
            phase=PlaybackPhase.PLAYING,
            last_sequence=0,
            last_monotonic_ns=0,
        ),
    )
    holder.update_position(last_sequence=42, last_monotonic_ns=420)
    assert holder.phase == PlaybackPhase.PLAYING
    assert holder.snapshot.last_sequence == 42


def test_listener_exception_does_not_kill_holder() -> None:
    holder = ReplayPlaybackStateHolder()
    holder.subscribe(lambda prev, nxt: (_ for _ in ()).throw(RuntimeError("noisy")))
    holder.subscribe(lambda prev, nxt: None)
    # Should not raise.
    holder.transition_to(
        PlaybackPhaseSnapshot(
            phase=PlaybackPhase.PLAYING,
            last_sequence=0,
            last_monotonic_ns=0,
        ),
    )
    assert holder.phase == PlaybackPhase.PLAYING
