"""Replay dispatch — single hot path that connects every layer.

For each frame the engine pulls, dispatch must:

1. Apply reducers to advance virtual runtime state.
2. Update the engine cursor.
3. Publish the frame through the event router (synchronous
   subscribers — runs inline so order is preserved).
4. Push the frame through the websocket bridge (async — yields
   between sink calls so a slow client doesn't stall reducers).
5. Snap a checkpoint when the checkpoint cadence hits.

The dispatch path is the *only* place these five concerns
intersect, so keeping it one focused module makes the ordering
guarantee easy to verify.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.runtime.models.engine_cursor import EngineCursor
from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.replay_checkpoint_runtime import CheckpointRuntime
from asyncviz.replay.runtime.replay_event_router import ReplayEventRouter
from asyncviz.replay.runtime.replay_reducers import ReducerRegistry
from asyncviz.replay.runtime.replay_state_store import ReplayStateStore
from asyncviz.replay.runtime.replay_websocket_bridge import ReplayWebsocketBridge


@dataclass(frozen=True, slots=True)
class DispatchResult:
    """Outcome of dispatching one frame."""

    frame: ReplayFrame
    new_cursor: EngineCursor
    new_state: VirtualRuntimeState
    checkpoint_taken: bool


class ReplayDispatch:
    """Owns the one-frame dispatch hot path."""

    __slots__ = (
        "_bridge",
        "_checkpoint_interval",
        "_checkpoints",
        "_reducers",
        "_router",
        "_state_store",
    )

    def __init__(
        self,
        *,
        reducers: ReducerRegistry,
        state_store: ReplayStateStore,
        router: ReplayEventRouter,
        bridge: ReplayWebsocketBridge,
        checkpoints: CheckpointRuntime,
        checkpoint_interval: int,
    ) -> None:
        if checkpoint_interval < 1:
            raise ValueError("checkpoint_interval must be >= 1")
        self._reducers = reducers
        self._state_store = state_store
        self._router = router
        self._bridge = bridge
        self._checkpoints = checkpoints
        self._checkpoint_interval = checkpoint_interval

    async def dispatch(
        self, frame: ReplayFrame, *, cursor: EngineCursor, virtual_ns: int,
    ) -> DispatchResult:
        # 1) Reducer → state store (atomic swap inside the store).
        new_state = self._state_store.update(
            lambda current: self._reducers.apply(current, frame),
        )

        # 2) Cursor.
        new_cursor = cursor.advance(
            sequence=frame.sequence,
            monotonic_ns=frame.monotonic_ns,
            virtual_ns=virtual_ns,
        )

        # 3) Synchronous fan-out — preserves canonical ordering.
        self._router.publish(frame)

        # 4) Async sink.
        await self._bridge.emit_frame(frame)
        await self._bridge.emit_state(new_state)

        # 5) Checkpoint cadence.
        checkpoint_taken = False
        if new_cursor.frames_dispatched % self._checkpoint_interval == 0:
            self._checkpoints.record(new_state)
            new_cursor = new_cursor.with_checkpoint(new_state.last_sequence)
            checkpoint_taken = True

        return DispatchResult(
            frame=frame,
            new_cursor=new_cursor,
            new_state=new_state,
            checkpoint_taken=checkpoint_taken,
        )
