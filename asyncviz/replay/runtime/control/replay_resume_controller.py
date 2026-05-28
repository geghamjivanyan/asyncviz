"""Resume controller — owns the resume side of coordination.

Symmetric to :class:`PauseController`. Accepts resume requests,
re-anchors the clock, opens the gate, transitions the state holder
through ``resuming → playing``, and resolves any awaiting barrier.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.replay.runtime.control.models.pause_request import ResumeRequest
from asyncviz.replay.runtime.control.models.playback_phase import (
    PlaybackPhase,
    PlaybackPhaseSnapshot,
)
from asyncviz.replay.runtime.control.replay_clock_coordination import (
    ClockCoordinator,
)
from asyncviz.replay.runtime.control.replay_playback_gate import (
    ReplayPlaybackGate,
)
from asyncviz.replay.runtime.control.replay_playback_observability import (
    get_coordination_metrics,
)
from asyncviz.replay.runtime.control.replay_playback_state import (
    ReplayPlaybackStateHolder,
)
from asyncviz.replay.runtime.control.replay_playback_tracing import (
    record_coordination_trace,
)
from asyncviz.replay.runtime.control.replay_resume_barrier import ResumeBarrier
from asyncviz.replay.runtime.control.replay_transition_guard import (
    check_transition,
)


@dataclass(slots=True)
class _PendingResume:
    request: ResumeRequest
    barrier: ResumeBarrier


class ResumeController:
    """Coordination-layer resume manager."""

    __slots__ = ("_clock", "_gate", "_lock", "_pending", "_state", "_strict")

    def __init__(
        self,
        *,
        state: ReplayPlaybackStateHolder,
        gate: ReplayPlaybackGate,
        clock: ClockCoordinator,
        strict: bool = True,
    ) -> None:
        self._state = state
        self._gate = gate
        self._clock = clock
        self._strict = strict
        self._lock = threading.RLock()
        self._pending: dict[int, _PendingResume] = {}

    def request(self, request: ResumeRequest) -> ResumeBarrier:
        """Accept a resume request. Returns a barrier the caller can
        ``await``."""
        barrier = ResumeBarrier(request.request_id)
        with self._lock:
            self._pending[request.request_id] = _PendingResume(request, barrier)
        self._finalize_resume(request)
        return barrier

    def _finalize_resume(self, request: ResumeRequest) -> None:
        current = self._state.snapshot
        # No-op when already playing.
        if current.phase == PlaybackPhase.PLAYING:
            self._resolve(request.request_id, current)
            return
        verdict = check_transition(current.phase, PlaybackPhase.RESUMING)
        if not verdict.allowed:
            if self._strict:
                verdict.raise_if_illegal()
            return
        resuming_snapshot = PlaybackPhaseSnapshot(
            phase=PlaybackPhase.RESUMING,
            last_sequence=current.last_sequence,
            last_monotonic_ns=current.last_monotonic_ns,
            pause_request_id=current.pause_request_id,
            resume_request_id=request.request_id,
            error_detail=current.error_detail,
        )
        self._state.transition_to(resuming_snapshot)
        # Re-anchor the clock + open the gate.
        self._clock.resume()
        self._gate.open()
        playing_snapshot = PlaybackPhaseSnapshot(
            phase=PlaybackPhase.PLAYING,
            last_sequence=current.last_sequence,
            last_monotonic_ns=current.last_monotonic_ns,
            pause_request_id=current.pause_request_id,
            resume_request_id=request.request_id,
            error_detail=current.error_detail,
        )
        self._state.transition_to(playing_snapshot)
        self._resolve(request.request_id, playing_snapshot)

    def _resolve(
        self, request_id: int, snapshot: PlaybackPhaseSnapshot,
    ) -> None:
        with self._lock:
            entry = self._pending.pop(request_id, None)
        if entry is None:
            return
        resolution = entry.barrier.resolve(
            resumed_at_sequence=snapshot.last_sequence,
            resumed_at_monotonic_ns=snapshot.last_monotonic_ns,
        )
        metrics = get_coordination_metrics()
        metrics.record_resume_completed(resolution.latency_ns)
        metrics.record_resume_barrier_resolved()
        record_coordination_trace(
            "resume-completed", f"id={request_id} seq={snapshot.last_sequence}",
        )

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def cancel(self, request_id: int) -> bool:
        with self._lock:
            return self._pending.pop(request_id, None) is not None
