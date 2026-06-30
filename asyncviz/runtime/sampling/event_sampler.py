"""Canonical EventSampler.

Composes the policy + budget + adaptive controller into one
public API:

    sampler = EventSampler(config=default_config())
    decision = sampler.evaluate(event_type, sequence)
    if decision.retain:
        emit(event)
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from typing import Any

from asyncviz.runtime.sampling.models.sampling_decision import (
    SamplingDecision,
)
from asyncviz.runtime.sampling.models.sampling_priority import (
    SamplingPriority,
    classify_event_priority,
)
from asyncviz.runtime.sampling.sampling_budget import (
    BudgetSnapshot,
    SamplingBudget,
)
from asyncviz.runtime.sampling.sampling_configuration import (
    SamplingConfig,
    default_config,
)
from asyncviz.runtime.sampling.sampling_policy import (
    DefaultSamplingPolicy,
    SamplingPolicy,
)
from asyncviz.runtime.sampling.sampling_thresholds import NeverDropPolicy


class EventSampler:
    """Top-level sampler façade."""

    __slots__ = (
        "_budget",
        "_config",
        "_lock",
        "_overload",
        "_policy",
        "_sequence",
    )

    def __init__(
        self,
        config: SamplingConfig | None = None,
        *,
        policy: SamplingPolicy | None = None,
    ) -> None:
        cfg = config or default_config()
        self._config = cfg
        base_policy = policy or DefaultSamplingPolicy(config=cfg)
        # Wrap in NeverDropPolicy if the config supplied an allowlist.
        if cfg.never_drop_event_types:
            base_policy = NeverDropPolicy(
                inner=base_policy,
                never_drop_event_types=frozenset(cfg.never_drop_event_types),
            )
        self._policy = base_policy
        self._budget = SamplingBudget(
            target_events=cfg.budget_target_events,
            window_ns=cfg.budget_window_ns,
        )
        self._lock = threading.Lock()
        self._sequence = 0
        self._overload = False

    @property
    def config(self) -> SamplingConfig:
        return self._config

    @property
    def policy(self) -> SamplingPolicy:
        return self._policy

    @property
    def budget(self) -> SamplingBudget:
        return self._budget

    def set_overload(self, overload: bool) -> None:
        """Adaptive controller toggles this — when True, the policy
        falls back to the overload floor."""
        with self._lock:
            self._overload = overload

    @property
    def overload(self) -> bool:
        with self._lock:
            return self._overload

    # ── decision API ──────────────────────────────────────────────

    def evaluate(
        self,
        event_type: str,
        *,
        priority: SamplingPriority | None = None,
    ) -> SamplingDecision:
        """Sample one event. Returns a structured decision."""
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
            overload = self._overload
        resolved_priority = priority or classify_event_priority(event_type)
        decision = self._policy.decide(
            event_type=event_type,
            priority=resolved_priority,
            sequence=sequence,
            seed=self._config.deterministic_seed,
            over_budget=self._budget.over_budget,
            overload=overload,
        )
        if decision.retain:
            self._budget.record_retained()
        return decision

    def evaluate_many(
        self,
        event_types: Iterable[str],
    ) -> list[SamplingDecision]:
        return [self.evaluate(et) for et in event_types]

    def should_retain(
        self,
        event_type: str,
        *,
        priority: SamplingPriority | None = None,
    ) -> bool:
        return self.evaluate(event_type, priority=priority).retain

    # ── inspection ────────────────────────────────────────────────

    def budget_snapshot(self) -> BudgetSnapshot:
        return self._budget.snapshot()

    def reset(self) -> None:
        """Reset budget + sequence counter. Used between recording
        sessions in tests + by the adaptive controller after a
        policy change."""
        with self._lock:
            self._sequence = 0
            self._overload = False
        self._budget.reset()

    # ── attach context (for downstream tracking) ──────────────────

    def annotate(self, decision: SamplingDecision) -> dict[str, Any]:
        """Build a JSON-safe annotation suitable for embedding in a
        sampling marker or websocket payload."""
        return {
            "retain": decision.retain,
            "priority": int(decision.priority),
            "reason": decision.reason,
            "sequence": decision.sequence,
            "bucket": decision.bucket,
        }
