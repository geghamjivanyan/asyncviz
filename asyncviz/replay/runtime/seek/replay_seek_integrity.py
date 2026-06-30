"""Seek invariant guards.

After every seek, the coordinator can optionally verify:

1. The reconstructed state's ``last_sequence`` matches the target.
2. The state's ``last_monotonic_ns`` is monotonic with respect to
   the previous cursor position (no time regression).
3. ``frames_replayed`` is non-negative.

Violations are surfaced as :class:`SeekIntegrityViolation` records
the coordinator counts + traces. Strict mode raises.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.seek.models.seek_request import SeekResult


class SeekIntegrityError(RuntimeError):
    """Raised when a seek integrity invariant is violated under
    strict mode."""


@dataclass(frozen=True, slots=True)
class SeekIntegrityViolation:
    """One observed breach."""

    kind: str
    """``sequence_mismatch`` / ``time_regression`` /
    ``negative_frames``."""
    detail: str


def check_seek_result(
    *,
    target_sequence: int,
    result: SeekResult,
    state: VirtualRuntimeState,
    previous_monotonic_ns: int,
    strategy: str = "best_effort",
) -> SeekIntegrityViolation | None:
    """Validate one completed seek."""
    if strategy == "exact_only" and result.landed_sequence != target_sequence:
        return SeekIntegrityViolation(
            kind="sequence_mismatch",
            detail=(
                f"target={target_sequence} landed={result.landed_sequence} (exact_only strategy)"
            ),
        )
    if state.last_sequence != result.landed_sequence and result.frames_replayed > 0:
        return SeekIntegrityViolation(
            kind="sequence_mismatch",
            detail=(
                f"state.last_sequence={state.last_sequence} != landed={result.landed_sequence}"
            ),
        )
    if result.frames_replayed < 0:
        return SeekIntegrityViolation(
            kind="negative_frames",
            detail=f"frames_replayed={result.frames_replayed}",
        )
    if result.landed_monotonic_ns < previous_monotonic_ns - 1:
        # Tolerate noise via the -1; only flag clear regressions.
        return SeekIntegrityViolation(
            kind="time_regression",
            detail=(
                f"landed_monotonic_ns={result.landed_monotonic_ns} "
                f"regresses from previous={previous_monotonic_ns}"
            ),
        )
    return None
