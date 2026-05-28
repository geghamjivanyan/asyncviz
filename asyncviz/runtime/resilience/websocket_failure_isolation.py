"""Websocket-subsystem failure isolation adapter.

Per-subscriber isolation is delegated to the manager's failure
domain: a misbehaving subscriber accumulates failures + trips its
own breaker without dragging the broader websocket fanout down.

The adapter keeps a *per-subscriber* breaker derived from a single
shared domain (so the manager's metrics still aggregate
sensibly) — operators that want a fully isolated breaker per
subscriber should register one subsystem per subscriber.
"""

from __future__ import annotations

import threading

from asyncviz.runtime.resilience.failure_domain import FailureDomain
from asyncviz.runtime.resilience.subsystem_boundary import (
    AsyncSubsystemBoundary,
    SubsystemBoundary,
)


class WebsocketFailureIsolation:
    """Helpers for isolating per-subscriber + global websocket
    failures."""

    __slots__ = ("_disconnected", "_domain", "_lock")

    def __init__(self, domain: FailureDomain) -> None:
        self._domain = domain
        self._lock = threading.Lock()
        self._disconnected: set[str] = set()

    def isolate_send(
        self,
        *,
        subscriber_id: str,
        suppress: bool = True,
    ) -> SubsystemBoundary:
        """Sync boundary the fanout uses around each ``send()`` call.

        ``subscriber_id`` is stored as the boundary's payload kind so
        a single misbehaving subscriber gets quarantined without
        affecting healthy ones (the websocket policy enables
        ``quarantine_payload_kind`` for this).
        """
        return SubsystemBoundary(
            self._domain,
            payload_kind=subscriber_id,
            suppress=suppress,
            on_failure=lambda event: self._note_disconnect(event.payload_kind),
            swallow_unavailable=True,
        )

    def isolate_session(
        self,
        *,
        suppress: bool = False,
    ) -> AsyncSubsystemBoundary:
        return AsyncSubsystemBoundary(
            self._domain,
            payload_kind="",
            suppress=suppress,
            on_failure=None,
            swallow_unavailable=False,
        )

    def disconnected_subscribers(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._disconnected))

    def is_disconnected(self, subscriber_id: str) -> bool:
        with self._lock:
            return subscriber_id in self._disconnected

    def reinstate(self, subscriber_id: str) -> bool:
        with self._lock:
            existed = subscriber_id in self._disconnected
            self._disconnected.discard(subscriber_id)
        if existed:
            self._domain.release_quarantine(subscriber_id)
        return existed

    def _note_disconnect(self, subscriber_id: str) -> None:
        if not subscriber_id:
            return
        with self._lock:
            self._disconnected.add(subscriber_id)
