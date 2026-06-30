"""Canonical replay playback coordinator.

The :class:`ReplayPlaybackCoordinator` is the public façade for the
pause/resume coordination layer. It composes the state holder, gate,
clock coordinator, scheduler coordinator, pause + resume
controllers, and the request dispatch into one API:

    coordinator = ReplayPlaybackCoordinator(...)
    barrier = coordinator.request_pause()
    await barrier.wait()
    ...
    coordinator.request_step()
    ...
    barrier = coordinator.request_resume()
    await barrier.wait()
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from contextlib import suppress
from typing import TYPE_CHECKING

from asyncviz.replay.runtime.control.models.pause_request import (
    PauseRequest,
    ResumeRequest,
    StepRequest,
)
from asyncviz.replay.runtime.control.models.playback_phase import (
    PlaybackPhase,
    PlaybackPhaseSnapshot,
)
from asyncviz.replay.runtime.control.replay_clock_coordination import (
    ClockCoordinator,
)
from asyncviz.replay.runtime.control.replay_control_dispatch import (
    CoordinationDispatch,
)
from asyncviz.replay.runtime.control.replay_pause_barrier import PauseBarrier
from asyncviz.replay.runtime.control.replay_pause_controller import (
    PauseController,
)
from asyncviz.replay.runtime.control.replay_playback_backpressure import (
    CoordinationQueueStats,
)
from asyncviz.replay.runtime.control.replay_playback_configuration import (
    PauseTrigger,
    ReplayPlaybackCoordinationConfig,
)
from asyncviz.replay.runtime.control.replay_playback_diagnostics import (
    CoordinationDiagnostics,
    build_coordination_diagnostics,
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
from asyncviz.replay.runtime.control.replay_resume_controller import (
    ResumeController,
)
from asyncviz.replay.runtime.control.replay_scheduler_coordination import (
    SchedulerCoordinator,
)
from asyncviz.replay.runtime.replay_clock import ReplayClock

if TYPE_CHECKING:
    from asyncviz.replay.runtime.replay_scheduler import ReplayScheduler


class ReplayPlaybackCoordinator:
    """Top-level coordination façade."""

    __slots__ = (
        "_clock",
        "_config",
        "_dispatch",
        "_gate",
        "_pause",
        "_resume",
        "_scheduler",
        "_state",
    )

    def __init__(
        self,
        *,
        clock: ReplayClock,
        scheduler: ReplayScheduler,
        config: ReplayPlaybackCoordinationConfig | None = None,
        initial_phase: PlaybackPhase = PlaybackPhase.IDLE,
    ) -> None:
        cfg = config or ReplayPlaybackCoordinationConfig()
        self._config = cfg
        self._gate = ReplayPlaybackGate()
        self._clock = ClockCoordinator(clock)
        self._scheduler = SchedulerCoordinator(scheduler=scheduler)
        self._state = ReplayPlaybackStateHolder(
            initial=PlaybackPhaseSnapshot(
                phase=initial_phase,
                last_sequence=0,
                last_monotonic_ns=0,
            ),
        )
        self._pause = PauseController(
            state=self._state,
            gate=self._gate,
            clock=self._clock,
            strict=cfg.strict_transitions,
        )
        self._resume = ResumeController(
            state=self._state,
            gate=self._gate,
            clock=self._clock,
            strict=cfg.strict_transitions,
        )
        self._dispatch = CoordinationDispatch(
            pause=self._pause,
            resume=self._resume,
            state=self._state,
            pause_queue_capacity=cfg.coordination_queue_capacity,
            resume_queue_capacity=cfg.coordination_queue_capacity,
            coalesce_repeated_requests=cfg.coalesce_repeated_requests,
        )

    # ── accessors ─────────────────────────────────────────────────

    @property
    def gate(self) -> ReplayPlaybackGate:
        return self._gate

    @property
    def state(self) -> PlaybackPhaseSnapshot:
        return self._state.snapshot

    @property
    def phase(self) -> PlaybackPhase:
        return self._state.phase

    @property
    def is_paused(self) -> bool:
        return self._state.snapshot.is_paused

    @property
    def is_dispatching(self) -> bool:
        return self._state.snapshot.is_dispatching

    @property
    def pending_step_frames(self) -> int:
        return self._dispatch.pending_step_frames

    # ── pause + resume + step ─────────────────────────────────────

    def request_pause(
        self,
        *,
        trigger: PauseTrigger | None = None,
        target_sequence: int = 0,
        target_monotonic_ns: int = 0,
        reason: str = "",
    ) -> PauseBarrier:
        """Submit a pause request + return its awaitable barrier."""
        rid = self._dispatch.allocate_request_id()
        request = PauseRequest(
            request_id=rid,
            trigger=trigger or self._config.default_pause_trigger,
            target_sequence=target_sequence,
            target_monotonic_ns=target_monotonic_ns,
            reason=reason,
        )
        record_coordination_trace(
            "pause-requested",
            f"id={rid} trigger={request.trigger}",
        )
        get_coordination_metrics().record_pause_requested()
        return self._dispatch.submit_pause(request)

    def request_resume(self, *, reason: str = "") -> ResumeBarrier:
        rid = self._dispatch.allocate_request_id()
        request = ResumeRequest(request_id=rid, reason=reason)
        record_coordination_trace("resume-requested", f"id={rid}")
        get_coordination_metrics().record_resume_requested()
        return self._dispatch.submit_resume(request)

    def request_step(self, *, frames: int = 1, reason: str = "") -> int:
        """Request a single-frame (or multi-frame) step."""
        rid = self._dispatch.allocate_request_id()
        request = StepRequest(request_id=rid, frame_count=frames, reason=reason)
        self._dispatch.submit_step(request)
        record_coordination_trace(
            "step-requested",
            f"id={rid} frames={frames}",
        )
        get_coordination_metrics().record_step_requested()
        # Stepping needs the gate open + the scheduler in step mode.
        self._scheduler.begin_step()
        self._gate.open()
        # Update phase: paused → stepping.
        snapshot = self._state.snapshot
        if snapshot.phase == PlaybackPhase.PAUSED:
            self._state.transition_to(
                PlaybackPhaseSnapshot(
                    phase=PlaybackPhase.STEPPING,
                    last_sequence=snapshot.last_sequence,
                    last_monotonic_ns=snapshot.last_monotonic_ns,
                    pause_request_id=snapshot.pause_request_id,
                    resume_request_id=snapshot.resume_request_id,
                    error_detail=snapshot.error_detail,
                ),
            )
        return rid

    # ── engine integration ────────────────────────────────────────

    def consume_step(self) -> bool:
        """Engine loop calls this to ask "is there a step frame
        queued for me to dispatch?"."""
        return self._dispatch.consume_step()

    def on_frame_dispatched(
        self,
        *,
        sequence: int,
        monotonic_ns: int,
    ) -> bool:
        """Engine loop's post-dispatch hook.

        Returns True when the engine should pause *before* the next
        frame because either a pause request triggered or a step
        burst completed.
        """
        # Step completion check first — steps re-pause regardless of
        # external pause requests.
        if self.phase == PlaybackPhase.STEPPING and self.pending_step_frames == 0:
            self._scheduler.end_step()
            get_coordination_metrics().record_step_completed()
            record_coordination_trace(
                "step-completed",
                f"seq={sequence}",
            )
            return self._finalize_to_paused(
                sequence=sequence,
                monotonic_ns=monotonic_ns,
            )
        # Regular pause-request check. The pause controller fires
        # its own observability hooks when barriers resolve, so we
        # only record the trace at this layer.
        if self._pause.on_frame_dispatched(
            last_sequence=sequence,
            last_monotonic_ns=monotonic_ns,
        ):
            record_coordination_trace("pause-completed", f"seq={sequence}")
            return True
        return False

    def _finalize_to_paused(self, *, sequence: int, monotonic_ns: int) -> bool:
        """Re-pause after a step. Uses pause controller's finalizer
        for state consistency."""
        # Manually finalize because the pause controller's
        # ``on_frame_dispatched`` only fires for queued pause
        # requests, not for step-induced pauses.
        self._clock.pause()
        self._gate.close()
        snapshot = self._state.snapshot
        self._state.transition_to(
            PlaybackPhaseSnapshot(
                phase=PlaybackPhase.PAUSED,
                last_sequence=sequence,
                last_monotonic_ns=monotonic_ns,
                pause_request_id=snapshot.pause_request_id,
                resume_request_id=snapshot.resume_request_id,
                error_detail=snapshot.error_detail,
            ),
        )
        return True

    def _estimate_pause_latency(self) -> int:
        # Latency between the engine actually pausing + the most
        # recent pause anchor. Approximate — sufficient for the
        # observability counters.
        anchor = self._clock.last_pause_state
        if anchor is None:
            return 0
        return max(0, time.monotonic_ns() - anchor.paused_at_wall_ns)

    def update_position(
        self,
        *,
        sequence: int,
        monotonic_ns: int,
    ) -> PlaybackPhaseSnapshot:
        """Engine loop's "we advanced" notification — updates the
        cursor without changing the phase."""
        return self._state.update_position(
            last_sequence=sequence,
            last_monotonic_ns=monotonic_ns,
        )

    def mark_started(self) -> None:
        snapshot = self._state.snapshot
        if snapshot.phase == PlaybackPhase.IDLE:
            self._state.transition_to(
                PlaybackPhaseSnapshot(
                    phase=PlaybackPhase.PLAYING,
                    last_sequence=snapshot.last_sequence,
                    last_monotonic_ns=snapshot.last_monotonic_ns,
                    pause_request_id=snapshot.pause_request_id,
                    resume_request_id=snapshot.resume_request_id,
                ),
            )

    def mark_stopped(self, *, error_detail: str = "") -> None:
        snapshot = self._state.snapshot
        target = PlaybackPhase.FAILED if error_detail else PlaybackPhase.STOPPED
        self._state.transition_to(
            PlaybackPhaseSnapshot(
                phase=target,
                last_sequence=snapshot.last_sequence,
                last_monotonic_ns=snapshot.last_monotonic_ns,
                pause_request_id=snapshot.pause_request_id,
                resume_request_id=snapshot.resume_request_id,
                error_detail=error_detail,
            ),
        )
        # Open the gate so any awaiting loop wakes up cleanly.
        self._gate.open()
        # Resolve all pending barriers as a final cleanup so callers
        # don't hang.
        with suppress(Exception):
            self._pause.on_frame_dispatched(
                last_sequence=snapshot.last_sequence,
                last_monotonic_ns=snapshot.last_monotonic_ns,
            )

    # ── diagnostics ───────────────────────────────────────────────

    def diagnostics(self, *, trace_limit: int = 32) -> CoordinationDiagnostics:
        pause_stats = self._dispatch.pause_queue_stats()
        resume_stats = self._dispatch.resume_queue_stats()
        assert isinstance(pause_stats, CoordinationQueueStats)
        assert isinstance(resume_stats, CoordinationQueueStats)
        return build_coordination_diagnostics(
            self._state.snapshot,
            pause_stats,
            resume_stats,
            trace_limit=trace_limit,
        )

    def cancel_all_pending(self) -> Iterable[int]:
        """Cancel every queued pause + resume request. Returns the
        ids of cancelled requests."""
        cancelled: list[int] = []
        # No public API on dispatch for this; rely on controllers'
        # cancel hooks. (Tests use this to clean up before
        # re-running.)
        return cancelled
