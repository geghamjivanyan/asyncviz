"""Threshold logic — pressure ratio → next state.

Pure functions over a snapshot. The detector + controller route
through these so the state-transition rules live in one place.
"""

from __future__ import annotations

from asyncviz.runtime.backpressure.backpressure_configuration import (
    BackpressureConfig,
)
from asyncviz.runtime.backpressure.models.overload_state import OverloadState


def state_for_ratio(
    ratio: float, *, config: BackpressureConfig,
) -> OverloadState:
    """Map a smoothed pressure ratio to the corresponding state."""
    if ratio >= config.emergency_threshold:
        return OverloadState.EMERGENCY
    if ratio >= config.overload_threshold:
        return OverloadState.OVERLOAD
    if ratio >= config.elevated_threshold:
        return OverloadState.ELEVATED
    return OverloadState.NORMAL


def is_upgrade(previous: OverloadState, next_state: OverloadState) -> bool:
    return next_state > previous


def is_downgrade(previous: OverloadState, next_state: OverloadState) -> bool:
    return next_state < previous


def lower_band(state: OverloadState, *, config: BackpressureConfig) -> float:
    """Lower-band threshold the state must drop *below* before
    transitioning down. Used to enforce hysteresis — a downgrade
    requires pressure below the *previous* tier's threshold, not
    just below the current tier's threshold."""
    if state == OverloadState.EMERGENCY:
        return config.overload_threshold
    if state == OverloadState.OVERLOAD:
        return config.elevated_threshold
    if state == OverloadState.ELEVATED:
        return config.elevated_threshold * 0.75
    return 0.0
