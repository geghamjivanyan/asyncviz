"""Rolling-window pressure budget.

Tracks events accepted + rejected in a sliding wall-clock window
so the controller can report sustained pressure rates that go
beyond instantaneous queue depth (e.g. "we shed 10k events in the
last second").
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    window_ns: int
    accepted: int
    rejected: int
    """Events refused by an offer because the bounded queue was
    full + the policy didn't make room."""
    overflowed: int
    """Events accepted only because an older item was evicted."""
    elapsed_ns: int


class BackpressureBudget:
    """Sliding-window counter — wall-clock based."""

    __slots__ = (
        "_accepted",
        "_lock",
        "_overflowed",
        "_rejected",
        "_window_ns",
        "_window_start",
    )

    def __init__(self, *, window_ns: int = 1_000_000_000) -> None:
        if window_ns < 1_000_000:
            raise ValueError("window_ns must be >= 1ms")
        self._window_ns = window_ns
        self._lock = threading.Lock()
        self._window_start = time.monotonic_ns()
        self._accepted = 0
        self._rejected = 0
        self._overflowed = 0

    def record_accepted(self) -> None:
        with self._lock:
            self._maybe_roll_locked()
            self._accepted += 1

    def record_rejected(self) -> None:
        with self._lock:
            self._maybe_roll_locked()
            self._rejected += 1

    def record_overflowed(self) -> None:
        with self._lock:
            self._maybe_roll_locked()
            self._overflowed += 1

    def snapshot(self) -> BudgetSnapshot:
        with self._lock:
            self._maybe_roll_locked()
            now = time.monotonic_ns()
            return BudgetSnapshot(
                window_ns=self._window_ns,
                accepted=self._accepted,
                rejected=self._rejected,
                overflowed=self._overflowed,
                elapsed_ns=now - self._window_start,
            )

    def reset(self) -> None:
        with self._lock:
            self._window_start = time.monotonic_ns()
            self._accepted = 0
            self._rejected = 0
            self._overflowed = 0

    def _maybe_roll_locked(self) -> None:
        now = time.monotonic_ns()
        if now - self._window_start >= self._window_ns:
            self._window_start = now
            self._accepted = 0
            self._rejected = 0
            self._overflowed = 0
