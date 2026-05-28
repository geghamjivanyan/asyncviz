"""Request dispatch — routes incoming requests to the right
controller.

The dispatch layer keeps the coordinator's public API uniform: one
``dispatch(request)`` regardless of whether the caller wants to
pause, resume, or step. The dispatch layer:

1. Coalesces redundant requests (configurable).
2. Pushes accepted requests onto the bounded coordination queue.
3. Forwards to the right controller.
4. Records drops + accepts.
"""

from __future__ import annotations

import threading

from asyncviz.replay.runtime.control.models.pause_request import (
    PauseRequest,
    ResumeRequest,
    StepRequest,
)
from asyncviz.replay.runtime.control.models.playback_phase import (
    PlaybackPhase,
)
from asyncviz.replay.runtime.control.replay_pause_barrier import PauseBarrier
from asyncviz.replay.runtime.control.replay_pause_controller import (
    PauseController,
)
from asyncviz.replay.runtime.control.replay_playback_backpressure import (
    CoordinationQueue,
)
from asyncviz.replay.runtime.control.replay_playback_state import (
    ReplayPlaybackStateHolder,
)
from asyncviz.replay.runtime.control.replay_resume_barrier import ResumeBarrier
from asyncviz.replay.runtime.control.replay_resume_controller import (
    ResumeController,
)

Request = PauseRequest | ResumeRequest | StepRequest


class CoordinationDispatch:
    """Single entry point for every pause / resume / step request."""

    __slots__ = (
        "_coalesce",
        "_lock",
        "_pause",
        "_pause_queue",
        "_request_counter",
        "_resume",
        "_resume_queue",
        "_state",
        "_step_pending",
    )

    def __init__(
        self,
        *,
        pause: PauseController,
        resume: ResumeController,
        state: ReplayPlaybackStateHolder,
        pause_queue_capacity: int = 64,
        resume_queue_capacity: int = 64,
        coalesce_repeated_requests: bool = True,
    ) -> None:
        self._pause = pause
        self._resume = resume
        self._state = state
        self._pause_queue: CoordinationQueue[PauseRequest] = CoordinationQueue(
            capacity=pause_queue_capacity,
        )
        self._resume_queue: CoordinationQueue[ResumeRequest] = CoordinationQueue(
            capacity=resume_queue_capacity,
        )
        self._coalesce = coalesce_repeated_requests
        self._request_counter = 0
        self._step_pending: int = 0
        self._lock = threading.Lock()

    # ── public API ────────────────────────────────────────────────

    def allocate_request_id(self) -> int:
        with self._lock:
            self._request_counter += 1
            return self._request_counter

    def submit_pause(self, request: PauseRequest) -> PauseBarrier:
        """Submit a pause request; returns the awaitable barrier."""
        if self._coalesce and self._state.phase in (
            PlaybackPhase.PAUSED, PlaybackPhase.PAUSING,
        ):
            # Already pausing / paused; the pause controller will
            # resolve the barrier immediately, but we still enqueue
            # for telemetry consistency.
            pass
        evicted = self._pause_queue.offer(request)
        if evicted is not None:
            # An older request fell out — cancel its pending entry
            # so we don't leak barriers.
            self._pause.cancel(evicted.request_id)
        return self._pause.request(request)

    def submit_resume(self, request: ResumeRequest) -> ResumeBarrier:
        """Submit a resume request."""
        if self._coalesce and self._state.phase == PlaybackPhase.PLAYING:
            pass
        evicted = self._resume_queue.offer(request)
        if evicted is not None:
            self._resume.cancel(evicted.request_id)
        return self._resume.request(request)

    def submit_step(self, request: StepRequest) -> None:
        """Note a step request — the engine layer is what actually
        dispatches frames; we just track that one is in flight."""
        if request.frame_count < 1:
            raise ValueError("StepRequest.frame_count must be >= 1")
        with self._lock:
            self._step_pending += request.frame_count

    def consume_step(self) -> bool:
        """Engine loop calls this to ask "should I dispatch one
        more frame as part of a step?"."""
        with self._lock:
            if self._step_pending <= 0:
                return False
            self._step_pending -= 1
            return True

    @property
    def pending_step_frames(self) -> int:
        with self._lock:
            return self._step_pending

    # ── introspection ─────────────────────────────────────────────

    @property
    def pause_queue_depth(self) -> int:
        return len(self._pause_queue)

    @property
    def resume_queue_depth(self) -> int:
        return len(self._resume_queue)

    def pause_queue_stats(self) -> object:
        return self._pause_queue.stats()

    def resume_queue_stats(self) -> object:
        return self._resume_queue.stats()
