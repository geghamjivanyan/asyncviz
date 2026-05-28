"""Lifetime counters for the blocking warning emitter."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BlockingWarningMetricsSnapshot:
    outcomes_observed: int
    captures_observed: int
    groups_opened: int
    groups_recovered: int
    groups_expired: int
    transitions_opened: int
    transitions_escalated: int
    transitions_active: int
    transitions_recovered: int
    transitions_expired: int
    suppressed_by_policy: int
    suppressed_by_dedup: int
    captures_correlated: int
    captures_uncorrelated: int
    events_emitted: int
    events_dropped_backpressure: int
    events_dropped_emitter: int
    emitter_failures: int
    listener_failures: int
    reconfigurations: int
    handler_failures: int

    def to_dict(self) -> dict[str, int]:
        return {
            "outcomes_observed": self.outcomes_observed,
            "captures_observed": self.captures_observed,
            "groups_opened": self.groups_opened,
            "groups_recovered": self.groups_recovered,
            "groups_expired": self.groups_expired,
            "transitions_opened": self.transitions_opened,
            "transitions_escalated": self.transitions_escalated,
            "transitions_active": self.transitions_active,
            "transitions_recovered": self.transitions_recovered,
            "transitions_expired": self.transitions_expired,
            "suppressed_by_policy": self.suppressed_by_policy,
            "suppressed_by_dedup": self.suppressed_by_dedup,
            "captures_correlated": self.captures_correlated,
            "captures_uncorrelated": self.captures_uncorrelated,
            "events_emitted": self.events_emitted,
            "events_dropped_backpressure": self.events_dropped_backpressure,
            "events_dropped_emitter": self.events_dropped_emitter,
            "emitter_failures": self.emitter_failures,
            "listener_failures": self.listener_failures,
            "reconfigurations": self.reconfigurations,
            "handler_failures": self.handler_failures,
        }


class BlockingWarningMetrics:
    """Mutable lifetime counters; thread-safe via single lock."""

    __slots__ = (
        "_captures_correlated",
        "_captures_observed",
        "_captures_uncorrelated",
        "_emitter_failures",
        "_events_dropped_backpressure",
        "_events_dropped_emitter",
        "_events_emitted",
        "_groups_expired",
        "_groups_opened",
        "_groups_recovered",
        "_handler_failures",
        "_listener_failures",
        "_lock",
        "_outcomes_observed",
        "_reconfigurations",
        "_suppressed_by_dedup",
        "_suppressed_by_policy",
        "_transitions_active",
        "_transitions_escalated",
        "_transitions_expired",
        "_transitions_opened",
        "_transitions_recovered",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._outcomes_observed = 0
        self._captures_observed = 0
        self._groups_opened = 0
        self._groups_recovered = 0
        self._groups_expired = 0
        self._transitions_opened = 0
        self._transitions_escalated = 0
        self._transitions_active = 0
        self._transitions_recovered = 0
        self._transitions_expired = 0
        self._suppressed_by_policy = 0
        self._suppressed_by_dedup = 0
        self._captures_correlated = 0
        self._captures_uncorrelated = 0
        self._events_emitted = 0
        self._events_dropped_backpressure = 0
        self._events_dropped_emitter = 0
        self._emitter_failures = 0
        self._listener_failures = 0
        self._reconfigurations = 0
        self._handler_failures = 0

    # ── recording ────────────────────────────────────────────────────────
    def record_outcome(self) -> None:
        with self._lock:
            self._outcomes_observed += 1

    def record_capture(self) -> None:
        with self._lock:
            self._captures_observed += 1

    def record_group_opened(self) -> None:
        with self._lock:
            self._groups_opened += 1

    def record_group_recovered(self) -> None:
        with self._lock:
            self._groups_recovered += 1

    def record_group_expired(self) -> None:
        with self._lock:
            self._groups_expired += 1

    def record_transition(self, transition: str) -> None:
        with self._lock:
            if transition == "opened":
                self._transitions_opened += 1
            elif transition == "escalated":
                self._transitions_escalated += 1
            elif transition == "active":
                self._transitions_active += 1
            elif transition == "recovered":
                self._transitions_recovered += 1
            elif transition == "expired":
                self._transitions_expired += 1

    def record_suppressed_by_policy(self) -> None:
        with self._lock:
            self._suppressed_by_policy += 1

    def record_suppressed_by_dedup(self) -> None:
        with self._lock:
            self._suppressed_by_dedup += 1

    def record_capture_correlated(self) -> None:
        with self._lock:
            self._captures_correlated += 1

    def record_capture_uncorrelated(self) -> None:
        with self._lock:
            self._captures_uncorrelated += 1

    def record_event_emitted(self) -> None:
        with self._lock:
            self._events_emitted += 1

    def record_event_dropped_backpressure(self) -> None:
        with self._lock:
            self._events_dropped_backpressure += 1

    def record_event_dropped_emitter(self) -> None:
        with self._lock:
            self._events_dropped_emitter += 1

    def record_emitter_failure(self) -> None:
        with self._lock:
            self._emitter_failures += 1

    def record_listener_failure(self) -> None:
        with self._lock:
            self._listener_failures += 1

    def record_reconfiguration(self) -> None:
        with self._lock:
            self._reconfigurations += 1

    def record_handler_failure(self) -> None:
        with self._lock:
            self._handler_failures += 1

    # ── snapshot ─────────────────────────────────────────────────────────
    def snapshot(self) -> BlockingWarningMetricsSnapshot:
        with self._lock:
            return BlockingWarningMetricsSnapshot(
                outcomes_observed=self._outcomes_observed,
                captures_observed=self._captures_observed,
                groups_opened=self._groups_opened,
                groups_recovered=self._groups_recovered,
                groups_expired=self._groups_expired,
                transitions_opened=self._transitions_opened,
                transitions_escalated=self._transitions_escalated,
                transitions_active=self._transitions_active,
                transitions_recovered=self._transitions_recovered,
                transitions_expired=self._transitions_expired,
                suppressed_by_policy=self._suppressed_by_policy,
                suppressed_by_dedup=self._suppressed_by_dedup,
                captures_correlated=self._captures_correlated,
                captures_uncorrelated=self._captures_uncorrelated,
                events_emitted=self._events_emitted,
                events_dropped_backpressure=self._events_dropped_backpressure,
                events_dropped_emitter=self._events_dropped_emitter,
                emitter_failures=self._emitter_failures,
                listener_failures=self._listener_failures,
                reconfigurations=self._reconfigurations,
                handler_failures=self._handler_failures,
            )
