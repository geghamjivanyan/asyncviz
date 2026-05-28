"""Lifetime counters for the blocking detector.

Distinct from :mod:`blocking_statistics` which aggregates window-level
duration / severity stats. This module tracks *meta*: how the detector
is performing — how many measurements it processed, how many
violations it produced, how many cooldowns suppressed, etc.

All counters are integer-only; updates take a single short lock.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.runtime.monitoring.blocking.blocking_classifier import BlockingSeverity


@dataclass(frozen=True, slots=True)
class BlockingMetricsSnapshot:
    """Immutable view of the detector's lifetime self-metrics."""

    measurements_processed: int
    violations_total: int
    violations_by_severity: dict[str, int]
    escalations_warning_to_critical: int
    escalations_critical_to_freeze: int
    windows_opened: int
    windows_closed: int
    cooldown_suppressions_total: int
    cooldown_suppressions_by_severity: dict[str, int]
    violation_events_emitted: int
    violation_events_dropped: int
    window_events_emitted: int
    window_events_dropped: int
    escalation_events_emitted: int
    escalation_events_dropped: int
    reconfigurations: int
    handler_failures: int

    def to_dict(self) -> dict[str, object]:
        return {
            "measurements_processed": self.measurements_processed,
            "violations_total": self.violations_total,
            "violations_by_severity": dict(self.violations_by_severity),
            "escalations_warning_to_critical": self.escalations_warning_to_critical,
            "escalations_critical_to_freeze": self.escalations_critical_to_freeze,
            "windows_opened": self.windows_opened,
            "windows_closed": self.windows_closed,
            "cooldown_suppressions_total": self.cooldown_suppressions_total,
            "cooldown_suppressions_by_severity": dict(self.cooldown_suppressions_by_severity),
            "violation_events_emitted": self.violation_events_emitted,
            "violation_events_dropped": self.violation_events_dropped,
            "window_events_emitted": self.window_events_emitted,
            "window_events_dropped": self.window_events_dropped,
            "escalation_events_emitted": self.escalation_events_emitted,
            "escalation_events_dropped": self.escalation_events_dropped,
            "reconfigurations": self.reconfigurations,
            "handler_failures": self.handler_failures,
        }


def _zero_by_severity() -> dict[str, int]:
    return {s.name: 0 for s in BlockingSeverity}


class BlockingMetrics:
    """Mutable lifetime counters. Thread-safe."""

    __slots__ = (
        "_cooldown_suppressions_by_severity",
        "_cooldown_suppressions_total",
        "_escalation_events_dropped",
        "_escalation_events_emitted",
        "_escalations_critical_to_freeze",
        "_escalations_warning_to_critical",
        "_handler_failures",
        "_lock",
        "_measurements_processed",
        "_reconfigurations",
        "_violation_events_dropped",
        "_violation_events_emitted",
        "_violations_by_severity",
        "_violations_total",
        "_window_events_dropped",
        "_window_events_emitted",
        "_windows_closed",
        "_windows_opened",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._measurements_processed = 0
        self._violations_total = 0
        self._violations_by_severity: dict[str, int] = _zero_by_severity()
        self._escalations_warning_to_critical = 0
        self._escalations_critical_to_freeze = 0
        self._windows_opened = 0
        self._windows_closed = 0
        self._cooldown_suppressions_total = 0
        self._cooldown_suppressions_by_severity: dict[str, int] = _zero_by_severity()
        self._violation_events_emitted = 0
        self._violation_events_dropped = 0
        self._window_events_emitted = 0
        self._window_events_dropped = 0
        self._escalation_events_emitted = 0
        self._escalation_events_dropped = 0
        self._reconfigurations = 0
        self._handler_failures = 0

    # ── recording ────────────────────────────────────────────────────────
    def record_measurement(self) -> None:
        with self._lock:
            self._measurements_processed += 1

    def record_violation(self, severity: BlockingSeverity) -> None:
        with self._lock:
            self._violations_total += 1
            self._violations_by_severity[severity.name] = (
                self._violations_by_severity.get(severity.name, 0) + 1
            )

    def record_escalation(
        self, *, from_severity: BlockingSeverity, to_severity: BlockingSeverity
    ) -> None:
        with self._lock:
            if (
                from_severity is BlockingSeverity.WARNING
                and to_severity is BlockingSeverity.CRITICAL
            ):
                self._escalations_warning_to_critical += 1
            if (
                from_severity is BlockingSeverity.CRITICAL
                and to_severity is BlockingSeverity.FREEZE
            ):
                self._escalations_critical_to_freeze += 1
            # WARNING → FREEZE is rare but possible (manual reclass).
            # Treated as two-step for counter purposes.
            if from_severity is BlockingSeverity.WARNING and to_severity is BlockingSeverity.FREEZE:
                self._escalations_warning_to_critical += 1
                self._escalations_critical_to_freeze += 1

    def record_window_opened(self) -> None:
        with self._lock:
            self._windows_opened += 1

    def record_window_closed(self) -> None:
        with self._lock:
            self._windows_closed += 1

    def record_cooldown_suppression(self, severity: BlockingSeverity) -> None:
        with self._lock:
            self._cooldown_suppressions_total += 1
            self._cooldown_suppressions_by_severity[severity.name] = (
                self._cooldown_suppressions_by_severity.get(severity.name, 0) + 1
            )

    def record_violation_event(self, *, accepted: bool) -> None:
        with self._lock:
            if accepted:
                self._violation_events_emitted += 1
            else:
                self._violation_events_dropped += 1

    def record_window_event(self, *, accepted: bool) -> None:
        with self._lock:
            if accepted:
                self._window_events_emitted += 1
            else:
                self._window_events_dropped += 1

    def record_escalation_event(self, *, accepted: bool) -> None:
        with self._lock:
            if accepted:
                self._escalation_events_emitted += 1
            else:
                self._escalation_events_dropped += 1

    def record_reconfiguration(self) -> None:
        with self._lock:
            self._reconfigurations += 1

    def record_handler_failure(self) -> None:
        with self._lock:
            self._handler_failures += 1

    # ── snapshot ─────────────────────────────────────────────────────────
    def snapshot(self) -> BlockingMetricsSnapshot:
        with self._lock:
            return BlockingMetricsSnapshot(
                measurements_processed=self._measurements_processed,
                violations_total=self._violations_total,
                violations_by_severity=dict(self._violations_by_severity),
                escalations_warning_to_critical=self._escalations_warning_to_critical,
                escalations_critical_to_freeze=self._escalations_critical_to_freeze,
                windows_opened=self._windows_opened,
                windows_closed=self._windows_closed,
                cooldown_suppressions_total=self._cooldown_suppressions_total,
                cooldown_suppressions_by_severity=dict(self._cooldown_suppressions_by_severity),
                violation_events_emitted=self._violation_events_emitted,
                violation_events_dropped=self._violation_events_dropped,
                window_events_emitted=self._window_events_emitted,
                window_events_dropped=self._window_events_dropped,
                escalation_events_emitted=self._escalation_events_emitted,
                escalation_events_dropped=self._escalation_events_dropped,
                reconfigurations=self._reconfigurations,
                handler_failures=self._handler_failures,
            )
