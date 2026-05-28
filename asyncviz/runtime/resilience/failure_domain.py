"""Per-subsystem failure domain.

A *failure domain* is the unit of containment: one circuit breaker,
a sliding window of recent :class:`FailureEvent`, an optional
payload-quarantine set, and the bookkeeping the manager reads.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from asyncviz.runtime.resilience.circuit_breaker import (
    BreakerSnapshot,
    CircuitBreaker,
)
from asyncviz.runtime.resilience.isolation_configuration import SubsystemPolicy
from asyncviz.runtime.resilience.models.breaker_state import BreakerState
from asyncviz.runtime.resilience.models.failure_event import FailureEvent

_HISTORY_CAPACITY = 64

FailureListener = Callable[[FailureEvent, BreakerState, BreakerState], None]
"""``listener(event, previous_state, new_state)``."""


@dataclass(frozen=True, slots=True)
class FailureDomainSnapshot:
    name: str
    breaker: BreakerSnapshot
    total_failures: int
    total_successes: int
    quarantined_payloads: tuple[str, ...]
    last_failure: FailureEvent | None
    recent_failures: tuple[FailureEvent, ...]


class FailureDomain:
    """Bookkeeping for one subsystem."""

    __slots__ = (
        "_breaker",
        "_history",
        "_last_failure",
        "_listeners",
        "_lock",
        "_name",
        "_policy",
        "_quarantine",
        "_total_failures",
        "_total_successes",
    )

    def __init__(self, name: str, policy: SubsystemPolicy) -> None:
        self._name = name
        self._policy = policy
        self._lock = threading.Lock()
        self._breaker = CircuitBreaker(name, policy)
        self._history: deque[FailureEvent] = deque(maxlen=_HISTORY_CAPACITY)
        self._quarantine: set[str] = set()
        self._total_failures = 0
        self._total_successes = 0
        self._last_failure: FailureEvent | None = None
        self._listeners: list[FailureListener] = []

    def subscribe(self, listener: FailureListener) -> Callable[[], None]:
        """Register a listener invoked on every recorded failure.

        Returns an unsubscribe callable. The listener never affects
        the domain's bookkeeping; exceptions raised inside it are
        suppressed."""
        with self._lock:
            self._listeners.append(listener)

        def _unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return _unsubscribe

    @property
    def name(self) -> str:
        return self._name

    @property
    def policy(self) -> SubsystemPolicy:
        return self._policy

    @property
    def breaker(self) -> CircuitBreaker:
        return self._breaker

    def allow_request(
        self,
        *,
        payload_kind: str = "",
        now_ns: int | None = None,
    ) -> bool:
        """Returns ``True`` when the subsystem may serve a request.

        Payload quarantine takes precedence over breaker state — a
        known-bad payload is rejected even when the breaker is closed.
        """
        if payload_kind and self._policy.quarantine_payload_kind:
            with self._lock:
                if payload_kind in self._quarantine:
                    return False
        return self._breaker.allow_request(now_ns=now_ns)

    def record_success(self, *, now_ns: int | None = None) -> BreakerState:
        with self._lock:
            self._total_successes += 1
        return self._breaker.record_success(now_ns=now_ns)

    def record_failure(self, event: FailureEvent) -> BreakerState:
        now_ns = event.at_ns or time.monotonic_ns()
        with self._lock:
            previous_state = self._breaker.state
            self._total_failures += 1
            self._history.append(event)
            self._last_failure = event
            if (
                self._policy.quarantine_payload_kind
                and event.payload_kind
                and not event.recoverable
            ):
                self._quarantine.add(event.payload_kind)
            listeners = tuple(self._listeners)
        new_state = self._breaker.record_failure(now_ns=now_ns)
        for listener in listeners:
            with contextlib.suppress(Exception):
                listener(event, previous_state, new_state)
        return new_state

    def quarantined(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._quarantine))

    def release_quarantine(self, payload_kind: str) -> bool:
        """Drop ``payload_kind`` from the quarantine set. Returns
        ``True`` when the key was present, ``False`` otherwise."""
        with self._lock:
            existed = payload_kind in self._quarantine
            self._quarantine.discard(payload_kind)
            return existed

    def is_quarantined(self, payload_kind: str) -> bool:
        with self._lock:
            return payload_kind in self._quarantine

    def snapshot(self) -> FailureDomainSnapshot:
        breaker = self._breaker.snapshot()
        with self._lock:
            return FailureDomainSnapshot(
                name=self._name,
                breaker=breaker,
                total_failures=self._total_failures,
                total_successes=self._total_successes,
                quarantined_payloads=tuple(sorted(self._quarantine)),
                last_failure=self._last_failure,
                recent_failures=tuple(self._history),
            )

    def reset(self) -> None:
        self._breaker.reset()
        with self._lock:
            self._history.clear()
            self._quarantine.clear()
            self._total_failures = 0
            self._total_successes = 0
            self._last_failure = None
