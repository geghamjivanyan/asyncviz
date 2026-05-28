"""Mid-level speed-coordination glue.

Composes :class:`SpeedDispatch` + :class:`SpeedClockCoordinator` +
:class:`SpeedTransitionEngine` into one cohesive layer. The
top-level :class:`ReplaySpeedController` (facade) wraps this with
ergonomic helpers (presets, default restore, drift sampling).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field

from asyncviz.replay.runtime.speed.models.speed_phase import (
    SpeedPhaseSnapshot,
)
from asyncviz.replay.runtime.speed.models.speed_request import (
    SpeedChangeRequest,
    SpeedChangeResult,
)
from asyncviz.replay.runtime.speed.replay_speed_clock import (
    DriftSample,
    SpeedClockCoordinator,
)
from asyncviz.replay.runtime.speed.replay_speed_dispatch import SpeedDispatch
from asyncviz.replay.runtime.speed.replay_speed_observability import (
    get_speed_metrics,
)
from asyncviz.replay.runtime.speed.replay_speed_state import (
    SpeedListener,
    SpeedStateHolder,
)
from asyncviz.replay.runtime.speed.replay_speed_tracing import (
    record_speed_trace,
)

SpeedChangeListener = Callable[[SpeedChangeResult], None]


@dataclass(slots=True)
class SpeedCoordination:
    """Glue layer."""

    dispatch: SpeedDispatch
    clock: SpeedClockCoordinator
    state: SpeedStateHolder
    listeners: list[SpeedChangeListener] = field(default_factory=list)

    def submit(self, request: SpeedChangeRequest) -> SpeedChangeResult:
        """Push a request through dispatch + fan the result out to
        listeners."""
        result = self.dispatch.submit(request)
        listeners = tuple(self.listeners)
        for listener in listeners:
            with suppress(Exception):
                listener(result)
        return result

    def sample_drift(self) -> DriftSample:
        sample = self.clock.sample_drift()
        get_speed_metrics().record_drift_sample(sample.drift_ns)
        record_speed_trace("drift-sample", f"drift_ns={sample.drift_ns}")
        return sample

    def subscribe_change(self, listener: SpeedChangeListener) -> Callable[[], None]:
        self.listeners.append(listener)

        def _unsubscribe() -> None:
            if listener in self.listeners:
                self.listeners.remove(listener)

        return _unsubscribe

    def subscribe_phase(self, listener: SpeedListener) -> Callable[[], None]:
        return self.state.subscribe(listener)

    @property
    def phase_snapshot(self) -> SpeedPhaseSnapshot:
        return self.state.snapshot

    def refresh_clock_anchor_from_seek(self, virtual_ns: int) -> None:
        """Notify the coordinator that an external seek re-anchored
        the clock — keeps drift samples honest."""
        self.clock.re_anchor_from_seek(virtual_ns)
        record_speed_trace("anchor-refreshed", f"virtual_ns={virtual_ns}")
