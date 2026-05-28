from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StateStoreMetricsSnapshot:
    """Immutable view of :class:`StateStoreMetrics`.

    Each counter is monotonically increasing for the lifetime of the store
    instance. Naming is part of the public protocol — coordinate with the
    TypeScript ``StateStoreMetricsSnapshot`` definition.
    """

    events_applied: int
    events_stale: int
    events_duplicate: int
    events_unknown_type: int
    events_rejected: int
    rebuilds_completed: int
    last_event_sequence: int
    last_event_monotonic_ns: int
    last_event_id: str | None
    last_event_type: str | None
    subscription_dispatches: int
    subscription_failures: int
    snapshots_emitted: int


class StateStoreMetrics:
    """Mutable counters owned by :class:`RuntimeStateStore`.

    All updates go through a single lock; readers receive an atomic snapshot
    via :meth:`snapshot`. The lock is also the implicit serializer for the
    ``last_event_*`` fields so they advance monotonically with applies.
    """

    __slots__ = (
        "_events_applied",
        "_events_duplicate",
        "_events_rejected",
        "_events_stale",
        "_events_unknown_type",
        "_last_event_id",
        "_last_event_monotonic_ns",
        "_last_event_sequence",
        "_last_event_type",
        "_lock",
        "_rebuilds_completed",
        "_snapshots_emitted",
        "_subscription_dispatches",
        "_subscription_failures",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events_applied = 0
        self._events_stale = 0
        self._events_duplicate = 0
        self._events_unknown_type = 0
        self._events_rejected = 0
        self._rebuilds_completed = 0
        self._last_event_sequence = 0
        self._last_event_monotonic_ns = 0
        self._last_event_id: str | None = None
        self._last_event_type: str | None = None
        self._subscription_dispatches = 0
        self._subscription_failures = 0
        self._snapshots_emitted = 0

    # ── apply-side ───────────────────────────────────────────────────────
    def record_applied(
        self,
        *,
        sequence: int,
        monotonic_ns: int,
        event_id: str,
        event_type: str,
    ) -> None:
        with self._lock:
            self._events_applied += 1
            if sequence > self._last_event_sequence:
                self._last_event_sequence = sequence
            if monotonic_ns > self._last_event_monotonic_ns:
                self._last_event_monotonic_ns = monotonic_ns
            self._last_event_id = event_id
            self._last_event_type = event_type

    def record_stale(self) -> None:
        with self._lock:
            self._events_stale += 1

    def record_duplicate(self) -> None:
        with self._lock:
            self._events_duplicate += 1

    def record_unknown_type(self) -> None:
        with self._lock:
            self._events_unknown_type += 1

    def record_rejected(self) -> None:
        with self._lock:
            self._events_rejected += 1

    # ── lifecycle ────────────────────────────────────────────────────────
    def record_rebuild(self) -> None:
        with self._lock:
            self._rebuilds_completed += 1

    def record_snapshot(self) -> None:
        with self._lock:
            self._snapshots_emitted += 1

    # ── subscriptions ────────────────────────────────────────────────────
    def record_subscription_dispatch(self, *, failures: int) -> None:
        with self._lock:
            self._subscription_dispatches += 1
            self._subscription_failures += failures

    # ── reset (rebuild path) ─────────────────────────────────────────────
    def soft_reset_lifetime(self) -> None:
        """Reset per-event counters for a clean replay rebuild.

        Lifetime counters (``rebuilds_completed``, ``snapshots_emitted``,
        ``subscription_*``) survive so they reflect the store instance's
        whole history rather than just the current playback.
        """
        with self._lock:
            self._events_applied = 0
            self._events_stale = 0
            self._events_duplicate = 0
            self._events_unknown_type = 0
            self._events_rejected = 0
            self._last_event_sequence = 0
            self._last_event_monotonic_ns = 0
            self._last_event_id = None
            self._last_event_type = None

    def snapshot(self) -> StateStoreMetricsSnapshot:
        with self._lock:
            return StateStoreMetricsSnapshot(
                events_applied=self._events_applied,
                events_stale=self._events_stale,
                events_duplicate=self._events_duplicate,
                events_unknown_type=self._events_unknown_type,
                events_rejected=self._events_rejected,
                rebuilds_completed=self._rebuilds_completed,
                last_event_sequence=self._last_event_sequence,
                last_event_monotonic_ns=self._last_event_monotonic_ns,
                last_event_id=self._last_event_id,
                last_event_type=self._last_event_type,
                subscription_dispatches=self._subscription_dispatches,
                subscription_failures=self._subscription_failures,
                snapshots_emitted=self._snapshots_emitted,
            )
