"""Per-reducer execution metrics.

Distinct from :class:`asyncviz.runtime.state.metrics.StateStoreMetrics`
which tracks the store-level apply/stale/duplicate counts. These metrics
break the same totals down *by reducer name* — i.e. by event class —
so observability can answer "which event type is dominating?" without
re-instrumenting downstream.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReducerCounters:
    """Snapshot of one reducer's counters."""

    applied: int
    rejected: int
    invalid_transitions: int
    terminal_blocked: int
    last_sequence: int


@dataclass(frozen=True, slots=True)
class ReducerMetricsSnapshot:
    """Per-reducer metrics view, keyed by reducer name (== event_type string)."""

    by_reducer: dict[str, ReducerCounters]
    total_applied: int
    total_rejected: int

    def total_invalid_transitions(self) -> int:
        return sum(c.invalid_transitions for c in self.by_reducer.values())

    def total_terminal_blocked(self) -> int:
        return sum(c.terminal_blocked for c in self.by_reducer.values())


class ReducerMetrics:
    """Thread-safe per-reducer counter set."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._applied: dict[str, int] = defaultdict(int)
        self._rejected: dict[str, int] = defaultdict(int)
        self._invalid_transitions: dict[str, int] = defaultdict(int)
        self._terminal_blocked: dict[str, int] = defaultdict(int)
        self._last_sequence: dict[str, int] = defaultdict(int)

    def record_applied(self, reducer_name: str, sequence: int | None) -> None:
        with self._lock:
            self._applied[reducer_name] += 1
            if sequence is not None and sequence > self._last_sequence[reducer_name]:
                self._last_sequence[reducer_name] = sequence

    def record_rejected(
        self,
        reducer_name: str,
        *,
        invalid_transition: bool = False,
        terminal_blocked: bool = False,
    ) -> None:
        with self._lock:
            self._rejected[reducer_name] += 1
            if invalid_transition:
                self._invalid_transitions[reducer_name] += 1
            if terminal_blocked:
                self._terminal_blocked[reducer_name] += 1

    def reset(self) -> None:
        with self._lock:
            self._applied.clear()
            self._rejected.clear()
            self._invalid_transitions.clear()
            self._terminal_blocked.clear()
            self._last_sequence.clear()

    def snapshot(self) -> ReducerMetricsSnapshot:
        with self._lock:
            keys = (
                set(self._applied)
                | set(self._rejected)
                | set(self._invalid_transitions)
                | set(self._terminal_blocked)
            )
            by_reducer = {
                name: ReducerCounters(
                    applied=self._applied[name],
                    rejected=self._rejected[name],
                    invalid_transitions=self._invalid_transitions[name],
                    terminal_blocked=self._terminal_blocked[name],
                    last_sequence=self._last_sequence[name],
                )
                for name in keys
            }
            total_applied = sum(self._applied.values())
            total_rejected = sum(self._rejected.values())
        return ReducerMetricsSnapshot(
            by_reducer=by_reducer,
            total_applied=total_applied,
            total_rejected=total_rejected,
        )
