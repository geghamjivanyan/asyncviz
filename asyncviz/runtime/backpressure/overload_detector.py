"""Overload state-machine detector.

Aggregates pressure signals from named sources, smooths via EMA,
applies the threshold logic, and transitions through the
:class:`OverloadState` graph with hysteresis + dwell-time guards.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Callable

from asyncviz.runtime.backpressure.backpressure_configuration import (
    BackpressureConfig,
)
from asyncviz.runtime.backpressure.backpressure_thresholds import (
    lower_band,
    state_for_ratio,
)
from asyncviz.runtime.backpressure.models.overload_state import (
    OverloadSnapshot,
    OverloadState,
)
from asyncviz.runtime.backpressure.models.pressure_signal import (
    PressureSignal,
)
from asyncviz.runtime.backpressure.utils.hysteresis import ema_smooth

StateTransitionListener = Callable[[OverloadSnapshot, OverloadSnapshot], None]
"""``listener(previous, next)``."""


class OverloadDetector:
    """Pressure → state machine."""

    __slots__ = (
        "_below_lower_since_ns",
        "_config",
        "_emergency_actions",
        "_last_action_detail",
        "_last_raw",
        "_last_transition_ns",
        "_listeners",
        "_lock",
        "_signals",
        "_smoothed_ratio",
        "_state",
        "_transitions",
    )

    def __init__(self, config: BackpressureConfig) -> None:
        self._config = config
        self._signals: dict[str, PressureSignal] = {}
        self._smoothed_ratio = 0.0
        self._last_raw = 0
        self._state = OverloadState.NORMAL
        self._last_transition_ns = 0
        self._below_lower_since_ns: int | None = None
        self._transitions = 0
        self._emergency_actions = 0
        self._last_action_detail = ""
        self._listeners: list[StateTransitionListener] = []
        self._lock = threading.RLock()

    @property
    def state(self) -> OverloadState:
        with self._lock:
            return self._state

    def observe(self, signal: PressureSignal) -> OverloadSnapshot:
        """Feed one pressure signal + return the new state snapshot."""
        with self._lock:
            self._signals[signal.source] = signal
            self._last_raw = signal.value
            ratio = self._compute_aggregate_ratio_locked()
            self._smoothed_ratio = ema_smooth(
                self._smoothed_ratio,
                ratio,
                decay=self._config.degrade_decay,
            )
            return self._maybe_transition_locked()

    def _compute_aggregate_ratio_locked(self) -> float:
        # Aggregate = max of any per-channel ratio (pessimistic).
        # The most-pressured subsystem drives the global state.
        if not self._signals:
            return 0.0
        return max(signal.ratio for signal in self._signals.values())

    def _maybe_transition_locked(self) -> OverloadSnapshot:
        proposed = state_for_ratio(
            self._smoothed_ratio,
            config=self._config,
        )
        previous = self._state
        next_state = previous
        now = time.monotonic_ns()
        if proposed > previous:
            # Upgrade fires immediately — overload doesn't wait.
            next_state = proposed
            self._below_lower_since_ns = None
        elif proposed < previous:
            # Downgrade requires dwell time below the lower band.
            band = lower_band(previous, config=self._config)
            if self._smoothed_ratio < band:
                if self._below_lower_since_ns is None:
                    self._below_lower_since_ns = now
                elapsed = now - self._below_lower_since_ns
                if elapsed >= self._config.recovery_hold_ns:
                    next_state = proposed
                    self._below_lower_since_ns = None
            else:
                self._below_lower_since_ns = None
        else:
            # Same proposed state — reset the timer.
            if proposed == previous:
                pass
            self._below_lower_since_ns = None

        snapshot = OverloadSnapshot(
            state=next_state,
            pressure_ratio=self._smoothed_ratio,
            raw_pressure=self._last_raw,
            last_transition_at_ns=self._last_transition_ns,
            transitions=self._transitions,
            emergency_actions_taken=self._emergency_actions,
            last_action_detail=self._last_action_detail,
        )
        if next_state != previous:
            self._transitions += 1
            self._last_transition_ns = now
            self._state = next_state
            if next_state == OverloadState.EMERGENCY:
                self._emergency_actions += 1
            snapshot = OverloadSnapshot(
                state=next_state,
                pressure_ratio=self._smoothed_ratio,
                raw_pressure=self._last_raw,
                last_transition_at_ns=self._last_transition_ns,
                transitions=self._transitions,
                emergency_actions_taken=self._emergency_actions,
                last_action_detail=self._last_action_detail,
            )
            previous_snapshot = OverloadSnapshot(
                state=previous,
                pressure_ratio=self._smoothed_ratio,
                raw_pressure=self._last_raw,
                last_transition_at_ns=self._last_transition_ns,
                transitions=self._transitions - 1,
                emergency_actions_taken=self._emergency_actions,
                last_action_detail=self._last_action_detail,
            )
            listeners = tuple(self._listeners)
        else:
            listeners = ()
            previous_snapshot = snapshot

        for listener in listeners:
            with contextlib.suppress(Exception):
                listener(previous_snapshot, snapshot)
        return snapshot

    def snapshot(self) -> OverloadSnapshot:
        with self._lock:
            return OverloadSnapshot(
                state=self._state,
                pressure_ratio=self._smoothed_ratio,
                raw_pressure=self._last_raw,
                last_transition_at_ns=self._last_transition_ns,
                transitions=self._transitions,
                emergency_actions_taken=self._emergency_actions,
                last_action_detail=self._last_action_detail,
            )

    def subscribe(
        self,
        listener: StateTransitionListener,
    ) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return _unsubscribe

    def record_action_detail(self, detail: str) -> None:
        with self._lock:
            self._last_action_detail = detail

    def reset(self) -> None:
        with self._lock:
            self._signals.clear()
            self._smoothed_ratio = 0.0
            self._last_raw = 0
            self._state = OverloadState.NORMAL
            self._last_transition_ns = 0
            self._below_lower_since_ns = None
            self._transitions = 0
            self._emergency_actions = 0
            self._last_action_detail = ""
