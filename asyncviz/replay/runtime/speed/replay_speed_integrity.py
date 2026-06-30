"""Invariant guards for speed transitions.

Post-transition checks:

1. Clock speed equals the resolved speed (sanity that nothing else
   stomped over our update mid-transition).
2. Anchor's virtual time is monotonic with the previous anchor.
3. New speed is within the configured ``[min, max]`` (defense in
   depth against a manual clock-poke bypassing :class:`ClampVerdict`).
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.speed.models.speed_request import SpeedTransition


class SpeedIntegrityError(RuntimeError):
    """Raised when a speed-transition invariant fails under strict
    mode."""


@dataclass(frozen=True, slots=True)
class SpeedIntegrityViolation:
    kind: str
    """``speed_mismatch`` / ``time_regression`` / ``out_of_bounds``."""
    detail: str


def check_transition(
    *,
    transition: SpeedTransition,
    observed_speed: float,
    previous_virtual_ns: int,
    min_speed: float,
    max_speed: float,
) -> SpeedIntegrityViolation | None:
    """Validate one transition after the clock has been re-anchored."""
    if abs(transition.new_speed - observed_speed) > 1e-9:
        return SpeedIntegrityViolation(
            kind="speed_mismatch",
            detail=(f"transition.new_speed={transition.new_speed} != observed={observed_speed}"),
        )
    if not (min_speed <= transition.new_speed <= max_speed):
        return SpeedIntegrityViolation(
            kind="out_of_bounds",
            detail=(f"new_speed={transition.new_speed} outside [{min_speed}, {max_speed}]"),
        )
    if transition.at_virtual_ns < previous_virtual_ns:
        return SpeedIntegrityViolation(
            kind="time_regression",
            detail=(
                f"at_virtual_ns={transition.at_virtual_ns} regresses from "
                f"previous={previous_virtual_ns}"
            ),
        )
    return None
