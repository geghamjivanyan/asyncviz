"""Runtime invariant guards.

What this module checks at dispatch time:

1. *Strict ordering* — incoming frame's sequence is strictly after
   the engine cursor's ``last_sequence``. Catches reducer bugs,
   replay-stream mishaps, and any path that accidentally feeds the
   engine a frame twice.

2. *Monotonic virtual time* — incoming frame's ``monotonic_ns`` is
   non-decreasing.

3. *State sequence consistency* — after dispatch, the state's
   ``last_sequence`` must match the frame's ``sequence``.

Violations are funneled through :class:`IntegrityViolation` so the
engine can decide whether to halt (strict mode) or count + log
(default).
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.runtime.models.engine_cursor import EngineCursor
from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState


class IntegrityViolationError(RuntimeError):
    """Raised when an invariant fails under ``strict_mode``."""


@dataclass(frozen=True, slots=True)
class IntegrityViolation:
    """One observed invariant breach."""

    kind: str
    """``out_of_order`` / ``duplicate`` / ``time_regression`` /
    ``state_sequence_mismatch``."""
    detail: str


def check_pre_dispatch(
    frame: ReplayFrame, cursor: EngineCursor,
) -> IntegrityViolation | None:
    """Pre-dispatch invariants."""
    if frame.sequence == cursor.last_sequence and cursor.last_sequence != 0:
        return IntegrityViolation(
            kind="duplicate",
            detail=f"sequence {frame.sequence} already dispatched",
        )
    if frame.sequence < cursor.last_sequence:
        return IntegrityViolation(
            kind="out_of_order",
            detail=(
                f"sequence {frame.sequence} not strictly after "
                f"cursor {cursor.last_sequence}"
            ),
        )
    if frame.monotonic_ns < cursor.last_monotonic_ns:
        return IntegrityViolation(
            kind="time_regression",
            detail=(
                f"monotonic_ns {frame.monotonic_ns} regresses from "
                f"cursor {cursor.last_monotonic_ns}"
            ),
        )
    return None


def check_post_dispatch(
    frame: ReplayFrame, state: VirtualRuntimeState,
) -> IntegrityViolation | None:
    """Post-dispatch invariants."""
    if state.last_sequence != frame.sequence:
        return IntegrityViolation(
            kind="state_sequence_mismatch",
            detail=(
                f"state last_sequence={state.last_sequence} after dispatching "
                f"frame seq={frame.sequence}"
            ),
        )
    return None
