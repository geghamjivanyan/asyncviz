"""Canonical replay-speed controller (top-level façade).

    controller = ReplaySpeedController(clock=engine.clock, scheduler=engine.scheduler)
    controller.set_speed(2.0)
    controller.increase_speed()
    controller.decrease_speed()
    controller.restore_default()
    controller.snap_to_preset(controller.current_speed)
"""

from __future__ import annotations

from collections.abc import Callable

from asyncviz.replay.runtime.replay_clock import ReplayClock
from asyncviz.replay.runtime.replay_scheduler import ReplayScheduler
from asyncviz.replay.runtime.speed.models.speed_phase import (
    SpeedPhase,
    SpeedPhaseSnapshot,
)
from asyncviz.replay.runtime.speed.models.speed_profile import SpeedProfile
from asyncviz.replay.runtime.speed.models.speed_request import (
    SpeedChangeRequest,
    SpeedChangeResult,
    SpeedTransition,
)
from asyncviz.replay.runtime.speed.replay_speed_clock import (
    DriftSample,
    SpeedClockCoordinator,
)
from asyncviz.replay.runtime.speed.replay_speed_configuration import (
    ReplaySpeedConfig,
)
from asyncviz.replay.runtime.speed.replay_speed_coordination import (
    SpeedChangeListener,
    SpeedCoordination,
)
from asyncviz.replay.runtime.speed.replay_speed_diagnostics import (
    SpeedDiagnostics,
    build_speed_diagnostics,
)
from asyncviz.replay.runtime.speed.replay_speed_dispatch import SpeedDispatch
from asyncviz.replay.runtime.speed.replay_speed_observability import (
    get_speed_metrics,
)
from asyncviz.replay.runtime.speed.replay_speed_presets import (
    nearest_preset,
    next_preset,
    previous_preset,
    restore_default,
)
from asyncviz.replay.runtime.speed.replay_speed_profile import (
    profile_from_config,
)
from asyncviz.replay.runtime.speed.replay_speed_scheduler import (
    SpeedSchedulerCoordinator,
)
from asyncviz.replay.runtime.speed.replay_speed_state import (
    SpeedListener,
    SpeedStateHolder,
)
from asyncviz.replay.runtime.speed.replay_speed_tracing import (
    record_speed_trace,
)
from asyncviz.replay.runtime.speed.replay_speed_transition import (
    SpeedTransitionEngine,
)


class ReplaySpeedController:
    """Top-level coordinator façade."""

    __slots__ = (
        "_clock",
        "_config",
        "_coord",
        "_last_drift",
        "_profile",
        "_scheduler",
        "_state",
    )

    def __init__(
        self,
        *,
        clock: ReplayClock,
        scheduler: ReplayScheduler,
        config: ReplaySpeedConfig | None = None,
    ) -> None:
        cfg = config or ReplaySpeedConfig()
        self._config = cfg
        self._profile = profile_from_config(cfg)
        self._clock = SpeedClockCoordinator(clock)
        self._scheduler = SpeedSchedulerCoordinator(scheduler=scheduler)
        self._state = SpeedStateHolder(
            initial=SpeedPhaseSnapshot(
                phase=SpeedPhase.IDLE,
                current_speed=clock.speed,
                last_completed_speed=clock.speed,
            ),
            history_capacity=cfg.history_capacity,
        )
        transition_engine = SpeedTransitionEngine(
            clock=self._clock, scheduler=self._scheduler,
        )
        dispatch = SpeedDispatch(
            clock=self._clock,
            transition_engine=transition_engine,
            state=self._state,
            min_speed=cfg.min_speed,
            max_speed=cfg.max_speed,
            queue_capacity=cfg.queue_capacity,
            coalesce_repeated_requests=cfg.coalesce_repeated_requests,
            invalid_policy=cfg.invalid_speed_policy,
        )
        self._coord = SpeedCoordination(
            dispatch=dispatch, clock=self._clock, state=self._state,
        )
        self._last_drift: DriftSample | None = None

    # ── accessors ─────────────────────────────────────────────────

    @property
    def config(self) -> ReplaySpeedConfig:
        return self._config

    @property
    def profile(self) -> SpeedProfile:
        return self._profile

    @property
    def current_speed(self) -> float:
        return self._clock.current_speed

    @property
    def phase(self) -> SpeedPhaseSnapshot:
        return self._state.snapshot

    @property
    def history(self) -> tuple[SpeedTransition, ...]:
        return self._state.history()

    # ── public speed API ──────────────────────────────────────────

    def set_speed(self, speed: float, *, reason: str = "") -> SpeedChangeResult:
        request = SpeedChangeRequest(
            request_id=self._coord.dispatch.allocate_request_id(),
            target_speed=float(speed),
            reason=reason,
        )
        get_speed_metrics().record_requested()
        record_speed_trace(
            "speed-requested",
            f"id={request.request_id} target={speed}",
        )
        return self._coord.submit(request)

    def increase_speed(self) -> SpeedChangeResult:
        target = next_preset(self._profile, self.current_speed)
        record_speed_trace("preset-cycled", f"increase to={target}")
        return self.set_speed(target, reason="preset-up")

    def decrease_speed(self) -> SpeedChangeResult:
        target = previous_preset(self._profile, self.current_speed)
        record_speed_trace("preset-cycled", f"decrease to={target}")
        return self.set_speed(target, reason="preset-down")

    def snap_to_nearest_preset(self) -> SpeedChangeResult:
        target = nearest_preset(self._profile, self.current_speed)
        record_speed_trace("preset-cycled", f"snap to={target}")
        return self.set_speed(target, reason="preset-snap")

    def restore_default(self) -> SpeedChangeResult:
        target = restore_default(self._profile)
        record_speed_trace("default-restored", f"speed={target}")
        return self.set_speed(target, reason="restore-default")

    # ── drift telemetry ───────────────────────────────────────────

    def sample_drift(self) -> DriftSample:
        sample = self._coord.sample_drift()
        self._last_drift = sample
        return sample

    @property
    def last_drift_sample(self) -> DriftSample | None:
        return self._last_drift

    # ── listeners ─────────────────────────────────────────────────

    def subscribe_change(
        self, listener: SpeedChangeListener,
    ) -> Callable[[], None]:
        return self._coord.subscribe_change(listener)

    def subscribe_phase(self, listener: SpeedListener) -> Callable[[], None]:
        return self._coord.subscribe_phase(listener)

    # ── seek integration ──────────────────────────────────────────

    def refresh_clock_anchor_from_seek(self, virtual_ns: int) -> None:
        """Call after the seek coordinator re-anchors the clock so
        drift samples don't flag the seek as drift."""
        self._coord.refresh_clock_anchor_from_seek(virtual_ns)

    # ── diagnostics ───────────────────────────────────────────────

    def diagnostics(self, *, trace_limit: int = 32) -> SpeedDiagnostics:
        return build_speed_diagnostics(
            self._state.snapshot,
            self._profile,
            self._coord.dispatch.queue_stats(),
            self._state.history(),
            last_drift_sample=self._last_drift,
            history_limit=self._config.history_capacity,
            trace_limit=trace_limit,
        )
