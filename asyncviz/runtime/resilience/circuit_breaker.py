"""Bounded, deterministic circuit breaker.

Implements the three-state model:

* **closed** — requests flow; failures accumulate in a sliding
  time-window.
* **open** — requests short-circuit immediately. After
  ``open_duration_s`` elapses, the breaker transitions to
  ``half_open``.
* **half_open** — a bounded number of probe requests are admitted.
  Each one either closes the breaker (on success) or trips it
  again (on failure).

The breaker is single-process + does not own a clock. The caller
supplies a monotonic-ns timestamp on each event — this keeps the
implementation deterministic + makes tests easy.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from asyncviz.runtime.resilience.isolation_configuration import SubsystemPolicy
from asyncviz.runtime.resilience.models.breaker_state import BreakerState


@dataclass(frozen=True, slots=True)
class BreakerSnapshot:
    state: BreakerState
    failures_in_window: int
    successes_since_open: int
    trips: int
    transitions: int
    opened_at_ns: int
    last_failure_at_ns: int
    last_success_at_ns: int


class CircuitBreaker:
    """Thread-safe circuit breaker."""

    __slots__ = (
        "_failures",
        "_half_open_probes_remaining",
        "_last_failure_ns",
        "_last_success_ns",
        "_lock",
        "_name",
        "_opened_at_ns",
        "_policy",
        "_state",
        "_successes_since_open",
        "_transitions",
        "_trips",
    )

    def __init__(self, name: str, policy: SubsystemPolicy) -> None:
        self._name = name
        self._policy = policy
        self._lock = threading.Lock()
        self._state = BreakerState.CLOSED
        self._failures: deque[int] = deque()
        self._half_open_probes_remaining = policy.half_open_probes
        self._opened_at_ns = 0
        self._last_failure_ns = 0
        self._last_success_ns = 0
        self._trips = 0
        self._transitions = 0
        self._successes_since_open = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def policy(self) -> SubsystemPolicy:
        return self._policy

    @property
    def state(self) -> BreakerState:
        with self._lock:
            return self._state

    def allow_request(self, *, now_ns: int | None = None) -> bool:
        """Decide whether a fresh request should be admitted."""
        when = now_ns if now_ns is not None else time.monotonic_ns()
        with self._lock:
            self._maybe_reopen_probe_locked(when)
            if self._state == BreakerState.OPEN:
                return False
            if self._state == BreakerState.HALF_OPEN:
                if self._half_open_probes_remaining <= 0:
                    return False
                self._half_open_probes_remaining -= 1
                return True
            return True

    def record_success(self, *, now_ns: int | None = None) -> BreakerState:
        when = now_ns if now_ns is not None else time.monotonic_ns()
        with self._lock:
            self._last_success_ns = when
            if self._state == BreakerState.HALF_OPEN:
                self._successes_since_open += 1
                self._transition_locked(BreakerState.CLOSED, when)
                self._failures.clear()
            elif self._state == BreakerState.CLOSED:
                self._prune_window_locked(when)
            return self._state

    def record_failure(self, *, now_ns: int | None = None) -> BreakerState:
        when = now_ns if now_ns is not None else time.monotonic_ns()
        with self._lock:
            self._last_failure_ns = when
            if self._state == BreakerState.HALF_OPEN:
                self._trip_locked(when)
                return self._state
            self._failures.append(when)
            self._prune_window_locked(when)
            if len(self._failures) >= self._policy.failure_threshold:
                self._trip_locked(when)
            return self._state

    def force_open(self, *, now_ns: int | None = None) -> None:
        when = now_ns if now_ns is not None else time.monotonic_ns()
        with self._lock:
            self._trip_locked(when)

    def force_close(self) -> None:
        """Operator hook — slam the breaker closed."""
        when = time.monotonic_ns()
        with self._lock:
            if self._state != BreakerState.CLOSED:
                self._transition_locked(BreakerState.CLOSED, when)
            self._failures.clear()
            self._half_open_probes_remaining = self._policy.half_open_probes

    def reset(self) -> None:
        with self._lock:
            self._state = BreakerState.CLOSED
            self._failures.clear()
            self._half_open_probes_remaining = self._policy.half_open_probes
            self._opened_at_ns = 0
            self._last_failure_ns = 0
            self._last_success_ns = 0
            self._trips = 0
            self._transitions = 0
            self._successes_since_open = 0

    def snapshot(self) -> BreakerSnapshot:
        with self._lock:
            return BreakerSnapshot(
                state=self._state,
                failures_in_window=len(self._failures),
                successes_since_open=self._successes_since_open,
                trips=self._trips,
                transitions=self._transitions,
                opened_at_ns=self._opened_at_ns,
                last_failure_at_ns=self._last_failure_ns,
                last_success_at_ns=self._last_success_ns,
            )

    # ── internals (called under lock) ─────────────────────────────

    def _maybe_reopen_probe_locked(self, when_ns: int) -> None:
        if self._state != BreakerState.OPEN:
            return
        open_duration_ns = int(self._policy.open_duration_s * 1e9)
        if when_ns - self._opened_at_ns >= open_duration_ns:
            self._transition_locked(BreakerState.HALF_OPEN, when_ns)
            self._half_open_probes_remaining = self._policy.half_open_probes
            self._successes_since_open = 0

    def _trip_locked(self, when_ns: int) -> None:
        if self._state != BreakerState.OPEN:
            self._trips += 1
            self._opened_at_ns = when_ns
            self._transition_locked(BreakerState.OPEN, when_ns)
        self._failures.clear()
        self._half_open_probes_remaining = 0

    def _transition_locked(self, target: BreakerState, when_ns: int) -> None:
        if self._state == target:
            return
        self._state = target
        self._transitions += 1
        _ = when_ns  # reserved for future per-transition timing hooks

    def _prune_window_locked(self, when_ns: int) -> None:
        window_ns = int(self._policy.failure_window_s * 1e9)
        cutoff = when_ns - window_ns
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()
