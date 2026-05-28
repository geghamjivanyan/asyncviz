"""Pause controller — owns the pause side of coordination.

Distinct from :class:`asyncviz.replay.runtime.replay_pause.PauseController`
(which is a low-level primitive). The *coordination* pause
controller:

* Tracks pending pause requests + their barriers.
* Handles every trigger flavor (``immediate``,
  ``after_current_frame``, ``at_sequence``, ``at_timestamp``).
* Coordinates with the gate, the clock, and the state holder so
  pause is observable + awaitable as one atomic step.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.replay.runtime.control.models.pause_request import PauseRequest
from asyncviz.replay.runtime.control.models.playback_phase import (
    PlaybackPhase,
    PlaybackPhaseSnapshot,
)
from asyncviz.replay.runtime.control.replay_clock_coordination import (
    ClockCoordinator,
)
from asyncviz.replay.runtime.control.replay_pause_barrier import PauseBarrier
from asyncviz.replay.runtime.control.replay_playback_gate import (
    ReplayPlaybackGate,
)
from asyncviz.replay.runtime.control.replay_playback_observability import (
    get_coordination_metrics,
)
from asyncviz.replay.runtime.control.replay_playback_state import (
    ReplayPlaybackStateHolder,
)
from asyncviz.replay.runtime.control.replay_transition_guard import (
    check_transition,
)


@dataclass(slots=True)
class _PendingPause:
    request: PauseRequest
    barrier: PauseBarrier


class PauseController:
    """Coordination-layer pause manager."""

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
        self._pending: dict[int, _PendingPause] = {}

    # ── request handling ──────────────────────────────────────────

    def request(self, request: PauseRequest) -> PauseBarrier:
        """Accept a pause request. Returns the barrier the caller
        can ``await`` to be told when pause is acknowledged."""
        barrier = PauseBarrier(request.request_id)
        with self._lock:
            self._pending[request.request_id] = _PendingPause(request, barrier)
            current = self._state.snapshot
        # For ``immediate``, transition phase to PAUSING right now
        # so the engine loop can observe + acknowledge at the next
        # frame boundary.
        if request.trigger == "immediate":
            self._begin_pausing(current, request)
        elif request.trigger == "after_current_frame":
            # Same as immediate for the gate; the playback loop
            # acknowledges at the next iteration.
            self._begin_pausing(current, request)
        # ``at_sequence`` and ``at_timestamp`` are observed lazily
        # by ``on_frame_dispatched`` — no immediate transition.
        return barrier

    def _begin_pausing(
        self,
        current: PlaybackPhaseSnapshot,
        request: PauseRequest,
    ) -> None:
        if current.phase == PlaybackPhase.PAUSED:
            # Already paused — resolve the barrier immediately.
            self._resolve_pending(request.request_id, current)
            return
        verdict = check_transition(current.phase, PlaybackPhase.PAUSING)
        if not verdict.allowed:
            if self._strict:
                verdict.raise_if_illegal()
            return
        next_snapshot = PlaybackPhaseSnapshot(
            phase=PlaybackPhase.PAUSING,
            last_sequence=current.last_sequence,
            last_monotonic_ns=current.last_monotonic_ns,
            pause_request_id=request.request_id,
            resume_request_id=current.resume_request_id,
            error_detail=current.error_detail,
        )
        self._state.transition_to(next_snapshot)
        # Close the gate so the engine's next ``wait_until_open``
        # actually blocks. Closing it here keeps the transition +
        # the gate state synchronized — there's no window where the
        # phase says paused but the gate is still open.
        self._gate.close()

    # ── engine acknowledgement ────────────────────────────────────

    def on_frame_dispatched(
        self,
        *,
        last_sequence: int,
        last_monotonic_ns: int,
    ) -> bool:
        """Called by the engine loop after dispatching a frame.

        Returns True when the engine should pause *before* the next
        frame (because either we're already pausing, or a deferred
        pause-at-sequence / pause-at-timestamp triggered now).
        """
        self._state.update_position(
            last_sequence=last_sequence, last_monotonic_ns=last_monotonic_ns,
        )
        with self._lock:
            pending = list(self._pending.values())
        triggered = False
        for entry in pending:
            req = entry.request
            if req.trigger in ("immediate", "after_current_frame") or (
                req.trigger == "at_sequence"
                and last_sequence >= req.target_sequence
            ) or (
                req.trigger == "at_timestamp"
                and last_monotonic_ns >= req.target_monotonic_ns
            ):
                triggered = True
        if not triggered:
            return False
        # Time to actually pause — flip phase to PAUSED, close gate,
        # freeze the clock, resolve every pending barrier.
        self._finalize_pause(last_sequence=last_sequence, last_monotonic_ns=last_monotonic_ns)
        return True

    def _finalize_pause(
        self, *, last_sequence: int, last_monotonic_ns: int,
    ) -> None:
        current = self._state.snapshot
        verdict = check_transition(current.phase, PlaybackPhase.PAUSED)
        if not verdict.allowed and self._strict:
            verdict.raise_if_illegal()
        self._clock.pause()
        self._gate.close()
        next_snapshot = PlaybackPhaseSnapshot(
            phase=PlaybackPhase.PAUSED,
            last_sequence=last_sequence,
            last_monotonic_ns=last_monotonic_ns,
            pause_request_id=current.pause_request_id,
            resume_request_id=current.resume_request_id,
            error_detail=current.error_detail,
        )
        self._state.transition_to(next_snapshot)
        # Resolve every pending barrier at once — fine because the
        # state machine guarantees the engine observed all of them.
        with self._lock:
            pending = list(self._pending.values())
            self._pending.clear()
        metrics = get_coordination_metrics()
        for entry in pending:
            resolution = entry.barrier.resolve(
                paused_at_sequence=last_sequence,
                paused_at_monotonic_ns=last_monotonic_ns,
            )
            metrics.record_pause_barrier_resolved()
            metrics.record_pause_completed(resolution.latency_ns)

    def _resolve_pending(
        self,
        request_id: int,
        snapshot: PlaybackPhaseSnapshot,
    ) -> None:
        with self._lock:
            entry = self._pending.pop(request_id, None)
        if entry is not None:
            entry.barrier.resolve(
                paused_at_sequence=snapshot.last_sequence,
                paused_at_monotonic_ns=snapshot.last_monotonic_ns,
            )

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def cancel(self, request_id: int) -> bool:
        """Cancel a pending request without firing its barrier."""
        with self._lock:
            return self._pending.pop(request_id, None) is not None
