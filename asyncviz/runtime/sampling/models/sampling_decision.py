"""Sampling decision value type.

Every sample call returns one of these so the caller knows both
the verdict + the rationale (useful for diagnostics + replay
metadata)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from asyncviz.runtime.sampling.models.sampling_priority import SamplingPriority

SamplingReason = Literal[
    "off",
    "never-drop-event-type",
    "critical-priority",
    "structural-priority",
    "retained-by-rate",
    "dropped-by-rate",
    "dropped-by-budget",
    "dropped-by-overload",
    "dropped-by-backpressure",
]


@dataclass(frozen=True, slots=True)
class SamplingDecision:
    retain: bool
    priority: SamplingPriority
    reason: SamplingReason
    sequence: int
    """Sampling sequence (per-sampler monotonic counter, used for
    deterministic bucket selection)."""
    bucket: int
    """The bucket index the decision landed in — exposed for tests +
    diagnostics that want to verify determinism."""

    @property
    def dropped(self) -> bool:
        return not self.retain
