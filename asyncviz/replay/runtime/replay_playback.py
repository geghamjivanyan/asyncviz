"""Playback controller — owns the engine's async loop.

The controller is the moving part of the engine. Everything else
(clock, scheduler, dispatch, reducers, state store) is passive: the
controller pulls frames from the loader's iterator, asks the
scheduler when to dispatch each one, awaits the pause gate, runs
dispatch, and updates the cursor.

The loop is structured as one ``async def _run()`` because that
makes pause/resume + speed change observably correct — each loop
iteration re-reads the pause gate + scheduler, so a control input
takes effect at the next frame boundary instead of getting
swallowed by a long ``asyncio.sleep``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.runtime.models.playback_state import (
    PlaybackSnapshot,
    PlaybackState,
)
from asyncviz.replay.runtime.replay_clock import ReplayClock
from asyncviz.replay.runtime.replay_cursor_runtime import CursorRuntime
from asyncviz.replay.runtime.replay_dispatch import ReplayDispatch
from asyncviz.replay.runtime.replay_integrity_runtime import (
    IntegrityViolationError,
    check_post_dispatch,
    check_pre_dispatch,
)
from asyncviz.replay.runtime.replay_observability import get_engine_metrics
from asyncviz.replay.runtime.replay_pause import PauseController
from asyncviz.replay.runtime.replay_scheduler import ReplayScheduler
from asyncviz.replay.runtime.replay_tracing import record_engine_trace
from asyncviz.utils.logging import get_logger

logger = get_logger("replay.runtime.playback")


@dataclass(slots=True)
class _LoopState:
    """Mutable state local to the playback loop."""

    state: PlaybackState = PlaybackState.IDLE
    error_detail: str = ""


class PlaybackController:
    """Owns the async playback loop + state transitions."""

    __slots__ = (
        "_clock",
        "_cursor",
        "_dispatch",
        "_loop_state",
        "_pause",
        "_scheduler",
        "_step_event",
        "_stop_event",
        "_strict",
        "_task",
    )

    def __init__(
        self,
        *,
        scheduler: ReplayScheduler,
        clock: ReplayClock,
        pause: PauseController,
        dispatch: ReplayDispatch,
        cursor: CursorRuntime,
        strict_mode: bool = True,
    ) -> None:
        self._scheduler = scheduler
        self._clock = clock
        self._pause = pause
        self._dispatch = dispatch
        self._cursor = cursor
        self._strict = strict_mode
        self._loop_state = _LoopState()
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._step_event = asyncio.Event()

    # ── snapshot accessors ────────────────────────────────────────

    @property
    def playback_state(self) -> PlaybackState:
        return self._loop_state.state

    def snapshot(self, *, queue_depth: int = 0) -> PlaybackSnapshot:
        cursor = self._cursor.cursor
        return PlaybackSnapshot(
            state=self._loop_state.state,
            speed=self._clock.speed,
            last_sequence=cursor.last_sequence,
            last_monotonic_ns=cursor.last_monotonic_ns,
            frames_dispatched=cursor.frames_dispatched,
            queue_depth=queue_depth,
            paused=self._clock.paused,
            error_detail=self._loop_state.error_detail,
        )

    # ── lifecycle ─────────────────────────────────────────────────

    async def play(self, frames: Iterator[ReplayFrame]) -> None:
        """Start (or restart) the playback loop against ``frames``."""
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._loop_state.state = PlaybackState.PLAYING
        self._loop_state.error_detail = ""
        get_engine_metrics().record_engine_started()
        record_engine_trace("engine-started")
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run(frames))

    async def stop(self) -> None:
        """Request the loop to stop. Idempotent."""
        if self._task is None:
            return
        self._stop_event.set()
        # Release any pause + any step gate so the loop sees the
        # stop signal at the next await point.
        self._pause.resume()
        self._step_event.set()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        if self._loop_state.state not in (
            PlaybackState.FAILED,
            PlaybackState.STOPPED,
        ):
            self._loop_state.state = PlaybackState.STOPPED
        get_engine_metrics().record_engine_stopped()
        record_engine_trace("engine-stopped")

    def step(self) -> None:
        """Signal the loop to dispatch one frame (used in
        ``playback_mode='step'``)."""
        self._step_event.set()

    async def wait_until_done(self) -> None:
        if self._task is None:
            return
        with suppress(asyncio.CancelledError):
            await self._task

    # ── internal loop ─────────────────────────────────────────────

    async def _run(self, frames: Iterator[ReplayFrame]) -> None:
        try:
            for frame in frames:
                if self._stop_event.is_set():
                    break
                # Wait if paused.
                await self._pause.wait_until_running()
                if self._stop_event.is_set():
                    break
                # Step mode — wait for explicit step signal.
                if self._scheduler.mode == "step":
                    await self._wait_for_step()
                    if self._stop_event.is_set():
                        break
                # Schedule the dispatch.
                schedule = self._scheduler.schedule(frame.monotonic_ns)
                if schedule.behind_by_ns > 0:
                    get_engine_metrics().record_lag(schedule.behind_by_ns)
                if schedule.wait_seconds > 0:
                    await self._sleep_or_stop(schedule.wait_seconds)
                    if self._stop_event.is_set():
                        break
                # Pre-dispatch invariant.
                cursor = self._cursor.cursor
                violation = check_pre_dispatch(frame, cursor)
                if violation is not None:
                    get_engine_metrics().record_integrity_violation()
                    record_engine_trace(
                        "integrity-violation",
                        f"{violation.kind}: {violation.detail}",
                    )
                    if self._strict:
                        raise IntegrityViolationError(violation.detail)
                    continue
                # Dispatch + cursor update.
                result = await self._dispatch.dispatch(
                    frame,
                    cursor=cursor,
                    virtual_ns=self._clock.current_virtual_ns(),
                )
                self._cursor.set(result.new_cursor)
                get_engine_metrics().record_frame_dispatched()
                get_engine_metrics().record_reducer_invocation()
                if result.checkpoint_taken:
                    get_engine_metrics().record_checkpoint()
                    record_engine_trace(
                        "checkpoint-recorded",
                        f"seq={result.new_state.last_sequence}",
                    )
                # Post-dispatch invariant.
                violation = check_post_dispatch(frame, result.new_state)
                if violation is not None:
                    get_engine_metrics().record_integrity_violation()
                    record_engine_trace(
                        "integrity-violation",
                        f"{violation.kind}: {violation.detail}",
                    )
                    if self._strict:
                        raise IntegrityViolationError(violation.detail)
                record_engine_trace(
                    "frame-dispatched",
                    f"seq={frame.sequence} type={frame.payload_type}",
                )
            self._loop_state.state = PlaybackState.STOPPED
        except IntegrityViolationError as exc:
            self._loop_state.state = PlaybackState.FAILED
            self._loop_state.error_detail = str(exc)
            logger.debug("playback loop failed: %s", exc)
        except Exception as exc:
            self._loop_state.state = PlaybackState.FAILED
            self._loop_state.error_detail = repr(exc)
            logger.exception("replay playback loop crashed")

    async def _sleep_or_stop(self, seconds: float) -> None:
        """Sleep, but wake early if the stop event is set."""
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except TimeoutError:
            return
        # If wait_for returned without timeout, stop was set; the
        # outer loop iteration will see it on the next check.

    async def _wait_for_step(self) -> None:
        await self._step_event.wait()
        self._step_event.clear()
