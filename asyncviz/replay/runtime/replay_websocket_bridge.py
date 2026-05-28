"""Websocket bridge for replay frames.

The bridge consumes :class:`ReplayFrame` events the engine
dispatches and converts them into messages that the existing
dashboard websocket layer can fan out to connected clients.

We deliberately don't import the dashboard's websocket server
here. The bridge speaks against a small :class:`ReplayWebsocketSink`
protocol so:

* tests can substitute a recording sink that just collects frames;
* the future remote replay viewer can plug in its own sink;
* the dashboard's actual websocket consumer wires itself to the
  sink at startup, without this layer needing to know about it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState


@runtime_checkable
class ReplayWebsocketSink(Protocol):
    """Receiver contract for a frame stream.

    Implementations are responsible for serialization + transport.
    The bridge only cares that each frame lands once, in order, and
    that ``push_state`` snapshots are best-effort (drop is OK on
    overflow)."""

    async def push_frame(self, frame: ReplayFrame) -> None: ...
    async def push_state(self, state: VirtualRuntimeState) -> None: ...


# ── built-in sinks ────────────────────────────────────────────────


@dataclass(slots=True)
class CollectingSink:
    """Test / inspection sink — accumulates frames + states in memory."""

    frames: list[ReplayFrame] | None = None
    states: list[VirtualRuntimeState] | None = None

    def __post_init__(self) -> None:
        if self.frames is None:
            self.frames = []
        if self.states is None:
            self.states = []

    async def push_frame(self, frame: ReplayFrame) -> None:
        assert self.frames is not None
        self.frames.append(frame)

    async def push_state(self, state: VirtualRuntimeState) -> None:
        assert self.states is not None
        self.states.append(state)


@dataclass(slots=True)
class NullSink:
    """No-op sink — used when ``websocket_enabled=False``."""

    async def push_frame(self, frame: ReplayFrame) -> None:
        return None

    async def push_state(self, state: VirtualRuntimeState) -> None:
        return None


# ── bridge ────────────────────────────────────────────────────────

PushHook = Callable[[ReplayFrame], Awaitable[Any]]


class ReplayWebsocketBridge:
    """Adapts engine dispatch → sink.

    The bridge runs ``sink.push_frame`` for every dispatched frame
    and ``sink.push_state`` for every state mutation. State pushes
    are coalesced — if the engine emits ten state updates faster
    than the sink can drain them, only the latest is sent."""

    __slots__ = ("_pending_state", "_sink", "_state_lock")

    def __init__(self, sink: ReplayWebsocketSink) -> None:
        self._sink = sink
        self._state_lock = asyncio.Lock()
        self._pending_state: VirtualRuntimeState | None = None

    @property
    def sink(self) -> ReplayWebsocketSink:
        return self._sink

    async def emit_frame(self, frame: ReplayFrame) -> None:
        await self._sink.push_frame(frame)

    async def emit_state(self, state: VirtualRuntimeState) -> None:
        """Coalesce state pushes — only the latest snapshot is sent
        when the sink can't keep up."""
        async with self._state_lock:
            self._pending_state = state
            current = self._pending_state
        with suppress(Exception):
            await self._sink.push_state(current)
        async with self._state_lock:
            if self._pending_state is current:
                self._pending_state = None
