"""Adaptive sampling controller.

Watches the budget + an external pressure signal (websocket queue
depth, recorder backlog, custom callbacks) and toggles the
sampler's overload mode when sustained pressure is observed.

Smoothed via an exponential moving average so transient spikes
don't cause oscillation between modes.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.runtime.sampling.event_sampler import EventSampler
from asyncviz.runtime.sampling.sampling_configuration import SamplingConfig

PressureSource = Callable[[], int]
"""Callable returning the current external pressure signal — e.g.
``lambda: websocket.queue_depth()``. Higher = more pressure."""


@dataclass(slots=True)
class AdaptiveSnapshot:
    """Read-only view of the controller's current state."""

    smoothed_pressure: float
    last_pressure: int
    overload: bool
    transitions: int
    last_decision_at_ns: int = 0


class AdaptiveSamplingController:
    """EMA-smoothed pressure → sampler overload state.

    Use :meth:`tick` periodically (e.g. once per second) to feed
    the controller a fresh pressure reading. Or call
    :meth:`observe_pressure` directly with a value.
    """

    __slots__ = (
        "_config",
        "_last_decision_at_ns",
        "_last_pressure",
        "_lock",
        "_overload_high",
        "_overload_low",
        "_pressure_source",
        "_sampler",
        "_smoothed",
        "_transitions",
    )

    def __init__(
        self,
        *,
        sampler: EventSampler,
        pressure_source: PressureSource | None = None,
        config: SamplingConfig | None = None,
    ) -> None:
        cfg = config or sampler.config
        self._config = cfg
        self._sampler = sampler
        self._pressure_source = pressure_source
        self._smoothed = 0.0
        self._last_pressure = 0
        self._transitions = 0
        self._last_decision_at_ns = 0
        # Hysteresis bands so the controller doesn't flap.
        self._overload_high = cfg.budget_target_events * cfg.overload_ratio
        self._overload_low = cfg.budget_target_events * 1.0
        self._lock = threading.Lock()

    def observe_pressure(self, value: int) -> AdaptiveSnapshot:
        """Feed one pressure reading + update state."""
        if value < 0:
            value = 0
        with self._lock:
            self._last_pressure = value
            # EMA with the configured decay.
            decay = self._config.relax_decay
            self._smoothed = decay * self._smoothed + (1.0 - decay) * value
            overload_now = self._sampler.overload
            if not overload_now and self._smoothed >= self._overload_high:
                self._sampler.set_overload(True)
                self._transitions += 1
                overload_now = True
            elif overload_now and self._smoothed <= self._overload_low:
                self._sampler.set_overload(False)
                self._transitions += 1
                overload_now = False
            return AdaptiveSnapshot(
                smoothed_pressure=self._smoothed,
                last_pressure=self._last_pressure,
                overload=overload_now,
                transitions=self._transitions,
            )

    def tick(self) -> AdaptiveSnapshot | None:
        """Pull from the configured pressure source + observe."""
        if self._pressure_source is None:
            return None
        try:
            value = int(self._pressure_source())
        except Exception:
            return None
        return self.observe_pressure(value)

    def snapshot(self) -> AdaptiveSnapshot:
        with self._lock:
            return AdaptiveSnapshot(
                smoothed_pressure=self._smoothed,
                last_pressure=self._last_pressure,
                overload=self._sampler.overload,
                transitions=self._transitions,
            )

    def reset(self) -> None:
        with self._lock:
            self._smoothed = 0.0
            self._last_pressure = 0
            self._transitions = 0
            self._sampler.set_overload(False)
