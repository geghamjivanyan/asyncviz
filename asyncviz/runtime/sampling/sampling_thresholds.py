"""Threshold-driven policy adapters.

Specialized policies that compose with :class:`DefaultSamplingPolicy`:

* :class:`NeverDropPolicy` — wraps another policy and forces
  retention for a configured event-type allowlist.
* :class:`CappedRatePolicy` — wraps another policy and overrides
  retention to a fixed rate regardless of priority.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.runtime.sampling.models.sampling_decision import (
    SamplingDecision,
)
from asyncviz.runtime.sampling.models.sampling_priority import (
    SamplingPriority,
)
from asyncviz.runtime.sampling.sampling_policy import SamplingPolicy
from asyncviz.runtime.sampling.utils.hashing import (
    BUCKET_COUNT,
    deterministic_bucket,
)


@dataclass(slots=True)
class NeverDropPolicy:
    """Force retention for a configured set of event types."""

    inner: SamplingPolicy
    never_drop_event_types: frozenset[str]

    def decide(
        self,
        *,
        event_type: str,
        priority: SamplingPriority,
        sequence: int,
        seed: int,
        over_budget: bool,
        overload: bool,
    ) -> SamplingDecision:
        if event_type in self.never_drop_event_types:
            bucket = deterministic_bucket(event_type, sequence, seed=seed)
            return SamplingDecision(
                retain=True,
                priority=priority,
                reason="never-drop-event-type",
                sequence=sequence,
                bucket=bucket,
            )
        return self.inner.decide(
            event_type=event_type,
            priority=priority,
            sequence=sequence,
            seed=seed,
            over_budget=over_budget,
            overload=overload,
        )


@dataclass(slots=True)
class CappedRatePolicy:
    """Override an inner policy's rate with a hard cap.

    Useful when an operator wants "no more than 10% of events
    retained regardless of priority" during a planned mitigation."""

    inner: SamplingPolicy
    cap_rate: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.cap_rate <= 1.0):
            raise ValueError("cap_rate must be in [0, 1]")

    def decide(
        self,
        *,
        event_type: str,
        priority: SamplingPriority,
        sequence: int,
        seed: int,
        over_budget: bool,
        overload: bool,
    ) -> SamplingDecision:
        inner_decision = self.inner.decide(
            event_type=event_type,
            priority=priority,
            sequence=sequence,
            seed=seed,
            over_budget=over_budget,
            overload=overload,
        )
        # Critical events always pass through.
        if priority == SamplingPriority.CRITICAL or not inner_decision.retain:
            return inner_decision
        bucket = inner_decision.bucket
        threshold = int(self.cap_rate * BUCKET_COUNT)
        if bucket < threshold:
            return inner_decision
        return SamplingDecision(
            retain=False,
            priority=priority,
            reason="dropped-by-rate",
            sequence=sequence,
            bucket=bucket,
        )
