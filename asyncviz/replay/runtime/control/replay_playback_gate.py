"""Async pause gate — the engine's dispatch loop awaits it.

Wraps an :class:`asyncio.Event` so the engine loop can pause at a
frame boundary with one ``await gate.wait_until_open()`` call. The
gate is *open* when playback is allowed and *closed* when paused.

Distinct from :class:`asyncviz.replay.runtime.replay_pause.PauseController`
in two ways:

1. The gate is *state*; the controller is the *orchestrator* that
   flips it.
2. The coordinator uses a *single* gate for pause + step + stop so
   the engine loop only awaits one primitive, not three.
"""

from __future__ import annotations

import asyncio
import threading


class ReplayPlaybackGate:
    """Asyncio.Event-backed pause gate."""

    __slots__ = ("_event", "_lock", "_loop")

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._event.set()  # initial state: open (playback allowed)
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def is_open(self) -> bool:
        return self._event.is_set()

    def open(self) -> None:
        """Allow playback to proceed. Idempotent."""
        with self._lock:
            self._event.set()

    def close(self) -> None:
        """Block the playback loop at its next ``wait_until_open``.
        Idempotent."""
        with self._lock:
            self._event.clear()

    async def wait_until_open(self) -> None:
        """Suspend until the gate is open. Returns immediately when
        the gate is already open."""
        await self._event.wait()
