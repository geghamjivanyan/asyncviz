"""Sampling invariants.

Cheap runtime checks the optimizer + tests use to assert
correctness:

1. Critical/structural events were never dropped (audit-trail
   property).
2. Decision sequence numbers are monotonic.
3. Bucket values fall within ``[0, BUCKET_COUNT)``.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.sampling.models.sampling_decision import SamplingDecision
from asyncviz.runtime.sampling.models.sampling_priority import SamplingPriority
from asyncviz.runtime.sampling.utils.hashing import BUCKET_COUNT


class SamplingIntegrityError(RuntimeError):
    """Raised when a sampling invariant fails under strict mode."""


@dataclass(frozen=True, slots=True)
class SamplingIntegrityViolation:
    kind: str
    """``dropped_critical`` / ``dropped_structural`` /
    ``non_monotonic_sequence`` / ``bucket_out_of_range``."""
    detail: str
    sequence: int


def check_decision(
    decision: SamplingDecision,
    *,
    previous_sequence: int = 0,
) -> SamplingIntegrityViolation | None:
    """Validate one decision. Returns ``None`` when clean."""
    if not decision.retain:
        if decision.priority == SamplingPriority.CRITICAL:
            return SamplingIntegrityViolation(
                kind="dropped_critical",
                detail=(
                    f"critical event dropped via reason={decision.reason}"
                ),
                sequence=decision.sequence,
            )
        # Structural drops are only permitted when the
        # ``structural_retention`` config explicitly downgrades —
        # everything that lands here as STRUCTURAL with a drop is
        # almost certainly a bug.
        if (
            decision.priority == SamplingPriority.STRUCTURAL
            and decision.reason in (
                "dropped-by-rate",
                "dropped-by-budget",
                "dropped-by-overload",
            )
        ):
            return SamplingIntegrityViolation(
                kind="dropped_structural",
                detail=(
                    f"structural event dropped via reason={decision.reason}"
                ),
                sequence=decision.sequence,
            )
    if decision.sequence <= previous_sequence:
        return SamplingIntegrityViolation(
            kind="non_monotonic_sequence",
            detail=(
                f"decision sequence {decision.sequence} is not > {previous_sequence}"
            ),
            sequence=decision.sequence,
        )
    if not (0 <= decision.bucket < BUCKET_COUNT):
        return SamplingIntegrityViolation(
            kind="bucket_out_of_range",
            detail=f"bucket {decision.bucket} outside [0, {BUCKET_COUNT})",
            sequence=decision.sequence,
        )
    return None
