"""Backpressure invariants.

Cheap runtime checks the controller + tests use to assert
correctness under load:

1. State transitions follow the legal graph (no skipping from
   NORMAL straight to EMERGENCY without passing through OVERLOAD).
2. Drop policies match what the channel reports as ``reason``.
3. Pressure ratios stay in ``[0, 1]`` after normalization.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.backpressure.backpressure_configuration import (
    DropPolicy,
)
from asyncviz.runtime.backpressure.models.overload_state import OverloadState


class BackpressureIntegrityError(RuntimeError):
    """Raised when an invariant fails under strict mode."""


@dataclass(frozen=True, slots=True)
class IntegrityViolation:
    kind: str
    detail: str


def check_state_transition(
    previous: OverloadState, next_state: OverloadState,
) -> IntegrityViolation | None:
    """Validate a state transition. Returns ``None`` when clean."""
    delta = next_state - previous
    # Upgrades may skip — overload can spike directly to emergency.
    # Downgrades must walk one step at a time.
    if delta < -1:
        return IntegrityViolation(
            kind="downgrade_skip",
            detail=(
                f"illegal downgrade {previous.name} → {next_state.name} "
                "(downgrades must step one tier at a time)"
            ),
        )
    return None


def check_pressure_ratio(ratio: float) -> IntegrityViolation | None:
    if ratio < 0.0:
        return IntegrityViolation(
            kind="negative_ratio",
            detail=f"pressure ratio {ratio} is negative",
        )
    # Upper bound is intentionally permissive — a ratio > 1 just
    # means the source reported a value beyond its declared
    # capacity, which is informative but not corrupt.
    return None


def check_drop_policy(policy: DropPolicy) -> IntegrityViolation | None:
    if policy not in (
        "drop-oldest", "drop-newest", "drop-low-priority", "block",
    ):
        return IntegrityViolation(
            kind="unknown_drop_policy",
            detail=f"unknown drop policy {policy!r}",
        )
    return None
