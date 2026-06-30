"""Sampling policy — turns ``(event_type, priority, sequence,
budget_state)`` into a retention decision.

The default policy uses the per-priority retention rates from the
config + a deterministic bucket hash. The policy interface is
small (`should_retain`) so callers can swap in custom strategies
(temperature-based, per-runtime, ml-driven, etc.) without touching
the sampler.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from asyncviz.runtime.sampling.models.sampling_decision import (
    SamplingDecision,
    SamplingReason,
)
from asyncviz.runtime.sampling.models.sampling_priority import (
    SamplingPriority,
)
from asyncviz.runtime.sampling.sampling_configuration import SamplingConfig
from asyncviz.runtime.sampling.utils.hashing import (
    BUCKET_COUNT,
    deterministic_bucket,
)


@runtime_checkable
class SamplingPolicy(Protocol):
    """Tiny contract — one decision method."""

    def decide(
        self,
        *,
        event_type: str,
        priority: SamplingPriority,
        sequence: int,
        seed: int,
        over_budget: bool,
        overload: bool,
    ) -> SamplingDecision: ...


@dataclass(slots=True)
class DefaultSamplingPolicy:
    """Per-priority retention with deterministic-hash sampling."""

    config: SamplingConfig

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
        bucket = deterministic_bucket(event_type, sequence, seed=seed)

        # Off-mode is the pass-through path.
        if self.config.mode == "off":
            return SamplingDecision(
                retain=True,
                priority=priority,
                reason="off",
                sequence=sequence,
                bucket=bucket,
            )

        # Critical events are always retained.
        if priority == SamplingPriority.CRITICAL:
            return SamplingDecision(
                retain=True,
                priority=priority,
                reason="critical-priority",
                sequence=sequence,
                bucket=bucket,
            )
        # Structural events are retained unless explicitly demoted
        # (e.g. structural_retention < 1.0 under aggressive policy).
        if priority == SamplingPriority.STRUCTURAL and self.config.structural_retention >= 1.0:
            return SamplingDecision(
                retain=True,
                priority=priority,
                reason="structural-priority",
                sequence=sequence,
                bucket=bucket,
            )

        # Hard backpressure — budget exhausted + overload.
        if over_budget and overload and priority < SamplingPriority.STRUCTURAL:
            floor = max(self.config.overload_floor, 0.0)
            if _bucket_below_rate(bucket, floor):
                return SamplingDecision(
                    retain=True,
                    priority=priority,
                    reason="retained-by-rate",
                    sequence=sequence,
                    bucket=bucket,
                )
            return SamplingDecision(
                retain=False,
                priority=priority,
                reason="dropped-by-overload",
                sequence=sequence,
                bucket=bucket,
            )

        # Budget-only drop (no overload yet): retain proportional
        # to a softer rate.
        if over_budget and priority < SamplingPriority.STRUCTURAL:
            relaxed_rate = _rate_for_priority(self.config, priority) * 0.5
            if _bucket_below_rate(bucket, relaxed_rate):
                return SamplingDecision(
                    retain=True,
                    priority=priority,
                    reason="retained-by-rate",
                    sequence=sequence,
                    bucket=bucket,
                )
            return SamplingDecision(
                retain=False,
                priority=priority,
                reason="dropped-by-budget",
                sequence=sequence,
                bucket=bucket,
            )

        # Normal path — per-priority rate.
        rate = _rate_for_priority(self.config, priority)
        if _bucket_below_rate(bucket, rate):
            return SamplingDecision(
                retain=True,
                priority=priority,
                reason="retained-by-rate",
                sequence=sequence,
                bucket=bucket,
            )
        return SamplingDecision(
            retain=False,
            priority=priority,
            reason="dropped-by-rate",
            sequence=sequence,
            bucket=bucket,
        )


def _rate_for_priority(
    config: SamplingConfig,
    priority: SamplingPriority,
) -> float:
    if priority == SamplingPriority.CRITICAL:
        return min(1.0, config.critical_retention)
    if priority == SamplingPriority.STRUCTURAL:
        return min(1.0, config.structural_retention)
    if priority == SamplingPriority.STATE:
        return config.state_retention
    return config.delta_retention


def _bucket_below_rate(bucket: int, rate: float) -> bool:
    """Bucket-membership check.

    A bucket is "below rate" when ``bucket < rate * BUCKET_COUNT``.
    For ``rate=0.1`` and ``BUCKET_COUNT=1024``, that's the first
    ~102 buckets — a deterministic 10% sample.
    """
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    threshold = int(rate * BUCKET_COUNT)
    return bucket < threshold


__all__ = [
    "DefaultSamplingPolicy",
    "SamplingPolicy",
    "SamplingReason",
]
