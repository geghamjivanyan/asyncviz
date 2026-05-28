"""Per-sampler statistics accumulator.

Tracks retention + drop counts by priority so callers can answer
"what was sampled out?" without walking every decision.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from asyncviz.runtime.sampling.models.sampling_decision import SamplingDecision
from asyncviz.runtime.sampling.models.sampling_priority import SamplingPriority


@dataclass(frozen=True, slots=True)
class SamplingStatistics:
    total_observed: int
    total_retained: int
    total_dropped: int
    retained_by_priority: dict[SamplingPriority, int] = field(
        default_factory=dict,
    )
    dropped_by_priority: dict[SamplingPriority, int] = field(
        default_factory=dict,
    )
    dropped_by_reason: dict[str, int] = field(default_factory=dict)


class SamplingStatisticsAccumulator:
    """Thread-safe accumulator over a stream of decisions."""

    __slots__ = (
        "_dropped_by_priority",
        "_dropped_by_reason",
        "_lock",
        "_retained_by_priority",
        "_total_dropped",
        "_total_observed",
        "_total_retained",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_observed = 0
        self._total_retained = 0
        self._total_dropped = 0
        self._retained_by_priority: dict[SamplingPriority, int] = {}
        self._dropped_by_priority: dict[SamplingPriority, int] = {}
        self._dropped_by_reason: dict[str, int] = {}

    def observe(self, decision: SamplingDecision) -> None:
        with self._lock:
            self._total_observed += 1
            if decision.retain:
                self._total_retained += 1
                self._retained_by_priority[decision.priority] = (
                    self._retained_by_priority.get(decision.priority, 0) + 1
                )
            else:
                self._total_dropped += 1
                self._dropped_by_priority[decision.priority] = (
                    self._dropped_by_priority.get(decision.priority, 0) + 1
                )
                self._dropped_by_reason[decision.reason] = (
                    self._dropped_by_reason.get(decision.reason, 0) + 1
                )

    def snapshot(self) -> SamplingStatistics:
        with self._lock:
            return SamplingStatistics(
                total_observed=self._total_observed,
                total_retained=self._total_retained,
                total_dropped=self._total_dropped,
                retained_by_priority=dict(self._retained_by_priority),
                dropped_by_priority=dict(self._dropped_by_priority),
                dropped_by_reason=dict(self._dropped_by_reason),
            )

    def reset(self) -> None:
        with self._lock:
            self._total_observed = 0
            self._total_retained = 0
            self._total_dropped = 0
            self._retained_by_priority.clear()
            self._dropped_by_priority.clear()
            self._dropped_by_reason.clear()
