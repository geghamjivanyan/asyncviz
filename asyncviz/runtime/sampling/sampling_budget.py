"""Sliding-window event budget.

Counts retained events per ``budget_window_ns`` and reports
``over_budget`` when the count exceeds the configured target.
Resets on window close.

The budget is a *retention* counter, not a *throughput* counter —
dropped events don't count against it. This means a runtime that
emits 1M events/sec but retains 1% can still keep ~10k retained
events/sec without tripping the budget.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    target_events: int
    window_ns: int
    current_retained: int
    elapsed_ns: int
    over_budget: bool


class SamplingBudget:
    """Sliding-window retention budget."""

    __slots__ = (
        "_current",
        "_lock",
        "_target",
        "_window_ns",
        "_window_start",
    )

    def __init__(
        self,
        *,
        target_events: int,
        window_ns: int,
    ) -> None:
        if target_events < 1:
            raise ValueError("target_events must be >= 1")
        if window_ns < 1_000_000:
            raise ValueError("window_ns must be >= 1ms")
        self._target = target_events
        self._window_ns = window_ns
        self._lock = threading.Lock()
        self._window_start = time.monotonic_ns()
        self._current = 0

    def record_retained(self) -> None:
        with self._lock:
            self._maybe_roll_locked()
            self._current += 1

    @property
    def over_budget(self) -> bool:
        with self._lock:
            self._maybe_roll_locked()
            return self._current > self._target

    def snapshot(self) -> BudgetSnapshot:
        with self._lock:
            self._maybe_roll_locked()
            now = time.monotonic_ns()
            return BudgetSnapshot(
                target_events=self._target,
                window_ns=self._window_ns,
                current_retained=self._current,
                elapsed_ns=now - self._window_start,
                over_budget=self._current > self._target,
            )

    def reset(self) -> None:
        with self._lock:
            self._window_start = time.monotonic_ns()
            self._current = 0

    def _maybe_roll_locked(self) -> None:
        now = time.monotonic_ns()
        if now - self._window_start >= self._window_ns:
            self._window_start = now
            self._current = 0
