"""Blocking-window lifecycle.

A *blocking window* groups a contiguous run of violations into one
unit so downstream consumers (timeline overlays, freeze heatmaps,
warning manager) can talk about "the freeze that started at sample
4250 and lasted 1.2s" rather than 6 unrelated violation events.

Window lifecycle::

    OPEN (first violation crossing window_open_severity)
      → EXTEND (each subsequent violation while open)
      → CLOSE (after window_close_consecutive_normals normal samples)

Each window holds:

* monotonic-ish identity (``window_id`` — deterministic from open
  index + runtime_id so replays produce stable ids).
* start / end monotonic_ns + sample indices.
* peak lag observed within the window.
* peak severity reached.
* violation count + escalation count.

All math is integer-nanosecond — no float drift across replays.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.clock.conversions import NS_PER_MS, NS_PER_SECOND
from asyncviz.runtime.monitoring.blocking.blocking_classifier import (
    BlockingClassification,
    BlockingSeverity,
)
from asyncviz.runtime.monitoring.blocking.blocking_escalation import EscalationOutcome
from asyncviz.runtime.monitoring.blocking.blocking_thresholds import BlockingThresholdPolicy


@dataclass(frozen=True, slots=True)
class BlockingWindowSnapshot:
    """Immutable view of one window.

    Frozen so consumers can stash it in caches / send it over the wire
    without worrying about later mutation. The mutable working object
    lives in :class:`BlockingWindowState`.
    """

    window_id: str
    runtime_id: str
    open_sample_index: int
    close_sample_index: int | None
    open_monotonic_ns: int
    close_monotonic_ns: int | None
    peak_lag_ns: int
    peak_severity: BlockingSeverity
    violation_count: int
    escalation_count: int
    closed: bool

    @property
    def duration_ns(self) -> int:
        if self.close_monotonic_ns is None:
            return 0
        delta = self.close_monotonic_ns - self.open_monotonic_ns
        return delta if delta > 0 else 0

    @property
    def duration_seconds(self) -> float:
        return self.duration_ns / NS_PER_SECOND

    @property
    def duration_ms(self) -> float:
        return self.duration_ns / NS_PER_MS

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "runtime_id": self.runtime_id,
            "open_sample_index": self.open_sample_index,
            "close_sample_index": self.close_sample_index,
            "open_monotonic_ns": self.open_monotonic_ns,
            "close_monotonic_ns": self.close_monotonic_ns,
            "peak_lag_ns": self.peak_lag_ns,
            "peak_severity": self.peak_severity.name,
            "violation_count": self.violation_count,
            "escalation_count": self.escalation_count,
            "closed": self.closed,
            "duration_ns": self.duration_ns,
            "duration_ms": self.duration_ms,
        }


@dataclass(slots=True)
class _ActiveWindow:
    """Mutable per-window working state.

    Internal only — promoted to :class:`BlockingWindowSnapshot` for
    every external consumer.
    """

    window_id: str
    runtime_id: str
    open_sample_index: int
    open_monotonic_ns: int
    peak_lag_ns: int
    peak_severity: BlockingSeverity
    violation_count: int
    escalation_count: int
    consecutive_normals: int = 0
    last_violation_sample_index: int = 0
    last_violation_monotonic_ns: int = 0

    def to_snapshot(self) -> BlockingWindowSnapshot:
        return BlockingWindowSnapshot(
            window_id=self.window_id,
            runtime_id=self.runtime_id,
            open_sample_index=self.open_sample_index,
            close_sample_index=None,
            open_monotonic_ns=self.open_monotonic_ns,
            close_monotonic_ns=None,
            peak_lag_ns=self.peak_lag_ns,
            peak_severity=self.peak_severity,
            violation_count=self.violation_count,
            escalation_count=self.escalation_count,
            closed=False,
        )

    def to_closed_snapshot(
        self,
        *,
        close_sample_index: int,
        close_monotonic_ns: int,
    ) -> BlockingWindowSnapshot:
        return BlockingWindowSnapshot(
            window_id=self.window_id,
            runtime_id=self.runtime_id,
            open_sample_index=self.open_sample_index,
            close_sample_index=close_sample_index,
            open_monotonic_ns=self.open_monotonic_ns,
            close_monotonic_ns=close_monotonic_ns,
            peak_lag_ns=self.peak_lag_ns,
            peak_severity=self.peak_severity,
            violation_count=self.violation_count,
            escalation_count=self.escalation_count,
            closed=True,
        )


@dataclass(frozen=True, slots=True)
class WindowTransition:
    """Outcome of feeding one sample to :class:`BlockingWindowTracker`.

    Exactly one of ``opened`` / ``extended`` / ``closed`` is true when
    something happened. All three are false on a sample that's outside
    a window (NORMAL with no open window) — the no-op case.
    """

    opened: BlockingWindowSnapshot | None
    extended: BlockingWindowSnapshot | None
    closed: BlockingWindowSnapshot | None
    active: BlockingWindowSnapshot | None


class BlockingWindowTracker:
    """Open / extend / close blocking windows from the classification stream.

    Drives:
      * one currently-open window at most (a fresh open creates a new
        identity).
      * a bounded ring of closed windows for snapshot serving.

    The closed-window ring is sized by ``history_capacity``. Older
    windows fall off — they remain in the replay log via
    :class:`EventReplayBuffer` (the violation/window-closed events were
    already streamed), so they don't disappear, they just stop being
    queryable from the detector's snapshot.
    """

    DEFAULT_HISTORY_CAPACITY: int = 64

    def __init__(
        self,
        *,
        policy: BlockingThresholdPolicy,
        runtime_id: str,
        history_capacity: int = DEFAULT_HISTORY_CAPACITY,
    ) -> None:
        if history_capacity <= 0:
            raise ValueError(f"history_capacity must be > 0 (got {history_capacity})")
        self._policy = policy
        self._runtime_id = runtime_id
        self._lock = threading.Lock()
        self._active: _ActiveWindow | None = None
        self._history: deque[BlockingWindowSnapshot] = deque(maxlen=history_capacity)
        self._next_id = 0
        self._total_opened = 0
        self._total_closed = 0

    @property
    def policy(self) -> BlockingThresholdPolicy:
        return self._policy

    @property
    def total_opened(self) -> int:
        with self._lock:
            return self._total_opened

    @property
    def total_closed(self) -> int:
        with self._lock:
            return self._total_closed

    def configure(self, policy: BlockingThresholdPolicy) -> None:
        with self._lock:
            self._policy = policy

    def has_active(self) -> bool:
        with self._lock:
            return self._active is not None

    def active_snapshot(self) -> BlockingWindowSnapshot | None:
        with self._lock:
            return None if self._active is None else self._active.to_snapshot()

    def history_snapshot(self) -> tuple[BlockingWindowSnapshot, ...]:
        with self._lock:
            return tuple(self._history)

    def reset(self) -> None:
        with self._lock:
            self._active = None
            self._history.clear()
            self._next_id = 0
            self._total_opened = 0
            self._total_closed = 0

    def process(self, outcome: EscalationOutcome) -> WindowTransition:
        """Advance window state for one escalation outcome."""
        with self._lock:
            policy = self._policy
            classification: BlockingClassification = outcome.classification
            severity = outcome.effective_severity
            measurement = classification.measurement

            opened: BlockingWindowSnapshot | None = None
            extended: BlockingWindowSnapshot | None = None
            closed: BlockingWindowSnapshot | None = None

            if policy.should_open_window(severity):
                if self._active is None:
                    self._next_id += 1
                    window_id = f"{self._runtime_id}:bw:{self._next_id}"
                    self._active = _ActiveWindow(
                        window_id=window_id,
                        runtime_id=self._runtime_id,
                        open_sample_index=measurement.sample_index,
                        open_monotonic_ns=measurement.actual_ns,
                        peak_lag_ns=classification.lag_ns,
                        peak_severity=severity,
                        violation_count=1,
                        escalation_count=1 if outcome.escalated else 0,
                        consecutive_normals=0,
                        last_violation_sample_index=measurement.sample_index,
                        last_violation_monotonic_ns=measurement.actual_ns,
                    )
                    self._total_opened += 1
                    opened = self._active.to_snapshot()
                else:
                    self._active.violation_count += 1
                    if outcome.escalated:
                        self._active.escalation_count += 1
                    if classification.lag_ns > self._active.peak_lag_ns:
                        self._active.peak_lag_ns = classification.lag_ns
                    if severity > self._active.peak_severity:
                        self._active.peak_severity = severity
                    self._active.consecutive_normals = 0
                    self._active.last_violation_sample_index = measurement.sample_index
                    self._active.last_violation_monotonic_ns = measurement.actual_ns
                    extended = self._active.to_snapshot()
            else:
                # severity below window-open threshold — either decay an
                # open window or remain idle.
                if self._active is not None:
                    self._active.consecutive_normals += 1
                    if self._active.consecutive_normals >= policy.window_close_consecutive_normals:
                        # Close at the *last violation* sample, not the
                        # current "all clear" sample. This makes the
                        # window's end coincide with the last symptom
                        # rather than the recovery moment.
                        snap = self._active.to_closed_snapshot(
                            close_sample_index=self._active.last_violation_sample_index,
                            close_monotonic_ns=self._active.last_violation_monotonic_ns,
                        )
                        self._history.append(snap)
                        self._total_closed += 1
                        self._active = None
                        closed = snap

            active = None if self._active is None else self._active.to_snapshot()
            return WindowTransition(
                opened=opened,
                extended=extended,
                closed=closed,
                active=active,
            )

    def force_close(self, *, monotonic_ns: int) -> BlockingWindowSnapshot | None:
        """Close any open window at ``monotonic_ns``. Used at shutdown."""
        with self._lock:
            if self._active is None:
                return None
            snap = self._active.to_closed_snapshot(
                close_sample_index=self._active.last_violation_sample_index,
                close_monotonic_ns=max(monotonic_ns, self._active.open_monotonic_ns),
            )
            self._history.append(snap)
            self._total_closed += 1
            self._active = None
            return snap
